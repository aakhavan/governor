"""The build ``StateGraph`` (batch2.md section 8), D3 and D4 parts: profile to the design gate, then silver.

::

    profile -> compare --up to date (batch3 section 29: drift.md, status up_to_date)--> END
                  | changed (previous design + drift note) or no fingerprint
               propose -> validate --findings, at most 2 repairs--> propose
                             | ok (or repairs used up: write_report, then status design_invalid)
                        write_report -> design_gate (interrupt)
             reject + note (once) <------|  approve
             -> propose                  v
                                    record_decisions -> write_silver (column docs first) --SQL refused--> repair_silver
                                                             | ok                          ^   |
                                                       dbt_build_silver --fail-------------+   |
                                                             | ok          (write model <= 2, then plan model once;
                                                             |              a failing staging model escalates at once)
                                                        silver_done --escalated--> END
                                                             | silver_built
                                                        write_gold (models, gaps.md, blueprint check)
                                                             | ok                 \\ high finding (blueprint_failed)
                                                        dbt_build_gold -> summarise (governor/build.json) -> END
                                                        (built | escalated)

Code owns every edge. Checkpoints live in ``GOVERNOR_STATE_DIR/build_checkpoints.sqlite``, so ``approve`` and
``reject`` resume the thread from a new process. The state holds the profile (no data values for PII columns), the
proposal and the findings; no raw rows.

``approve`` resumes the thread at the gate and runs on to ``built``, ``escalated`` or ``blueprint_failed`` in the
same call, returning ``kpis_built``, ``gaps``, ``tests_passed``, ``repairs`` and the ``blueprint`` findings. The
silver step state (SQL per model, failures, repairs per model) is kept under ``silver``; ``sql_repairs`` counts
repair calls (``repairs`` stays the design-loop count).

A rejection sends the design back once, with the note, for one more proposal round (that round has its own repair
budget). A second rejection ends the thread with status ``design_rejected``.
"""

from __future__ import annotations

import datetime as dt
import functools
import json
import operator
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Callable, Iterator, TypedDict

import yaml
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from governor.build import design, docs, drift, gold, silver
from governor.build.dbt import run_dbt
from governor.build.events import emit
from governor.build.llm import BuildLLM, LLMOutputError
from governor.build.models import Finding, Proposal
from governor.core import paths
from governor.core.catalogue import load_approved, load_blueprint, load_kpis

if TYPE_CHECKING:
    from governor.core.tenancy import Tenant

MAX_REPAIRS = 2
MAX_REJECTIONS = 1
CHECKPOINT_FILE = "build_checkpoints.sqlite"
DEFAULT_POLICY = paths.KNOWLEDGE / "shop" / "policy.yaml"
DEFAULT_KPIS = paths.KNOWLEDGE / "kpis.yaml"
DEFAULT_BLUEPRINT = paths.KNOWLEDGE / "blueprint.md"
DEFAULT_APPROVED = paths.KNOWLEDGE / "approved.yaml"

AWAITING = "awaiting_design_approval"
INVALID = "design_invalid"
APPROVED = "design_approved"
REJECTED = "design_rejected"
UP_TO_DATE = "up_to_date"

DRIFT_HEAD = "The raw schema changed since the last approved build:"
DRIFT_TAIL = "Keep every unchanged model and KPI mapping; change only what these differences require."


class BuildError(RuntimeError):
    """A build command cannot run (unknown thread, thread not at the gate, bad decision)."""


class BuildState(TypedDict, total=False):
    target: str
    project_name: str
    policy: str
    profile: dict
    proposal: dict | None
    findings: list[dict]
    repairs: int
    rejections: int
    note: str | None
    status: str
    report: str
    design: str | None
    approved_by: str
    approved_file: str
    silver: dict
    docs: dict  # model -> column -> description (batch2c section 16)
    sql_repairs: int
    gold: dict
    blueprint: list[dict]
    summary: dict
    force: bool  # skip the up-to-date check (batch3.md section 29)
    drift: list[str] | None  # Drift.summary_lines() of a drift run
    last_build: str | None  # the approved build an up-to-date run points to
    calls: Annotated[list[dict], operator.add]


