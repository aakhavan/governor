"""Build evaluation: the build agent against a one-shot baseline (batch2b.md section 15).

::

    python -m governor.eval.build_eval --system agent|baseline --runs N --gold <file> --out <report.json>
        [--plan-model ...] [--write-model ...] [--llm fake:<script.json>|openrouter] [--max-cost-usd X] [--work <dir>]

Each run starts from an empty target (a fresh dbt project with ``models/sources.yml``) and an emptied
``dev_governor``: the objects there owned by the build login (``governor_build``) are dropped first, nothing else.

* ``agent``: the full build graph. The design is approved programmatically as ``eval-harness``; that bypass of the
  human gate exists only here and is recorded in every run and in the report.
* ``baseline``: one plan-model call (``prompts/baseline_build.md``) with the same profile, blueprint and KPI
  definitions (no templates) that returns every silver and gold file at once. The files are written, built once
  with ``dbt build`` and never validated or repaired.

Fake LLM scripts: the agent reads the build script format (``propose``, ``intermediate``, ``repair``); the baseline
reads ``{"baseline": ["<json {\\"files\\": [{\\"path\\", \\"content\\"}]}>", ...]}``. Lists are consumed in order and
the last reply repeats.

Gold checks come from the gold file (``table``, ``expr``, ``where``, ``expected``, ``tol``) and run against the run's
schema as the build login; a missing table or column fails that check.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import statistics
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable

import yaml
from pydantic import BaseModel, Field

from governor.build import gold as gold_mod
from governor.build import graph
from governor.build.dbt import DbtResult, run_dbt
from governor.build.llm import BuildLLM, FakeBuildLLM, LLMOutputError, OpenRouterLLM, make_llm
from governor.build.models import Proposal
from governor.core.catalogue import KpiCatalogue, load_blueprint, load_kpis

PROMPTS = Path(__file__).resolve().parent / "prompts"
SCHEMA = "dev_governor"
PROJECT = "shop"
APPROVER = "eval-harness"
# The expected KPI decisions on the shop data (section 15: 8 build, 2 decline); every other catalogue KPI is built.
EXPECTED_DECLINE = frozenset({"conversion_rate", "gross_margin"})
ALLOWED_ROOTS = ("models", "tests")


# --------------------------------------------------------------------------- gold checks


class GoldCheck(BaseModel):
    id: str
    table: str
    expr: str
    where: str = ""
    expected: float
    tol: float = 0.0


class GoldFile(BaseModel):
    version: int = 1
    dataset: str = ""
    checks: list[GoldCheck]


def load_gold(path: str | Path) -> GoldFile:
    return GoldFile.model_validate(yaml.safe_load(Path(path).read_text(encoding="utf-8")))


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class GoldQueryError(RuntimeError):
    """A gold check query failed; ``reason`` is ``missing_table``, ``missing_column`` or ``error``."""

    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


Query = Callable[[GoldCheck, str], Any]  # (check, schema) -> the single value, or raises GoldQueryError


def check_sql(check: GoldCheck, schema: str = SCHEMA):
    """The check as a composed query: ``select <expr> from <schema>.<table> [where <where>]``.

    ``expr`` and ``where`` come from the human-owned, hash-frozen gold file; the table name is quoted."""
    from psycopg import sql

    q = sql.SQL("select {} from {}.{}").format(sql.SQL(check.expr), sql.Identifier(schema), sql.Identifier(check.table))
    if check.where.strip():
        q = q + sql.SQL(" where ") + sql.SQL(check.where)
    return q


def pg_query(dsn: str | None = None) -> Query:
    """A query function over the build login; every check runs in its own autocommit statement."""

    def run(check: GoldCheck, schema: str) -> Any:
        import psycopg
        from psycopg import errors

        from governor.build.workspace import build_dsn

        try:
            with psycopg.connect(dsn or build_dsn(), autocommit=True) as conn:
                row = conn.execute(check_sql(check, schema)).fetchone()
        except errors.UndefinedTable as e:
            raise GoldQueryError("missing_table", _first_line(e)) from None
        except errors.UndefinedColumn as e:
            raise GoldQueryError("missing_column", _first_line(e)) from None
        except psycopg.Error as e:
            raise GoldQueryError("error", _first_line(e)) from None
        return row[0] if row else None

    return run


def score_gold(checks: list[GoldCheck], query: Query, schema: str = SCHEMA) -> list[dict]:
    """One result per check: ``{id, table, passed, value, expected, tol, reason}``."""
    out: list[dict] = []
    for c in checks:
        item: dict[str, Any] = {"id": c.id, "table": c.table, "expected": c.expected, "tol": c.tol, "value": None}
        try:
            raw = query(c, schema)
        except GoldQueryError as e:
            out.append({**item, "passed": False, "reason": e.reason, "error": str(e)[:300]})
            continue
        try:
            value = None if raw is None else float(raw)
        except (TypeError, ValueError):
            out.append({**item, "passed": False, "reason": "not_a_number"})
            continue
        if value is None:
            out.append({**item, "passed": False, "reason": "no_value"})
            continue
        ok = abs(value - c.expected) <= c.tol
        out.append({**item, "value": value, "passed": ok, "reason": "" if ok else "out_of_tolerance"})
    return out


# --------------------------------------------------------------------------- per-run environment


def _first_line(e: BaseException) -> str:
    text = str(e)
    return f"{type(e).__name__}: {text.splitlines()[0] if text else ''}"


def empty_dev_schema(dsn: str | None = None, schema: str = SCHEMA) -> list[str]:
    """Drop the relations in ``schema`` owned by the build login (current_user); nothing else is touched.

    No CASCADE: objects are dropped views first and retried until no more can go, so a dependent object owned by
    another role makes the drop fail instead of silently removing it."""
    import psycopg
    from psycopg import sql

    from governor.build.workspace import build_dsn

    kinds = {"v": "VIEW", "m": "MATERIALIZED VIEW", "r": "TABLE", "p": "TABLE", "f": "FOREIGN TABLE"}
    dropped: list[str] = []
    with psycopg.connect(dsn or build_dsn(), autocommit=True) as conn:
        rows = conn.execute(
            "select c.relname, c.relkind from pg_class c join pg_namespace n on n.oid = c.relnamespace "
            "where n.nspname = %s and c.relkind = any(%s) and pg_get_userbyid(c.relowner) = current_user",
            (schema, list(kinds)),
        ).fetchall()
        pending = sorted(rows, key=lambda r: (r[1] not in ("v", "m"), r[0]))
        while pending:
            left, last = [], None
            for name, kind in pending:
                stmt = sql.SQL("drop {} if exists {}.{}").format(sql.SQL(kinds[kind]), sql.Identifier(schema),
                                                               sql.Identifier(name))
                try:
                    conn.execute(stmt)
                    dropped.append(name)
                except psycopg.Error as e:
                    left.append((name, kind))
                    last = e
            if len(left) == len(pending):
                raise RuntimeError(f"cannot empty {schema}: {len(left)} object(s) left; {_first_line(last)}")
            pending = left
    return dropped


def new_target(work: Path, system: str, run: int) -> Path:
    """A fresh, empty dbt project with ``models/sources.yml`` written from schema raw."""
    from governor.build.__main__ import raw_tables
    from governor.build.workspace import init_target, write_sources

    target = work / f"{system}-{run:02d}" / "project"
    if target.exists():
        raise RuntimeError(f"target {target} already exists")
    init_target(target, PROJECT)
    write_sources(target, raw_tables())
    return target


@dataclass
class Hooks:
    """Everything a run touches outside Python; tests replace these with fakes."""

    reset: Callable[[], Any] = empty_dev_schema
    make_target: Callable[[Path, str, int], Path] = new_target
    query: Query = field(default_factory=pg_query)
    profiler: Callable[[str], dict] = graph.default_profiler
    dbt_runner: Callable[[Path, list[str]], DbtResult] = run_dbt
    graph_kwargs: dict = field(default_factory=dict)  # extra build_graph arguments (inspector, row_counter, ...)
    policy: Path = graph.DEFAULT_POLICY
    kpis_path: Path = graph.DEFAULT_KPIS
    blueprint_path: Path = graph.DEFAULT_BLUEPRINT


# --------------------------------------------------------------------------- shared scoring


def kpi_decisions(decisions: dict[str, str], catalogue: KpiCatalogue) -> int:
    """How many catalogue KPIs got the expected decision (build, or decline for :data:`EXPECTED_DECLINE`)."""
    return sum(decisions.get(k.id) == ("decline" if k.id in EXPECTED_DECLINE else "build") for k in catalogue.kpis)


def count_tests(results: list[dict]) -> tuple[int, int]:
    """(passed, failed) dbt tests in one run_results list."""
    passed = failed = 0
    for r in results:
        if not str(r.get("unique_id") or "").startswith("test."):
            continue
        status = (r.get("status") or "").lower()
        passed += status == "pass"
        failed += status in ("fail", "error", "runtime error")
    return passed, failed


def blueprint_breakdown(findings: Any) -> dict[str, dict[str, int]]:
    """``{rule: {severity: count}}`` for blueprint findings (dicts or objects); counts only, no file contents."""
    out: dict[str, dict[str, int]] = {}
    for f in findings or []:
        rule, severity = ((f.get("rule"), f.get("severity")) if isinstance(f, dict)
                          else (getattr(f, "rule", None), getattr(f, "severity", None)))
        by = out.setdefault(str(rule), {})
        by[str(severity)] = by.get(str(severity), 0) + 1
    return {r: dict(sorted(s.items())) for r, s in sorted(out.items())}


def _last_results(target: Path) -> list[dict]:
    path = Path(target) / "target" / "run_results.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("results", [])
    except (OSError, ValueError):
        return []
    return [{"unique_id": r.get("unique_id"), "status": r.get("status")} for r in raw]


def _cost(calls: list[dict]) -> float | None:
    return gold_mod.model_cost(calls)["cost_usd"]


# --------------------------------------------------------------------------- agent


def run_agent(llm: BuildLLM, target: Path, work: Path, hooks: Hooks, catalogue: KpiCatalogue) -> dict:
    checkpoints = work / "checkpoints.sqlite"
    kw = {"checkpoints": checkpoints, "profiler": hooks.profiler, "dbt_runner": hooks.dbt_runner,
          "kpis_path": hooks.kpis_path, "blueprint_path": hooks.blueprint_path, **hooks.graph_kwargs}
    out = graph.start(target, PROJECT, llm, policy=hooks.policy, **kw)
    tid = out["thread_id"]
    approved_by = None
    if out.get("status") == graph.AWAITING:
        approved_by = APPROVER  # the programmatic approval: only inside this harness
        out = graph.approve(tid, APPROVER, llm, **kw)
    gkw = {k: v for k, v in kw.items() if k != "checkpoints"}
    with graph.open_checkpointer(checkpoints) as saver:
        values = graph.build_graph(llm, saver, **gkw).get_state({"configurable": {"thread_id": tid}}).values or {}
    status = values.get("status") or out.get("status")
    gate_reached = status != graph.INVALID and values.get("proposal") is not None
    proposal = values.get("proposal")
    decisions = {k.id: k.decision for k in Proposal.model_validate(proposal).kpis} if proposal else {}
    sv, gd = values.get("silver") or {}, values.get("gold") or {}
    passed = int(sv.get("tests_passed") or 0) + int(gd.get("tests_passed") or 0)
    failed = 0 if status == graph.BUILT else count_tests(_last_results(target))[1]
    return {
        "status": status,
        "thread_id": tid,
        "approved_by": approved_by,
        "valid_design_first_try": bool(gate_reached and int(values.get("repairs") or 0) == 0),
        "validation_repairs": int(values.get("repairs") or 0),
        "dbt_repairs": int(values.get("sql_repairs") or 0),
        "escalated": status == graph.ESCALATED,
        "tests_passed": passed,
        "tests_failed": failed,
        "blueprint_high": sum((f.get("severity") == "high") for f in values.get("blueprint") or []),
        "blueprint_findings": blueprint_breakdown(values.get("blueprint")),
        "kpi_decisions_correct": kpi_decisions(decisions, catalogue),
    }


# --------------------------------------------------------------------------- baseline


class BaselineFile(BaseModel):
    path: str
    content: str


class BaselineReply(BaseModel):
    files: list[BaselineFile] = Field(default_factory=list)


def output_columns(template_sql: str) -> list[str]:
    """The output column names of a catalogue template (its outer SELECT), placeholders filled with dummies."""
    import sqlglot

    sql = re.sub(r"\{(\w+)\}", r"\1", template_sql)
    try:
        return list(sqlglot.parse_one(sql, read="postgres").named_selects)
    except Exception:  # noqa: BLE001
        return []


def kpis_for_baseline(catalogue: KpiCatalogue) -> list[dict]:
    """The KPI definitions without templates: what to compute, from which inputs, and the output columns."""
    from governor.build.design import catalogue_for_prompt

    by_id = {k.id: k for k in catalogue.kpis}
    return [{**d, "model": gold_mod.model_name(d["id"]), "output_columns": output_columns(by_id[d["id"]].template_sql)}
            for d in catalogue_for_prompt(catalogue)]


def baseline_prompt(profile: dict, catalogue: KpiCatalogue, blueprint) -> str:
    from governor.build.design import _dump, blueprint_for_prompt, profile_for_prompt

    text = (PROMPTS / "baseline_build.md").read_text(encoding="utf-8")
    parts = {"{{profile}}": _dump(profile_for_prompt(profile)),
             "{{blueprint}}": _dump(blueprint_for_prompt(blueprint)),
             "{{kpis}}": _dump(kpis_for_baseline(catalogue))}
    for key, value in parts.items():
        text = text.replace(key, value)
    return text.rstrip() + "\n"


def safe_path(target: Path, raw: str) -> Path | None:
    """``target/raw`` when ``raw`` is a relative path under ``models/`` or ``tests/``; else None."""
    p = PurePosixPath(raw.replace("\\", "/").strip())
    if p.is_absolute() or not p.parts or p.parts[0] not in ALLOWED_ROOTS or len(p.parts) < 2 \
            or any(part in ("..", "") or ":" in part for part in p.parts):
        return None
    out = (Path(target) / Path(*p.parts)).resolve()
    root = (Path(target) / p.parts[0]).resolve()
    return out if root in out.parents else None


def write_baseline(target: Path, reply: BaselineReply) -> tuple[list[str], list[str]]:
    """Write each file under the target; (written, refused) relative paths."""
    written, refused = [], []
    for f in reply.files:
        dest = safe_path(target, f.path)
        if dest is None or dest.name == "sources.yml":
            refused.append(f.path)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(f.content.rstrip() + "\n", encoding="utf-8")
        written.append(dest.relative_to(Path(target).resolve()).as_posix())
    return written, refused


def run_baseline(llm: BuildLLM, target: Path, hooks: Hooks, catalogue: KpiCatalogue) -> dict:
    blueprint = load_blueprint(hooks.blueprint_path)
    profile = hooks.profiler(str(hooks.policy))
    out: dict[str, Any] = {"approved_by": None, "valid_design_first_try": None, "validation_repairs": None,
                           "dbt_repairs": 0, "escalated": False, "tests_passed": 0, "tests_failed": 0,
                           "blueprint_high": None, "blueprint_findings": None, "kpi_decisions_correct": 0, "files": [], "refused_files": []}
    try:
        reply = llm.structured("baseline", baseline_prompt(profile, catalogue, blueprint), BaselineReply, role="plan")
    except LLMOutputError as e:
        return {**out, "status": "invalid_output", "error": str(e)[:500]}
    written, refused = write_baseline(target, reply)
    out |= {"files": written, "refused_files": refused}
    marts = {Path(p).stem for p in written if p.endswith(".sql")}
    decisions = {k.id: "build" if gold_mod.model_name(k.id) in marts else "decline" for k in catalogue.kpis}
    out["kpi_decisions_correct"] = kpi_decisions(decisions, catalogue)
    try:
        found = gold_mod.check_project(target, catalogue, str(hooks.policy), blueprint=blueprint)
        out["blueprint_high"] = len(gold_mod.high(found))
        out["blueprint_findings"] = blueprint_breakdown(found)
    except Exception as e:  # noqa: BLE001 - a measurement only; the baseline is never validated
        out["blueprint_error"] = _first_line(e)
    res = hooks.dbt_runner(target, ["build"])  # once, never repaired
    out["tests_passed"], out["tests_failed"] = count_tests(res.results)
    out["status"] = "built" if res.ok and res.results else "failed"
    if out["status"] == "failed":
        out["error"] = "; ".join(f"{r.get('unique_id')} {r.get('status')}" for r in res.results
                                 if (r.get("status") or "").lower() in ("error", "fail", "runtime error"))[:500] \
                       or res.log_tail[-500:]
    return out


# --------------------------------------------------------------------------- the loop and the report


def models_used(llm: BuildLLM) -> dict:
    if isinstance(llm, OpenRouterLLM):
        return dict(llm.models)
    if isinstance(llm, FakeBuildLLM):
        return {"plan": "fake", "write": "fake"}
    return {"plan": type(llm).__name__, "write": type(llm).__name__}


def _mean(values: list) -> float | None:
    vals = [float(v) for v in values if v is not None]
    return round(statistics.fmean(vals), 6) if vals else None


def _rate(values: list) -> float | None:
    vals = [bool(v) for v in values if v is not None]
    return round(sum(vals) / len(vals), 6) if vals else None


def summarise(runs: list[dict], gold_total: int) -> dict:
    statuses: dict[str, int] = {}
    for r in runs:
        statuses[r["status"]] = statuses.get(r["status"], 0) + 1
    costs = [r.get("cost_usd") for r in runs]
    by_rule: dict[str, dict[str, int]] = {}
    for r in runs:
        for rule, sev in (r.get("blueprint_findings") or {}).items():
            tot = by_rule.setdefault(rule, {})
            for s, n in sev.items():
                tot[s] = tot.get(s, 0) + n
    return {
        "blueprint_findings_by_rule": {k: dict(sorted(v.items())) for k, v in sorted(by_rule.items())},
        "runs": len(runs),
        "statuses": statuses,
        "built_rate": _rate([r["status"] == "built" for r in runs]),
        "valid_design_first_try_rate": _rate([r.get("valid_design_first_try") for r in runs]),
        "escalated_rate": _rate([r.get("escalated") for r in runs]),
        "gold_all_passed_rate": _rate([r.get("gold_passed") == gold_total for r in runs]),
        "kpi_decisions_all_correct_rate": _rate([r.get("kpi_decisions_correct") == r.get("kpi_decisions_total")
                                                 for r in runs]),
        "mean": {k: _mean([r.get(k) for r in runs]) for k in
                 ("validation_repairs", "dbt_repairs", "tests_passed", "tests_failed", "blueprint_high",
                  "kpi_decisions_correct", "gold_passed", "cost_usd", "seconds")},
        "total_cost_usd": round(sum(c for c in costs if c is not None), 6) if runs else 0.0,
        "cost_unknown_runs": sum(c is None for c in costs),
    }


def evaluate(system: str, runs: int, gold_path: str | Path, llm: BuildLLM, *, work: Path | None = None,
             hooks: Hooks | None = None, max_cost_usd: float | None = None, llm_spec: str = "") -> dict:
    """Run ``system`` ``runs`` times and return the report (section 15)."""
    if system not in ("agent", "baseline"):
        raise ValueError(f"unknown system {system!r}: use agent or baseline")
    hooks = hooks or Hooks()
    work = Path(work or tempfile.mkdtemp(prefix="governor_build_eval_"))
    gold = load_gold(gold_path)
    catalogue = load_kpis(hooks.kpis_path)
    results: list[dict] = []
    total, stopped = 0.0, False
    for i in range(1, runs + 1):
        if max_cost_usd is not None and total >= max_cost_usd:
            stopped = True
            break
        before = len(llm.calls)
        t0 = time.perf_counter()
        row: dict[str, Any] = {"run": i, "system": system}
        try:
            hooks.reset()
            target = hooks.make_target(work, system, i)
            row["target"] = str(target)
            if system == "agent":
                row |= run_agent(llm, target, work / f"{system}-{i:02d}", hooks, catalogue)
            else:
                row |= run_baseline(llm, target, hooks, catalogue)
            checks = score_gold(gold.checks, hooks.query)
        except Exception as e:  # noqa: BLE001 - one broken run is recorded, the loop goes on
            row |= {"status": "error", "error": _first_line(e)[:500]}
            checks = [{"id": c.id, "table": c.table, "passed": False, "reason": "run_failed"} for c in gold.checks]
        calls = llm.calls[before:]
        row |= {"kpi_decisions_total": len(catalogue.kpis), "gold_passed": sum(c["passed"] for c in checks),
                "gold_total": len(gold.checks), "gold": checks, "llm_calls": len(calls), "cost_usd": _cost(calls),
                "seconds": round(time.perf_counter() - t0, 2)}
        total += row["cost_usd"] or 0.0
        results.append(row)
    return {
        "system": system,
        "gold_file": str(gold_path),
        "gold_sha256": file_sha256(gold_path),
        "gold_dataset": gold.dataset,
        "llm": llm_spec,
        "models": models_used(llm),
        "approval": APPROVER if system == "agent" else None,
        "max_cost_usd": max_cost_usd,
        "stopped_by_budget": stopped,
        "runs_requested": runs,
        "runs": results,
        "summary": summarise(results, len(gold.checks)),
        "total_cost_usd": round(total, 6),
        "work": str(work),
    }


def make_eval_llm(spec: str, plan_model: str | None, write_model: str | None) -> BuildLLM:
    if (spec or "openrouter").strip() == "openrouter":
        return OpenRouterLLM(plan_model, write_model)
    return make_llm(spec)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="governor.eval.build_eval")
    ap.add_argument("--system", required=True, choices=["agent", "baseline"])
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--gold", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--plan-model")
    ap.add_argument("--write-model")
    ap.add_argument("--llm", default="openrouter", help="openrouter or fake:<script.json>")
    ap.add_argument("--max-cost-usd", type=float, help="stop starting runs once the total cost reaches this")
    ap.add_argument("--work", type=Path, help="folder for the run targets (default: a new temp folder)")
    args = ap.parse_args(argv)
    if args.runs < 1:
        ap.error("--runs must be at least 1")
    try:
        llm = make_eval_llm(args.llm, args.plan_model, args.write_model)
        report = evaluate(args.system, args.runs, args.gold, llm, work=args.work, max_cost_usd=args.max_cost_usd,
                          llm_spec=args.llm if not args.llm.startswith("fake:") else "fake")
    except Exception as e:  # noqa: BLE001
        print(f"build eval failed: {_first_line(e)}", file=sys.stderr)
        return 1
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    s = report["summary"]
    print(json.dumps({"out": str(args.out), "system": args.system, "runs": s["runs"], "statuses": s["statuses"],
                      "mean_gold_passed": s["mean"]["gold_passed"], "gold_total": len(load_gold(args.gold).checks),
                      "total_cost_usd": report["total_cost_usd"], "stopped_by_budget": report["stopped_by_budget"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
