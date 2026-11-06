"""Silver (batch2.md section 9): write staging and intermediate models, build them in ``dev_governor``, repair.

- Staging SQL is code: ``select <expr> as <name>, ... from {{ source('raw', '<table>') }}``.
- Intermediate SQL comes from the write model (``prompts/intermediate.md``): it gets the model's description, its
  refs with their declared columns and its own declared columns; never a data value.
- :func:`check_sql` runs before dbt: exactly one SELECT (sqlglot, Postgres, after replacing the Jinja calls with
  identifiers), only ``{{ ref('<declared ref>') }}``, no ``source()`` in intermediate, no DDL or DML.
- ``_staging.yml`` / ``_intermediate.yml``: description, columns, ``meta: {pii: true}`` on PII columns (L6, under
  the column's ``config`` as dbt 1.10+ wants it), ``unique`` + ``not_null`` on a single-column key; a composite key
  gets a singular test ``tests/<model>__primary_key.sql`` (L4).
- ``dbt build --select staging intermediate`` as the build login into ``dev_governor``, then each model's columns
  are compared with the design through ``information_schema``. A failing model (SQL check, dbt error, failing
  test, column mismatch) goes back for repair (``prompts/repair.md``) with its error and SQL: at most
  :data:`WRITE_REPAIRS` repairs by the write model, then one by the plan model, then the build is ``escalated``.
  Only intermediate SQL is repaired: a failing staging model is the approved design, so it escalates at once with
  the dbt error (the fix is a new design through the gate).
- :func:`prune_stale` runs first: model, yml and key-test files the approved design no longer contains are removed
  from staging, intermediate and marts, so stale models never reach dbt.

The steps (:func:`write_silver`, :func:`dbt_build_silver`, :func:`repair_silver`, :func:`next_step`) work on a
plain JSON-able dict so the build graph can checkpoint between them; :func:`build_silver` chains them.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import SqlglotError

from governor.build.dbt import DbtResult, run_dbt
from governor.build.llm import BuildLLM, LLMOutputError
from governor.build.models import Proposal, SilverModel

PROMPTS = Path(__file__).resolve().parent / "prompts"
SCHEMA = "dev_governor"
STAGING, INTERMEDIATE = "staging", "intermediate"
WRITE_REPAIRS = 2  # write-model repairs per model; then the plan model gets one try
MAX_REPAIRS = WRITE_REPAIRS + 1

BUILT, ESCALATED = "silver_built", "escalated"

_JINJA = re.compile(r"\{\{(.*?)\}\}|\{%.*?%\}|\{#.*?#\}", re.S)
_REF = re.compile(r"""^\s*ref\(\s*(['"])([A-Za-z_][A-Za-z0-9_]*)\1\s*\)\s*$""")
_SOURCE = re.compile(r"""^\s*source\(\s*(['"])([A-Za-z_][A-Za-z0-9_]*)\1\s*,\s*(['"])([A-Za-z_][A-Za-z0-9_]*)\3\s*\)\s*$""")
_WRITE_NODES = (exp.DDL, exp.DML, exp.Into, exp.Command, exp.Grant, exp.Set, exp.Use, exp.Transaction,
                exp.Commit, exp.Rollback, exp.Copy, exp.Pragma)


def _proposal(design: Proposal | dict) -> Proposal:
    return design if isinstance(design, Proposal) else Proposal.model_validate(design)


# --------------------------------------------------------------------------- SQL


def staging_sql(model: SilverModel) -> str:
    """The staging model as code: one select of the declared expressions from its raw table."""
    cols = ",\n".join(f"    {c.expr} as {c.name}" for c in model.columns)
    return f"select\n{cols}\nfrom {{{{ source('raw', '{model.source_table}') }}}}\n"


def clean_sql(text: str) -> str:
    """A model reply as a model file: code fence removed, trailing semicolons dropped (dbt wraps the select)."""
    body = (text or "").strip()
    fence = re.search(r"```[A-Za-z]*\s*\n(.*?)```", body, re.S)
    if fence:
        body = fence.group(1).strip()
    while body.endswith(";"):
        body = body[:-1].rstrip()
    return body + "\n" if body else ""


def check_sql(model: SilverModel | str, sql: str, design: Proposal | dict) -> list[str]:
    """Problems with one model's SQL before dbt sees it; empty means it may be written and built."""
    prop = _proposal(design)
    m = prop.model(model) if isinstance(model, str) else model
    if m is None:
        return [f"'{model}' is not a silver model of the design"]
    problems: list[str] = []
    if not (sql or "").strip():
        return ["the SQL is empty"]

    def swap(match: re.Match) -> str:
        if match.group(1) is None:
            problems.append(f"Jinja block {match.group(0)[:40]!r} is not allowed; use only {{{{ ref('<model>') }}}}")
            return " "
        call = match.group(1)
        ref = _REF.match(call)
        if ref:
            name = ref.group(2)
            if name not in m.refs:
                problems.append(f"ref('{name}') is not a declared ref of {m.name} (declared: {', '.join(m.refs) or 'none'})")
            return f" __ref_{name} "
        src = _SOURCE.match(call)
        if src:
            if m.folder != STAGING:
                problems.append("source() is not allowed in an intermediate model; read silver through ref() (L3)")
            elif (src.group(2), src.group(4)) != ("raw", m.source_table):
                problems.append(f"source('{src.group(2)}', '{src.group(4)}') is not this model's raw table "
                                f"('raw', '{m.source_table}')")
            return f" __source_{src.group(2)}_{src.group(4)} "
        problems.append(f"Jinja call {{{{{call.strip()[:40]}}}}} is not allowed; use only {{{{ ref('<model>') }}}}")
        return " __jinja "

    plain = _JINJA.sub(swap, sql)
    if "{{" in plain or "{%" in plain or "}}" in plain:
        problems.append("unbalanced Jinja braces")
        return problems
    try:
        trees = [t for t in sqlglot.parse(plain, read="postgres") if t is not None]
    except SqlglotError as exc:
        problems.append(f"the SQL does not parse: {str(exc).splitlines()[0][:200]}")
        return problems
    if len(trees) != 1:
        problems.append(f"expected exactly one SELECT statement, found {len(trees)} statements")
        return problems
    tree = trees[0]
    if not isinstance(tree, exp.Query):
        problems.append(f"the statement is a {type(tree).__name__.upper()}, not a SELECT")
    bad = sorted({type(n).__name__.upper() for n in tree.walk() if isinstance(n, _WRITE_NODES)})
    if bad:
        problems.append(f"DDL or DML is not allowed ({', '.join(bad)})")
    return problems


# --------------------------------------------------------------------------- prompts


def _columns(m: SilverModel) -> list[dict]:
    return [{"name": c.name, "type": c.type, **({"description": c.description} if c.description else {})}
            for c in m.columns]


def _render(name: str, parts: dict[str, str]) -> str:
    text = (PROMPTS / name).read_text(encoding="utf-8")
    for key, value in parts.items():
        text = text.replace("{{" + key + "}}", value)
    return text.rstrip() + "\n"


def _model_block(m: SilverModel, prop: Proposal) -> dict[str, str]:
    refs = []
    for r in m.refs:
        rm = prop.model(r)
        refs.append(f"### {r}\n\n{rm.description if rm else ''}\n\n" + _table(_columns(rm) if rm else []))
    return {"model": m.name, "folder": m.folder, "description": m.description or "(none)",
            "primary_key": ", ".join(m.primary_key), "columns": _table(_columns(m)),
            "refs": "\n\n".join(refs) or "(none)"}


def _table(cols: list[dict]) -> str:
    lines = ["| column | type | description |", "|---|---|---|"]
    lines += [f"| {c['name']} | {c['type']} | {c.get('description', '')} |" for c in cols]
    return "\n".join(lines)


def intermediate_prompt(m: SilverModel, design: Proposal | dict) -> str:
    return _render("intermediate.md", _model_block(m, _proposal(design)))


def repair_prompt(m: SilverModel, design: Proposal | dict, sql: str, error: str) -> str:
    return _render("repair.md", {**_model_block(m, _proposal(design)), "sql": sql.strip() or "(no SQL yet)",
                                 "error": error.strip()[-3000:]})


# --------------------------------------------------------------------------- yml and tests


def _column_yml(m: SilverModel, c, docs: dict[str, dict[str, str]] | None = None) -> dict:
    out: dict[str, Any] = {"name": c.name, "description": ((docs or {}).get(m.name) or {}).get(c.name) or c.description or ""}
    if c.pii:
        out["config"] = {"meta": {"pii": True}}
    if len(m.primary_key) == 1 and m.primary_key[0] == c.name:
        out["data_tests"] = ["unique", "not_null"]
    return out


def models_yml(models: list[SilverModel], docs: dict[str, dict[str, str]] | None = None) -> str:
    """``docs``: model -> column -> description (``governor.build.docs.describe``); the design's text otherwise."""
    doc = {"version": 2, "models": [
        {"name": m.name, "description": m.description or "",
         "config": {"meta": {"primary_key": list(m.primary_key)}},
         "columns": [_column_yml(m, c, docs) for c in m.columns]} for m in models]}
    return yaml.safe_dump(doc, sort_keys=False, allow_unicode=True)


def composite_key_test(m: SilverModel) -> str:
    """A singular test that returns a row for each null part or duplicate of a composite primary key (L4)."""
    keys = ", ".join(m.primary_key)
    nulls = " or ".join(f"{k} is null" for k in m.primary_key)
    return (f"-- {m.name}: primary key ({keys}) is unique and not null\n"
            f"select {keys}, count(*) as n\nfrom {{{{ ref('{m.name}') }}}}\n"
            f"group by {keys}\nhaving count(*) > 1 or bool_or({nulls})\n")


def key_test_name(m: SilverModel) -> str:
    return f"{m.name}__primary_key"


# --------------------------------------------------------------------------- state and steps


def model_path(target: str | Path, m: SilverModel) -> Path:
    return Path(target) / "models" / m.folder / f"{m.name}.sql"


def new_state() -> dict:
    """``sql``: model -> current SQL; ``failures``: model -> error; ``attempts``: model -> repairs made;
    ``repairs``: total repair calls."""
    return {"sql": {}, "failures": {}, "attempts": {}, "repairs": 0, "tests_passed": 0,
            "models": [], "dbt_runs": 0, "status": None, "escalated": None, "folders": {}, "pruned": []}


def _accept(target: Path, m: SilverModel, sql: str, prop: Proposal, st: dict) -> None:
    """Record ``sql`` for ``m``; write the file only when it passes check_sql, else keep it as a failure."""
    st["sql"][m.name] = sql
    problems = check_sql(m, sql, prop)
    if problems:
        st["failures"][m.name] = "the SQL was refused before dbt:\n- " + "\n- ".join(problems)
        return
    st["failures"].pop(m.name, None)
    path = model_path(target, m)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sql, encoding="utf-8")


MODEL_FOLDERS = (STAGING, INTERMEDIATE, "marts")
_YML_SUFFIXES = (".yml", ".yaml")


def mart_folder(domain: str | None) -> str:
    """The ``models/marts/<domain>`` folder name for a KPI domain: lower case, ``[a-z0-9_]`` only."""
    return re.sub(r"[^a-z0-9_]+", "_", (domain or "").strip().lower()).strip("_") or "general"


def expected_files(target: str | Path, design: Proposal | dict) -> set[Path]:
    """Model, yml and singular-test files the approved design produces (silver here, gold in ``gold.py``)."""
    target, prop = Path(target), _proposal(design)
    models = target / "models"
    out: set[Path] = set()
    for m in prop.silver_models:
        out.add(models / m.folder / f"{m.name}.sql")
        if len(m.primary_key) > 1:
            out.add(target / "tests" / f"{key_test_name(m)}.sql")
    out.add(models / STAGING / "_staging.yml")
    out.add(models / INTERMEDIATE / "_intermediate.yml")
    for k in prop.kpis:
        if k.decision == "build":
            domain = mart_folder(k.domain)
            out.add(models / "marts" / domain / f"kpi_{k.id}.sql")
            out.add(models / "marts" / domain / f"_{domain}.yml")
    return {p.resolve() for p in out}


def prune_stale(target: str | Path, design: Proposal | dict) -> list[Path]:
    """Remove model and yml files under staging, intermediate and marts (and composite-key tests) that the approved
    design no longer contains, so stale models never reach dbt. Returns the removed paths."""
    target = Path(target)
    keep = expected_files(target, design)
    removed: list[Path] = []
    candidates: list[Path] = []
    for folder in MODEL_FOLDERS:
        d = target / "models" / folder
        if d.is_dir():
            candidates += [p for p in d.rglob("*") if p.is_file() and p.suffix in (".sql", *_YML_SUFFIXES)]
    tests = target / "tests"
    if tests.is_dir():
        candidates += [p for p in tests.glob("*__primary_key.sql") if p.is_file()]
    for p in candidates:
        if p.resolve() not in keep:
            p.unlink()
            removed.append(p)
    marts = target / "models" / "marts"
    if marts.is_dir():
        for d in sorted((p for p in marts.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(d.iterdir()):
                d.rmdir()
    return removed


def write_silver(target: str | Path, design: Proposal | dict, llm: BuildLLM, state: dict | None = None, *,
                 docs: dict[str, dict[str, str]] | None = None) -> dict:
    """Write staging (code), intermediate (write model), the yml files and the composite-key tests.

    ``docs`` (model -> column -> description, from ``governor.build.docs.describe``) fills the yml column
    descriptions (batch2c section 16); without it the design's descriptions are written.

    Files from an earlier design that this one no longer contains are removed first (:func:`prune_stale`)."""
    target, prop = Path(target), _proposal(design)
    st = state if state is not None else new_state()
    st["pruned"] = [p.relative_to(target).as_posix() for p in prune_stale(target, prop)]
    st["folders"] = {m.name: m.folder for m in prop.silver_models}
    for folder, yml in ((STAGING, "_staging.yml"), (INTERMEDIATE, "_intermediate.yml")):
        models = [m for m in prop.silver_models if m.folder == folder]
        d = target / "models" / folder
        d.mkdir(parents=True, exist_ok=True)
        (d / yml).write_text(models_yml(models, docs), encoding="utf-8")
    tests = target / "tests"
    tests.mkdir(parents=True, exist_ok=True)
    for m in prop.silver_models:
        if len(m.primary_key) > 1:
            (tests / f"{key_test_name(m)}.sql").write_text(composite_key_test(m), encoding="utf-8")
    for m in prop.silver_models:
        if m.folder == STAGING:
            sql = staging_sql(m)
        else:
            try:
                sql = clean_sql(llm.text("intermediate", intermediate_prompt(m, prop), key=m.name, role="write"))
            except LLMOutputError as exc:
                st["sql"][m.name] = ""
                st["failures"][m.name] = f"the write model gave no SQL: {exc}"
                continue
        _accept(target, m, sql, prop, st)
    st["models"] = [m.name for m in prop.silver_models]
    return st


def _owner(unique_id: str, names: list[str]) -> str | None:
    """The silver model a dbt node belongs to: ``model.<project>.<name>`` or a test whose name contains it."""
    parts = (unique_id or "").split(".")
    if len(parts) >= 3 and parts[0] in ("model", "seed", "snapshot"):
        return parts[2] if parts[2] in names else None
    node = parts[2] if len(parts) >= 3 else unique_id or ""
    hits = [n for n in names if n in node]
    return max(hits, key=len) if hits else None


def declared_vs_built(design: Proposal | dict, built: dict[str, list[str]]) -> dict[str, str]:
    """Column mismatches between the design and ``information_schema`` (model -> problem)."""
    out: dict[str, str] = {}
    for m in _proposal(design).silver_models:
        have = [c.lower() for c in built.get(m.name, [])]
        if not have:
            out[m.name] = f"{m.name} does not exist in {SCHEMA} after dbt build"
            continue
        want = [c.name.lower() for c in m.columns]
        missing = [c for c in want if c not in have]
        extra = [c for c in have if c not in want]
        if missing or extra:
            out[m.name] = (f"the built columns differ from the declared columns: missing {missing or 'none'}, "
                           f"not declared {extra or 'none'}; select exactly the declared columns, with those names")
    return out


def built_columns(names: list[str], dsn: str | None = None) -> dict[str, list[str]]:
    """Columns of each model in ``dev_governor``, read as the build login."""
    import psycopg

    from governor.build.workspace import build_dsn

    with psycopg.connect(dsn or build_dsn()) as conn:
        rows = conn.execute(
            "select table_name, column_name from information_schema.columns "
            "where table_schema = %s and table_name = any(%s) order by table_name, ordinal_position",
            (SCHEMA, list(names))).fetchall()
    out: dict[str, list[str]] = {}
    for table, column in rows:
        out.setdefault(table, []).append(column)
    return out


Runner = Callable[[Path, list[str]], DbtResult]
Inspector = Callable[[list[str]], dict[str, list[str]]]


def dbt_build_silver(target: str | Path, design: Proposal | dict, state: dict, *, runner: Runner = run_dbt,
                     inspector: Inspector = built_columns) -> dict:
    """``dbt build --select staging intermediate``; failures are dbt errors, failing tests and column mismatches."""
    target, prop = Path(target), _proposal(design)
    st = state
    names = [m.name for m in prop.silver_models]
    res = runner(target, ["build", "--select", STAGING, INTERMEDIATE])
    st["dbt_runs"] = st.get("dbt_runs", 0) + 1
    failures: dict[str, str] = {}
    passed = 0
    for r in res.results:
        status = (r.get("status") or "").lower()
        if status == "pass" and str(r.get("unique_id", "")).startswith("test."):
            passed += 1
        if status in ("error", "fail", "runtime error"):
            owner = _owner(r.get("unique_id") or "", names)
            what = "test" if str(r.get("unique_id", "")).startswith("test.") else "model"
            msg = f"dbt {what} {r.get('unique_id')} {status}: {(r.get('message') or '').strip()}"
            if owner:
                failures[owner] = (failures[owner] + "\n" + msg) if owner in failures else msg
    st["tests_passed"] = passed
    if not res.results:
        # dbt did not get to the models (profile, connection, parse): not something one model's SQL can fix
        st["failures"] = {}
        st["status"] = ESCALATED
        st["escalated"] = {"model": None, "error": "dbt build produced no results:\n" + res.log_tail[-2000:]}
        return st
    if not failures:
        try:
            failures = declared_vs_built(prop, inspector(names))
        except Exception as exc:  # noqa: BLE001
            st["failures"] = {}
            st["status"] = ESCALATED
            st["escalated"] = {"model": None, "error": f"cannot read information_schema: {type(exc).__name__}: "
                                                       f"{str(exc).splitlines()[0] if str(exc) else ''}"}
            return st
    st["failures"] = failures
    if not failures and res.ok:
        st["status"] = BUILT
    elif not failures:
        st["status"] = ESCALATED
        st["escalated"] = {"model": None, "error": "dbt build failed with no failing silver model:\n"
                                                   + res.log_tail[-2000:]}
    return st


def repair_silver(target: str | Path, design: Proposal | dict, llm: BuildLLM, state: dict) -> dict:
    """One repair call per failing model that has budget left (write model, then the plan model once)."""
    target, prop = Path(target), _proposal(design)
    st = state
    for name, error in list(st["failures"].items()):
        made = st["attempts"].get(name, 0)
        m = prop.model(name)
        if made >= MAX_REPAIRS or m is None or m.folder != INTERMEDIATE:
            continue  # only intermediate SQL is repaired; staging comes from the approved design (next_step)
        role = "write" if made < WRITE_REPAIRS else "plan"
        st["attempts"][name] = made + 1
        st["repairs"] = st.get("repairs", 0) + 1
        try:
            sql = clean_sql(llm.text("repair", repair_prompt(m, prop, st["sql"].get(name, ""), error), key=name, role=role))
        except LLMOutputError as exc:
            st["failures"][name] = f"{error}\n(repair {made + 1} gave no SQL: {exc})"
            continue
        _accept(target, m, sql, prop, st)  # a repair that passes check_sql clears the failure until dbt runs
    return st


def next_step(state: dict) -> str:
    """``dbt``, ``repair``, ``built`` or ``escalated``.

    A model still failing after :data:`MAX_REPAIRS` repairs escalates the build (naming it and its last error);
    A failing staging model (or any model that is not intermediate) is never repaired: its SQL is the approved
    design, so the build escalates at once with the error and the fix is a new design through the gate. Any other
    failure (refused by check_sql or failed in dbt) is repaired; no failure means dbt runs next.
    """
    st = state
    if st.get("status") in (BUILT, ESCALATED):
        return "built" if st["status"] == BUILT else "escalated"
    folders = st.get("folders") or {}
    fixed = [n for n in st["failures"] if folders.get(n, STAGING if n.startswith("stg_") else INTERMEDIATE) != INTERMEDIATE]
    if fixed:
        st["status"] = ESCALATED
        st["escalated"] = {"model": fixed[0], "folder": folders.get(fixed[0], STAGING),
                           "error": st["failures"][fixed[0]][-3000:],
                           "fix": "staging SQL is the approved design and is not repaired by a model; "
                                  "propose a corrected design and approve it at the design gate"}
        return "escalated"
    out = [n for n in st["failures"] if st["attempts"].get(n, 0) >= MAX_REPAIRS]
    if out:
        st["status"] = ESCALATED
        st["escalated"] = {"model": out[0], "error": st["failures"][out[0]][-3000:]}
        return "escalated"
    return "repair" if st["failures"] else "dbt"


@dataclass
class SilverResult:
    status: str  # silver_built | escalated
    models: list[str] = field(default_factory=list)
    tests_passed: int = 0
    repairs: int = 0
    escalated: dict | None = None  # {"model", "error"}
    state: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        out = {"status": self.status, "models": self.models, "tests_passed": self.tests_passed,
               "repairs": self.repairs}
        if self.escalated:
            out["escalated"] = self.escalated
        return out


def result(state: dict) -> SilverResult:
    return SilverResult(status=state.get("status") or ESCALATED, models=list(state.get("models") or []),
                        tests_passed=int(state.get("tests_passed") or 0), repairs=int(state.get("repairs") or 0),
                        escalated=state.get("escalated"), state=state)


def build_silver(target: str | Path, design: Proposal | dict, llm: BuildLLM, *, runner: Runner = run_dbt,
                 inspector: Inspector = built_columns) -> SilverResult:
    """Write, build, repair until built or escalated (the same steps the build graph checkpoints)."""
    st = write_silver(target, design, llm)
    while True:
        step = next_step(st)
        if step == "dbt":
            dbt_build_silver(target, design, st, runner=runner, inspector=inspector)
        elif step == "repair":
            repair_silver(target, design, llm, st)
        else:
            return result(st)


__all__ = ["BUILT", "ESCALATED", "MAX_REPAIRS", "SilverResult", "build_silver", "check_sql", "clean_sql",
           "composite_key_test", "dbt_build_silver", "intermediate_prompt", "mart_folder", "models_yml", "next_step",
           "prune_stale",
           "repair_prompt", "repair_silver", "result", "staging_sql", "write_silver"]