# --------------------------------------------------------------------------- files in the target


def governor_dir(target: str | Path) -> Path:
    d = Path(target) / "governor"
    d.mkdir(parents=True, exist_ok=True)
    return d


def target_approved(target: str | Path) -> Path:
    return Path(target) / "governor" / "approved.yaml"


def load_approved_context(target: str | Path, default: Path | None = DEFAULT_APPROVED) -> list[dict]:
    """The decisions the plan model should follow: the cross-company defaults, then the company's own."""
    out: list[dict] = []
    for path in (default, target_approved(target)):
        if path is not None and Path(path).is_file():
            out += [d.model_dump(mode="json", exclude_none=True) for d in load_approved(path).decisions]
    return out


_APPROVED_HEADER = (
    "# Approved decisions for this company (governor batch2.md section 4; design.md section 8 format).\n"
    "# Written by governor when a design is approved; change it through a reviewed pull request.\n"
)


def mapping_decisions(proposal: Proposal, approved_by: str, approved_on: dt.date, thread_id: str) -> list[dict]:
    """One ``column_mapping`` decision per mapping entry of each built KPI."""
    out: list[dict] = []
    for k in proposal.kpis:
        if k.decision != "build":
            continue
        for name, value in k.mapping.items():
            out.append({
                "id": f"map-{k.id}-{name}",
                "kind": "column_mapping",
                "subject": f"kpi.{k.id}.{name}",
                "value": value,
                "reason": f"approved design for {k.id} ({k.domain or 'no domain'}): {name} -> {value}",
                "approved_by": approved_by,
                "approved_on": approved_on,
                "source": f"governor/design.json (build thread {thread_id})",
            })
    return out


def record_decisions(target: str | Path, proposal: Proposal, approved_by: str, approved_on: dt.date,
                     thread_id: str) -> Path:
    """Append the approved mappings to ``<target>/governor/approved.yaml``.

    Existing decisions are kept in order. A decision with the same id (the same KPI input approved again) is
    replaced in place: the latest approval wins. The file is checked with ``load_approved`` after writing.
    """
    path = target_approved(target)
    governor_dir(target)
    doc: dict[str, Any] = {"version": 1, "decisions": []}
    if path.is_file():
        load_approved(path)  # refuse to extend a file that does not validate
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or doc
        doc["decisions"] = list(doc.get("decisions") or [])
    index = {d.get("id"): i for i, d in enumerate(doc["decisions"])}
    for d in mapping_decisions(proposal, approved_by, approved_on, thread_id):
        if d["id"] in index:
            doc["decisions"][index[d["id"]]] = d
        else:
            index[d["id"]] = len(doc["decisions"])
            doc["decisions"].append(d)
    path.write_text(_APPROVED_HEADER + yaml.safe_dump(doc, sort_keys=False, allow_unicode=True), encoding="utf-8")
    load_approved(path)
    return path


def target_fingerprint(target: str | Path) -> Path:
    return Path(target) / "governor" / "profile_fingerprint.json"


def write_fingerprint(target: str | Path, profile: dict, approved_on: dt.date, thread_id: str) -> Path:
    """Write ``<target>/governor/profile_fingerprint.json`` for the profile the design was approved on (batch3.md
    section 28): names, types, PII flags and candidate keys only."""
    fp = drift.fingerprint(profile)
    path = target_fingerprint(target)
    governor_dir(target)
    doc = {"thread_id": thread_id, "approved_on": approved_on.isoformat(), "hash": drift.fingerprint_hash(fp),
           "fingerprint": fp}
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _read_json(path: Path) -> dict | None:
    """A JSON object file, or None when it is missing or unreadable."""
    try:
        doc = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (OSError, ValueError):
        return None
    return doc if isinstance(doc, dict) else None


