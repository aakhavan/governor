"""The build ``StateGraph`` (batch2.md section 8), D3 and D4 parts: profile to the design gate, then silver.

::

    profile -> propose -> validate --findings, at most 2 repairs--> propose
                             | ok (or repairs used up: write_report, then status design_invalid)
                        write_report -> design_gate (interrupt)
             reject + note (once) <------|  approve
             -> propose                  v
                                    record_decisions -> write_silver --SQL refused--> repair_silver
                                                             | ok                          ^   |
                                                       dbt_build_silver --fail-------------+   |
                                                             | ok          (write model <= 2, then plan model once)
                                                            END (silver_built)      out of repairs -> END (escalated)

Code owns every edge. Checkpoints live in ``GOVERNOR_STATE_DIR/build_checkpoints.sqlite``, so ``approve`` and
``reject`` resume the thread from a new process. The state holds the profile (no data values for PII columns), the
proposal and the findings; no raw rows.

``approve`` resumes the thread at the gate and runs on to ``silver_built`` or ``escalated`` in the same call. The
silver step state (SQL per model, failures, repairs per model) is kept under ``silver``; ``sql_repairs`` counts
repair calls (``repairs`` stays the design-loop count).

A rejection sends the design back once, with the note, for one more proposal round (that round has its own repair
budget). A second rejection ends the thread with status ``design_rejected``.
"""

from __future__ import annotations

import datetime as dt
import json
import operator
import os
import sqlite3
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Annotated, Any, Callable, Iterator, TypedDict

import yaml
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from governor.build import design, silver
from governor.build.dbt import run_dbt
from governor.build.llm import BuildLLM, LLMOutputError
from governor.build.models import Finding, Proposal
from governor.core import paths
from governor.core.catalogue import load_approved, load_blueprint, load_kpis

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
    sql_repairs: int
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


# --------------------------------------------------------------------------- graph