def drift_note(lines: list[str]) -> str:
    """The note a drift run gives the plan model (batch3.md section 29.2)."""
    return "\n".join([DRIFT_HEAD, *(f"- {ln}" for ln in lines), DRIFT_TAIL])


def write_drift(target: str | Path, text: str) -> Path:
    path = governor_dir(target) / "drift.md"
    path.write_text(text, encoding="utf-8")
    return path


# --------------------------------------------------------------------------- graph


def default_profiler(policy_path: str) -> dict:
    from governor.build.profile import load_policy, profile_schema
    from governor.build.workspace import build_dsn

    return profile_schema(build_dsn(), "raw", load_policy(policy_path))


def tenant_profiler(dsn: str) -> Callable[[str], dict]:
    """A profiler bound to one database (a tenant's ``build_dsn()``), not to the process environment."""

    def profiler(policy_path: str) -> dict:
        from governor.build.profile import load_policy, profile_schema

        return profile_schema(dsn, "raw", load_policy(policy_path))

    return profiler


def tenant_graph_kwargs(tenant: Tenant) -> dict[str, Any]:
    """The ``build_graph`` keyword arguments for one tenant (batch3.md section 31.2): its catalogue, blueprint and
    default decisions, a profiler, inspector and row counter on its database, and dbt with its env. Nothing
    process-wide is changed."""
    dsn = tenant.build_dsn()
    return {"profiler": tenant_profiler(dsn), "kpis_path": tenant.kpis_path, "blueprint_path": tenant.blueprint_path,
            "default_approved": tenant.approved_default,
            "dbt_runner": functools.partial(run_dbt, env=tenant.dbt_env()),
            "inspector": functools.partial(silver.built_columns, dsn=dsn),
            "row_counter": functools.partial(gold.kpi_rows, dsn=dsn)}


def _for_tenant(tenant: Tenant | None, checkpoints: str | Path | None,
                graph_kwargs: dict[str, Any]) -> tuple[str | Path | None, dict[str, Any]]:
    """Checkpoints and graph kwargs with the tenant's filled in; explicit arguments win. No tenant: unchanged."""
    if tenant is None:
        return checkpoints, graph_kwargs
    return checkpoints or tenant.checkpoints, {**tenant_graph_kwargs(tenant), **graph_kwargs}


def _policy(path: str | None) -> dict[str, str]:
    from governor.build.profile import load_policy

    return load_policy(path) if path else {}


def build_graph(
    llm: BuildLLM,
    checkpointer: Any,
    *,
    profiler: Callable[[str], dict] = default_profiler,
    kpis_path: Path = DEFAULT_KPIS,
    blueprint_path: Path = DEFAULT_BLUEPRINT,
    default_approved: Path | None = DEFAULT_APPROVED,
    today: Callable[[], dt.date] = dt.date.today,
    dbt_runner: silver.Runner = run_dbt,
    inspector: silver.Inspector = silver.built_columns,
    row_counter: gold.RowCounter = gold.kpi_rows,
):
    catalogue = load_kpis(kpis_path)
    blueprint = load_blueprint(blueprint_path)

    def _tid(config: RunnableConfig) -> str:
        return config["configurable"]["thread_id"]

    def _cost(calls: list[dict]) -> float | None:
        costs = [c.get("cost_usd") for c in calls]
        return round(sum(costs), 6) if calls and None not in costs else None

    def profile(state: BuildState, config: RunnableConfig) -> dict:
        prof = state.get("profile") or profiler(state["policy"])
        from governor.build.workspace import sync_sources

        sync_sources(Path(state["target"]), prof)  # every entry point gets sources.yml for the tables just profiled
        emit("profiled", thread_id=_tid(config), tables=len(prof.get("tables") or []),
             relationships=len(prof.get("relationships") or []), saved=bool(state.get("profile")))
        return {} if state.get("profile") else {"profile": prof}

    def compare(state: BuildState, config: RunnableConfig) -> dict:
        """Up to date, drift or neither (batch3.md section 29). No fingerprint: nothing changes (29.3)."""
        target = Path(state["target"])
        doc = _read_json(target_fingerprint(target))
        if doc is None:
            return {}
        current = drift.fingerprint(state["profile"])
        if doc.get("hash") == drift.fingerprint_hash(current):
            last = str(doc.get("thread_id") or "")
            build = _read_json(target / "governor" / "build.json") or {}
            up_to_date = (not state.get("force") and build.get("status") == BUILT and last
                          and build.get("thread_id") == last and (target / "governor" / "design.json").is_file())
            if not up_to_date:
                return {}  # same schema, but the last build did not finish (or force): a full design as before
            write_drift(target, f"No change in the raw schema since build {last[:8]}, "
                                f"approved on {doc.get('approved_on')}.\n")
            emit("up_to_date", thread_id=_tid(config), last_build=last)
            return {"status": UP_TO_DATE, "last_build": last}
        lines = drift.diff(doc.get("fingerprint") or {}, current).summary_lines()
        write_drift(target, "# Drift since the last approved build\n\n" + "".join(f"- {ln}\n" for ln in lines))
        update: dict[str, Any] = {"drift": lines, "note": drift_note(lines)}
        previous = _read_json(target / "governor" / "design.json")
        if previous is not None:
            update["proposal"] = previous  # propose passes it as ``previous`` because the note is set
        return update

    def after_compare(state: BuildState) -> str:
        return END if state.get("status") == UP_TO_DATE else "propose"

    def propose(state: BuildState, config: RunnableConfig) -> dict:
        findings = [Finding.model_validate(f) for f in state.get("findings") or []]
        note = state.get("note")
        previous = state.get("proposal") if (findings or note) else None
        update: dict[str, Any] = {"repairs": state.get("repairs", 0) + (1 if findings else 0)}
        approved = load_approved_context(state["target"], default_approved)
        before = len(llm.calls)
        try:
            proposal = design.propose(state["profile"], catalogue, blueprint, approved, llm, findings or None,
                                      previous=previous, note=note)
            update |= {"proposal": proposal.to_json_dict(), "findings": []}
            counts = {"silver_models": len(proposal.silver_models),
                      "kpis_build": sum(k.decision == "build" for k in proposal.kpis),
                      "kpis_decline": sum(k.decision == "decline" for k in proposal.kpis)}
        except LLMOutputError as exc:
            update |= {"proposal": None, "findings": [Finding(code="PROPOSAL_UNPARSEABLE", subject="proposal",
                                                              problem=str(exc)[:2000]).model_dump()]}
            counts = {"parsed": False}
        update["calls"] = list(llm.calls[before:])
        emit("proposed", thread_id=_tid(config), repair=update["repairs"], note=bool(note), **counts,
             cost_usd=_cost(update["calls"]))
        return update

    def validate(state: BuildState, config: RunnableConfig) -> dict:
        if state.get("proposal") is None:
            emit("validated", thread_id=_tid(config), codes=["PROPOSAL_UNPARSEABLE"], findings=1)
            return {}  # the PROPOSAL_UNPARSEABLE finding from propose stands
        found = design.validate(state["proposal"], state["profile"], catalogue, _policy(state.get("policy")))
        emit("validated", thread_id=_tid(config), codes=sorted({f.code for f in found}), findings=len(found))
        return {"findings": [f.model_dump() for f in found]}

    def after_validate(state: BuildState) -> str:
        if state.get("findings") and state.get("repairs", 0) < MAX_REPAIRS:
            return "propose"
        return "write_report"

    def write_report(state: BuildState, config: RunnableConfig) -> dict:
        thread_id = config["configurable"]["thread_id"]
        findings = state.get("findings") or []
        out = governor_dir(state["target"])
        report = out / "design.md"
        report.write_text(design.render_report(state.get("proposal"), findings, thread_id, drift=state.get("drift")),
                          encoding="utf-8")
        design_file = None
        if not findings:
            # design.json is the proposal that would be approved; an invalid one is never written there
            design_file = out / "design.json"
            design_file.write_text(json.dumps(state["proposal"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        status = INVALID if findings else AWAITING
        # emitted here, not in design_gate: that node runs again from its start when the thread resumes
        emit("design_gate", thread_id=thread_id, status=status, report="governor/design.md",
             codes=sorted({f["code"] for f in findings}), cost_usd=_cost(list(state.get("calls") or [])))
        return {"status": status, "report": str(report), "design": str(design_file) if design_file else None}

    def after_report(state: BuildState) -> str:
        return END if state.get("status") == INVALID else "design_gate"

    def design_gate(state: BuildState, config: RunnableConfig) -> dict:
        decision = interrupt({"thread_id": config["configurable"]["thread_id"], "status": AWAITING,
                              "report": state.get("report")})
        action = (decision or {}).get("action") if isinstance(decision, dict) else None
        if action == "approve":
            emit("approved", thread_id=_tid(config), by=str(decision["by"]))
            return {"status": "approving", "approved_by": str(decision["by"])}
        if action == "reject":
            note = str(decision.get("note") or "").strip()
            final = state.get("rejections", 0) >= MAX_REJECTIONS
            emit("rejected", thread_id=_tid(config), rejections=state.get("rejections", 0) + 1,
                 status=REJECTED if final else "rejected")
            if final:
                return {"status": REJECTED, "note": note}
            return {"status": "rejected", "note": note, "rejections": state.get("rejections", 0) + 1,
                    "findings": [], "repairs": 0}
        raise BuildError(f"the design gate needs approve or reject, got {decision!r}")

    def after_gate(state: BuildState) -> str:
        return {"approving": "record_decisions", "rejected": "propose"}.get(state.get("status") or "", END)

    def record(state: BuildState, config: RunnableConfig) -> dict:
        path = record_decisions(state["target"], Proposal.model_validate(state["proposal"]), state["approved_by"],
                                today(), config["configurable"]["thread_id"])
        if state.get("profile"):
            write_fingerprint(state["target"], state["profile"], today(), config["configurable"]["thread_id"])
        return {"status": APPROVED, "approved_file": str(path)}

    def _silver_update(st: dict, before: int) -> dict:
        out = {"silver": st, "sql_repairs": int(st.get("repairs") or 0), "calls": list(llm.calls[before:])}
        if st.get("status") in (silver.BUILT, silver.ESCALATED):
            out["status"] = st["status"]
        return out

    def write_silver(state: BuildState) -> dict:
        before = len(llm.calls)
        described = docs.describe(state["proposal"], state.get("profile"), catalogue, _policy(state.get("policy")), llm)
        st = silver.write_silver(state["target"], state["proposal"], llm, docs=described)
        return {**_silver_update(st, before), "docs": described}

    def dbt_build_silver(state: BuildState) -> dict:
        st = silver.dbt_build_silver(state["target"], state["proposal"], dict(state["silver"]),
                                     runner=dbt_runner, inspector=inspector)
        return _silver_update(st, len(llm.calls))

    def repair_silver(state: BuildState, config: RunnableConfig) -> dict:
        before = len(llm.calls)
        failing = sorted((state.get("silver") or {}).get("failures") or {})
        st = silver.repair_silver(state["target"], state["proposal"], llm, dict(state["silver"]))
        update = _silver_update(st, before)
        emit("repair", thread_id=_tid(config), models=failing, repairs=int(st.get("repairs") or 0),
             cost_usd=_cost(update["calls"]))
        return update

    def after_silver(state: BuildState) -> Any:
        st = dict(state["silver"])
        step = silver.next_step(st)
        if step == "dbt":
            return "dbt_build_silver"
        if step == "repair":
            return "repair_silver"
        return "silver_done"

    def silver_done(state: BuildState, config: RunnableConfig) -> dict:
        st = dict(state["silver"])
        silver.next_step(st)  # sets the escalation (model and last error) when a model is out of repairs
        status = st.get("status") or silver.ESCALATED
        if status == silver.BUILT:
            emit("silver_built", thread_id=_tid(config), models=len(st.get("models") or []),
                 tests_passed=int(st.get("tests_passed") or 0), repairs=int(st.get("repairs") or 0))
        else:
            emit("escalated", thread_id=_tid(config), stage="silver",
                 model=(st.get("escalated") or {}).get("model"), repairs=int(st.get("repairs") or 0))
        return {"silver": st, "status": status}

    def after_silver_done(state: BuildState) -> str:
        return "write_gold" if state.get("status") == silver.BUILT else END

    def write_gold(state: BuildState) -> dict:
        target, proposal = state["target"], state["proposal"]
        files = gold.write_gold(target, proposal, catalogue, docs=state.get("docs"))
        gaps_file = gold.write_gaps(target, proposal)
        found = gold.check_project(target, catalogue, _policy(state.get("policy")), blueprint=blueprint)
        st = {"files": [Path(f).relative_to(target).as_posix() for f in files],
              "gaps_file": str(gaps_file), "models": [], "tests_passed": 0}
        update: dict[str, Any] = {"gold": st, "blueprint": [f.model_dump() for f in found]}
        if gold.high(found):
            update["status"] = gold.BLUEPRINT_FAILED
        return update

    def after_write_gold(state: BuildState) -> str:
        return "summarise" if state.get("status") == gold.BLUEPRINT_FAILED else "dbt_build_gold"

    def dbt_build_gold(state: BuildState, config: RunnableConfig) -> dict:
        res = gold.dbt_build_gold(state["target"], state["proposal"], runner=dbt_runner)
        st = {**dict(state.get("gold") or {}), **res}
        if res["status"] == gold.BUILT:
            emit("gold_built", thread_id=_tid(config), models=len(res.get("models") or []),
                 tests_passed=int(res.get("tests_passed") or 0))
        if res["status"] == gold.BUILT:
            try:
                st["rows"] = row_counter(res["models"])
            except Exception as exc:  # noqa: BLE001
                st["rows"] = {}
                st["rows_error"] = f"{type(exc).__name__}: {str(exc).splitlines()[0] if str(exc) else ''}"
        return {"gold": st, "status": res["status"]}

    def summarise(state: BuildState, config: RunnableConfig) -> dict:
        st = dict(state.get("gold") or {})
        summary = gold.summarise(state["target"], state["proposal"], status=state["status"],
                                 silver_state=dict(state.get("silver") or {}), gold_state=st,
                                 findings=list(state.get("blueprint") or []), calls=list(state.get("calls") or []),
                                 sql_repairs=int(state.get("sql_repairs") or 0), rows=st.get("rows"),
                                 thread_id=config["configurable"]["thread_id"],
                                 approved_by=state.get("approved_by"))
        status = state["status"]
        info = {"thread_id": _tid(config), "status": status, "kpis_built": len(summary["kpis_built"]),
                "gaps": [g["id"] for g in summary["gaps"]], "tests_passed": summary["tests_passed"]["total"],
                "cost_usd": summary["cost"]["cost_usd"]}
        if status == BUILT:
            emit("built", **info)
        else:
            emit("escalated", stage="gold", model=(st.get("escalated") or {}).get("model"),
                 blueprint_findings=len(state.get("blueprint") or []), **info)
        return {"summary": summary}

    g = StateGraph(BuildState)
    g.add_node("profile", profile)
    g.add_node("compare", compare)
    g.add_node("propose", propose)
    g.add_node("validate", validate)
    g.add_node("write_report", write_report)
    g.add_node("design_gate", design_gate)
    g.add_node("record_decisions", record)
    g.add_node("write_silver", write_silver)
    g.add_node("dbt_build_silver", dbt_build_silver)
    g.add_node("repair_silver", repair_silver)
    g.add_node("silver_done", silver_done)
    g.add_node("write_gold", write_gold)
    g.add_node("dbt_build_gold", dbt_build_gold)
    g.add_node("summarise", summarise)
    g.add_edge(START, "profile")
    g.add_edge("profile", "compare")
    g.add_conditional_edges("compare", after_compare, ["propose", END])
    g.add_edge("propose", "validate")
    g.add_conditional_edges("validate", after_validate, ["propose", "write_report"])
    g.add_conditional_edges("write_report", after_report, ["design_gate", END])
    g.add_conditional_edges("design_gate", after_gate, ["record_decisions", "propose", END])
    g.add_edge("record_decisions", "write_silver")
    routes = ["dbt_build_silver", "repair_silver", "silver_done"]
    for node in ("write_silver", "dbt_build_silver", "repair_silver"):
        g.add_conditional_edges(node, after_silver, routes)
    g.add_conditional_edges("silver_done", after_silver_done, ["write_gold", END])
    g.add_conditional_edges("write_gold", after_write_gold, ["dbt_build_gold", "summarise"])
    g.add_edge("dbt_build_gold", "summarise")
    g.add_edge("summarise", END)
    return g.compile(checkpointer=checkpointer)


# --------------------------------------------------------------------------- checkpoints and commands


def state_dir() -> Path:
    raw = os.environ.get("GOVERNOR_STATE_DIR")
    return paths.ROOT / raw if raw else paths.STATE


@contextmanager
def open_checkpointer(path: str | Path | None = None) -> Iterator[SqliteSaver]:
    target = Path(path) if path else state_dir() / CHECKPOINT_FILE
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target), check_same_thread=False)
    try:
        yield SqliteSaver(conn)
    finally:
        conn.close()


def _summary(graph, config: dict) -> dict:
    values = graph.get_state(config).values or {}
    out = {"thread_id": config["configurable"]["thread_id"], "status": values.get("status"),
           "report": values.get("report")}
    if values.get("status") == INVALID:
        out["findings"] = sorted({f["code"] for f in values.get("findings") or []})
    if values.get("approved_file"):
        out["approved"] = values.get("approved_file")
    if values.get("status") == UP_TO_DATE:
        out["last_build"] = values.get("last_build")
        out["drift_report"] = str(Path(values["target"]) / "governor" / "drift.md")
    elif values.get("drift") is not None:
        out["drift"] = list(values["drift"])
    status = values.get("status")
    if status in (silver.BUILT, BUILT, ESCALATED, BLUEPRINT_FAILED):
        sv = silver.result(values.get("silver") or {}).to_dict()
        gd = values.get("gold") or {}
        out.update(sv)
        out["status"] = status
        out["models"] = list(sv.get("models") or []) + list(gd.get("models") or [])
        out["tests_passed"] = int(sv.get("tests_passed") or 0) + int(gd.get("tests_passed") or 0)
        out["repairs"] = int(values.get("sql_repairs") or 0)
        proposal = values.get("proposal")
        out["kpis_built"] = [k.id for k in gold.built_kpis(proposal)] if status == BUILT and proposal else []
        out["gaps"] = [g["id"] for g in gold.gaps(proposal)] if proposal else []
        if gd.get("escalated"):
            out["escalated"] = gd["escalated"]
        if values.get("blueprint") is not None:
            out["blueprint"] = values.get("blueprint")
        if values.get("summary"):
            out["build"] = str(Path(values["target"]) / "governor" / "build.json")
    calls = values.get("calls") or []
    costs = [c.get("cost_usd") for c in calls]
    out["llm_calls"] = len(calls)
    out["cost_usd"] = round(sum(costs), 6) if calls and None not in costs else None
    return out


def start(target: str | Path, project_name: str, llm: BuildLLM, *, policy: str | Path | None = DEFAULT_POLICY,
          profile: dict | None = None, thread_id: str | None = None, checkpoints: str | Path | None = None,
          force: bool = False, tenant: Tenant | None = None, **graph_kwargs: Any) -> dict:
    """Run a new build thread to the design gate (or to design_invalid, or ``up_to_date`` when nothing changed since
    the last approved build). ``profile`` skips profiling raw; ``force`` skips only the up-to-date check.

    ``tenant`` (batch3.md section 31.2): the tenant's knowledge, checkpoints, database and dbt env; the default
    policy becomes the tenant's, and ``target`` must be the tenant's target."""
    if tenant is not None:
        if Path(target).resolve() != Path(tenant.target).resolve():
            raise BuildError(f"target {target} is not the target of tenant {tenant.name}")
        if policy is not None and Path(policy) == DEFAULT_POLICY:
            policy = tenant.policy_path
    checkpoints, graph_kwargs = _for_tenant(tenant, checkpoints, graph_kwargs)
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state: dict[str, Any] = {"target": str(Path(target).resolve()), "project_name": project_name,
                             "policy": str(policy) if policy else "", "repairs": 0, "rejections": 0, "calls": [],
                             "force": bool(force)}
    if profile is not None:
        state["profile"] = profile
    emit("run_started", thread_id=thread_id, project=project_name, saved_profile=profile is not None)
    with open_checkpointer(checkpoints) as saver:
        graph = build_graph(llm, saver, **graph_kwargs)
        graph.invoke(state, config)
        return _summary(graph, config)


def _resume(thread_id: str, decision: dict, llm: BuildLLM, checkpoints: str | Path | None, **graph_kwargs: Any) -> dict:
    config = {"configurable": {"thread_id": thread_id}}
    with open_checkpointer(checkpoints) as saver:
        graph = build_graph(llm, saver, **graph_kwargs)
        pending = graph.get_state(config)
        if not pending.values:
            raise BuildError(f"unknown build thread {thread_id}")
        if "design_gate" not in (pending.next or ()):
            raise BuildError(f"thread {thread_id} is not waiting at the design gate "
                             f"(status {pending.values.get('status')})")
        graph.invoke(Command(resume=decision), config)
        return _summary(graph, config)


def approve(thread_id: str, by: str, llm: BuildLLM, *, checkpoints: str | Path | None = None,
            tenant: Tenant | None = None, **graph_kwargs: Any) -> dict:
    if not (by or "").strip():
        raise BuildError("approve needs --by <name>")
    checkpoints, graph_kwargs = _for_tenant(tenant, checkpoints, graph_kwargs)
    return _resume(thread_id, {"action": "approve", "by": by.strip()}, llm, checkpoints, **graph_kwargs)


def reject(thread_id: str, note: str, llm: BuildLLM, *, checkpoints: str | Path | None = None,
           tenant: Tenant | None = None, **graph_kwargs: Any) -> dict:
    if not (note or "").strip():
        raise BuildError("reject needs --note \"<what to change>\"")
    checkpoints, graph_kwargs = _for_tenant(tenant, checkpoints, graph_kwargs)
    return _resume(thread_id, {"action": "reject", "note": note.strip()}, llm, checkpoints, **graph_kwargs)


SILVER_BUILT = silver.BUILT
BUILT, ESCALATED, BLUEPRINT_FAILED = gold.BUILT, gold.ESCALATED, gold.BLUEPRINT_FAILED

__all__ = ["APPROVED", "AWAITING", "BLUEPRINT_FAILED", "BUILT", "ESCALATED", "SILVER_BUILT", "INVALID", "REJECTED", "UP_TO_DATE", "BuildError",
           "approve", "build_graph", "drift_note", "record_decisions", "reject", "start", "target_fingerprint",
           "tenant_graph_kwargs", "tenant_profiler", "write_fingerprint"]