def default_profiler(policy_path: str) -> dict:
    from governor.build.profile import load_policy, profile_schema
    from governor.build.workspace import build_dsn

    return profile_schema(build_dsn(), "raw", load_policy(policy_path))


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
):
    catalogue = load_kpis(kpis_path)
    blueprint = load_blueprint(blueprint_path)

    def profile(state: BuildState) -> dict:
        if state.get("profile"):
            return {}
        return {"profile": profiler(state["policy"])}

    def propose(state: BuildState) -> dict:
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
        except LLMOutputError as exc:
            update |= {"proposal": None, "findings": [Finding(code="PROPOSAL_UNPARSEABLE", subject="proposal",
                                                              problem=str(exc)[:2000]).model_dump()]}
        update["calls"] = list(llm.calls[before:])
        return update

    def validate(state: BuildState) -> dict:
        if state.get("proposal") is None:
            return {}  # the PROPOSAL_UNPARSEABLE finding from propose stands
        found = design.validate(state["proposal"], state["profile"], catalogue, _policy(state.get("policy")))
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
        report.write_text(design.render_report(state.get("proposal"), findings, thread_id), encoding="utf-8")
        design_file = None
        if not findings:
            # design.json is the proposal that would be approved; an invalid one is never written there
            design_file = out / "design.json"
            design_file.write_text(json.dumps(state["proposal"], indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return {"status": INVALID if findings else AWAITING, "report": str(report),
                "design": str(design_file) if design_file else None}

    def after_report(state: BuildState) -> str:
        return END if state.get("status") == INVALID else "design_gate"

    def design_gate(state: BuildState, config: RunnableConfig) -> dict:
        decision = interrupt({"thread_id": config["configurable"]["thread_id"], "status": AWAITING,
                              "report": state.get("report")})
        action = (decision or {}).get("action") if isinstance(decision, dict) else None
        if action == "approve":
            return {"status": "approving", "approved_by": str(decision["by"])}
        if action == "reject":
            note = str(decision.get("note") or "").strip()
            if state.get("rejections", 0) >= MAX_REJECTIONS:
                return {"status": REJECTED, "note": note}
            return {"status": "rejected", "note": note, "rejections": state.get("rejections", 0) + 1,
                    "findings": [], "repairs": 0}
        raise BuildError(f"the design gate needs approve or reject, got {decision!r}")

    def after_gate(state: BuildState) -> str:
        return {"approving": "record_decisions", "rejected": "propose"}.get(state.get("status") or "", END)

    def record(state: BuildState, config: RunnableConfig) -> dict:
        path = record_decisions(state["target"], Proposal.model_validate(state["proposal"]), state["approved_by"],
                                today(), config["configurable"]["thread_id"])
        return {"status": APPROVED, "approved_file": str(path)}

    def _silver_update(st: dict, before: int) -> dict:
        out = {"silver": st, "sql_repairs": int(st.get("repairs") or 0), "calls": list(llm.calls[before:])}
        if st.get("status") in (silver.BUILT, silver.ESCALATED):
            out["status"] = st["status"]
        return out

    def write_silver(state: BuildState) -> dict:
        before = len(llm.calls)
        st = silver.write_silver(state["target"], state["proposal"], llm)
        return _silver_update(st, before)

    def dbt_build_silver(state: BuildState) -> dict:
        st = silver.dbt_build_silver(state["target"], state["proposal"], dict(state["silver"]),
                                     runner=dbt_runner, inspector=inspector)
        return _silver_update(st, len(llm.calls))

    def repair_silver(state: BuildState) -> dict:
        before = len(llm.calls)
        st = silver.repair_silver(state["target"], state["proposal"], llm, dict(state["silver"]))
        return _silver_update(st, before)

    def after_silver(state: BuildState) -> Any:
        st = dict(state["silver"])
        step = silver.next_step(st)
        if step == "dbt":
            return "dbt_build_silver"
        if step == "repair":
            return "repair_silver"
        return "silver_done"

    def silver_done(state: BuildState) -> dict:
        st = dict(state["silver"])
        silver.next_step(st)  # sets the escalation (model and last error) when a model is out of repairs
        return {"silver": st, "status": st.get("status") or silver.ESCALATED}

    g = StateGraph(BuildState)
    g.add_node("profile", profile)
    g.add_node("propose", propose)
    g.add_node("validate", validate)
    g.add_node("write_report", write_report)
    g.add_node("design_gate", design_gate)
    g.add_node("record_decisions", record)
    g.add_node("write_silver", write_silver)
    g.add_node("dbt_build_silver", dbt_build_silver)
    g.add_node("repair_silver", repair_silver)
    g.add_node("silver_done", silver_done)
    g.add_edge(START, "profile")
    g.add_edge("profile", "propose")
    g.add_edge("propose", "validate")
    g.add_conditional_edges("validate", after_validate, ["propose", "write_report"])
    g.add_conditional_edges("write_report", after_report, ["design_gate", END])
    g.add_conditional_edges("design_gate", after_gate, ["record_decisions", "propose", END])
    g.add_edge("record_decisions", "write_silver")
    routes = ["dbt_build_silver", "repair_silver", "silver_done"]
    for node in ("write_silver", "dbt_build_silver", "repair_silver"):
        g.add_conditional_edges(node, after_silver, routes)
    g.add_edge("silver_done", END)
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
    if values.get("status") in (silver.BUILT, silver.ESCALATED):
        out.update(silver.result(values.get("silver") or {}).to_dict())
        out["repairs"] = int(values.get("sql_repairs") or 0)
    calls = values.get("calls") or []
    costs = [c.get("cost_usd") for c in calls]
    out["llm_calls"] = len(calls)
    out["cost_usd"] = round(sum(costs), 6) if calls and None not in costs else None
    return out


def start(target: str | Path, project_name: str, llm: BuildLLM, *, policy: str | Path | None = DEFAULT_POLICY,
          profile: dict | None = None, thread_id: str | None = None, checkpoints: str | Path | None = None,
          **graph_kwargs: Any) -> dict:
    """Run a new build thread to the design gate (or to design_invalid). ``profile`` skips profiling raw."""
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    state: dict[str, Any] = {"target": str(Path(target).resolve()), "project_name": project_name,
                             "policy": str(policy) if policy else "", "repairs": 0, "rejections": 0, "calls": []}
    if profile is not None:
        state["profile"] = profile
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


def approve(thread_id: str, by: str, llm: BuildLLM, *, checkpoints: str | Path | None = None, **graph_kwargs: Any) -> dict:
    if not (by or "").strip():
        raise BuildError("approve needs --by <name>")
    return _resume(thread_id, {"action": "approve", "by": by.strip()}, llm, checkpoints, **graph_kwargs)


def reject(thread_id: str, note: str, llm: BuildLLM, *, checkpoints: str | Path | None = None, **graph_kwargs: Any) -> dict:
    if not (note or "").strip():
        raise BuildError("reject needs --note \"<what to change>\"")
    return _resume(thread_id, {"action": "reject", "note": note.strip()}, llm, checkpoints, **graph_kwargs)


BUILT, ESCALATED = silver.BUILT, silver.ESCALATED

__all__ = ["APPROVED", "AWAITING", "BUILT", "ESCALATED", "INVALID", "REJECTED", "BuildError", "approve",
           "build_graph", "record_decisions", "reject", "start"]
