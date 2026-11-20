"""Node specs and topology for the build and ask graphs (batch4.md section 35).

``topology`` compiles a graph with a fake model and no checkpointer, so it never
touches the network or a database. Build and ask stay unimported until a caller
asks for that graph.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["guard", "llm", "check", "dbt", "gate", "io", "summary"]
Group = Literal["design", "silver", "gold", "understand", "sql", "answer"]


class NodeSpec(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: str
    label: str
    kind: Kind
    description: str = Field(max_length=100)
    group: Group
    order: int
    planned: bool = False


def _spec(id: str, label: str, kind: Kind, description: str, group: Group, order: int) -> NodeSpec:
    return NodeSpec(id=id, label=label, kind=kind, description=description, group=group, order=order)


BUILD_NODES: tuple[NodeSpec, ...] = (
    _spec("profile", "Profile", "io", "Reads the raw schema: table, column and PII counts.", "design", 1),
    _spec("compare", "Compare", "check", "Checks the schema fingerprint against the last approved build.", "design", 2),
    _spec("propose", "Propose", "llm", "Asks the model for silver models and KPI mappings.", "design", 3),
    _spec("validate", "Validate", "check", "Checks the proposal and lists finding codes.", "design", 4),
    _spec("write_report", "Report", "io", "Writes the design report for the approval gate.", "design", 5),
    _spec("design_gate", "Design gate", "gate", "Waits for a person to approve or reject the design.", "design", 6),
    _spec("record_decisions", "Record", "io", "Records the approved KPI mappings.", "design", 7),
    _spec("write_silver", "Write silver", "llm", "Writes staging and intermediate models.", "silver", 8),
    _spec("dbt_build_silver", "Build silver", "dbt", "Builds and tests the silver models.", "silver", 9),
    _spec("repair_silver", "Repair silver", "llm", "Asks the model to repair a failing silver model.", "silver", 10),
    _spec("silver_done", "Silver done", "check", "Records whether silver built or escalated.", "silver", 11),
    _spec("write_gold", "Write gold", "io", "Writes gold KPI models and the gap list.", "gold", 12),
    _spec("dbt_build_gold", "Build gold", "dbt", "Builds and tests the gold KPI models.", "gold", 13),
    _spec("summarise", "Summary", "summary", "Writes the build summary: status and cost.", "gold", 14),
)

START = _spec("start", "Start", "io", "Where a build run begins.", "design", 0)
END = _spec("end", "End", "io", "Where a build run ends.", "gold", 100)

# Conditional edges of the compiled build graph, in plain words. Keys use the
# compiled ids (``__end__``); ``topology`` publishes them as ``end``.
BUILD_EDGES: dict[tuple[str, str], str] = {
    ("compare", "__end__"): "up to date",
    ("compare", "propose"): "changed or new",
    ("validate", "propose"): "findings: repair",
    ("validate", "write_report"): "ok",
    ("write_report", "design_gate"): "awaiting approval",
    ("write_report", "__end__"): "design invalid",
    ("design_gate", "record_decisions"): "approved",
    ("design_gate", "propose"): "rejected",
    ("design_gate", "__end__"): "rejected again",
    ("write_silver", "dbt_build_silver"): "sql ok",
    ("write_silver", "repair_silver"): "sql refused",
    ("write_silver", "silver_done"): "escalated",
    ("dbt_build_silver", "dbt_build_silver"): "more models",
    ("dbt_build_silver", "repair_silver"): "test failed",
    ("dbt_build_silver", "silver_done"): "silver finished",
    ("repair_silver", "dbt_build_silver"): "repaired",
    ("repair_silver", "repair_silver"): "still failing",
    ("repair_silver", "silver_done"): "escalated",
    ("silver_done", "write_gold"): "silver built",
    ("silver_done", "__end__"): "escalated",
    ("write_gold", "dbt_build_gold"): "ok",
    ("write_gold", "summarise"): "blueprint failed",
}

ASK_NODES: tuple[NodeSpec, ...] = (
    _spec("guard", "Guard", "guard", "Stops a question that is not about the billing data.", "understand", 1),
    _spec("retrieve_context", "Retrieve", "io", "Finds catalog cards for the tables and metrics.", "understand", 2),
    _spec("plan", "Plan", "llm", "Asks the model what the question is asking for.", "understand", 3),
    _spec("clarify", "Clarify", "gate", "Waits for a person to fill in a missing detail.", "understand", 4),
    _spec("draft_sql", "Draft SQL", "llm", "Asks the model to draft a query.", "sql", 5),
    _spec("validate", "Validate", "check", "Checks the query against the access policy.", "sql", 6),
    _spec("dry_run", "Dry run", "check", "Checks the query with the warehouse planner.", "sql", 7),
    _spec("repair", "Repair", "llm", "Asks the model to repair a refused query.", "sql", 8),
    _spec("execute", "Execute", "io", "Runs the checked query and counts the rows.", "sql", 9),
    _spec("answer", "Answer", "llm", "Asks the model to word the answer.", "answer", 10),
    _spec("record_trace", "Record", "io", "Saves the decision trace for this question.", "answer", 11),
)

ASK_START = _spec("start", "Start", "io", "Where an ask run begins.", "understand", 0)
ASK_END = _spec("end", "End", "io", "Where an ask run ends.", "answer", 100)

# Conditional edges of the compiled ask graph, in plain words.
ASK_EDGES: dict[tuple[str, str], str] = {
    ("guard", "retrieve_context"): "ok",
    ("guard", "record_trace"): "blocked",
    ("plan", "clarify"): "unclear",
    ("plan", "draft_sql"): "ready",
    ("plan", "record_trace"): "refused",
    ("clarify", "plan"): "answered",
    ("clarify", "record_trace"): "blocked",
    ("validate", "dry_run"): "ok",
    ("validate", "repair"): "refused: repair",
    ("validate", "record_trace"): "refused",
    ("dry_run", "execute"): "ok",
    ("dry_run", "repair"): "failed: repair",
    ("dry_run", "record_trace"): "refused",
    ("execute", "answer"): "ok",
    ("execute", "repair"): "failed: repair",
    ("execute", "record_trace"): "refused",
}


def _public(node_id: str) -> str:
    return {"__start__": "start", "__end__": "end"}.get(node_id, node_id)


def _drawn(graph: str, specs: tuple[NodeSpec, ...] | list[NodeSpec], labels: dict[tuple[str, str], str], drawable) -> dict:
    edges = [{"source": _public(edge.source), "target": _public(edge.target),
              "label": labels.get((edge.source, edge.target), ""),
              "conditional": bool(edge.conditional)}
             for edge in drawable.edges]
    return {"graph": graph, "nodes": [spec.model_dump() for spec in specs], "edges": edges}


def topology(graph: str) -> dict:
    """``{graph, nodes, edges}`` for a compiled graph. Fake model, no checkpointer, no database."""
    if graph == "build":
        from governor.build.graph import build_graph
        from governor.build.llm import FakeBuildLLM

        return _drawn("build", [START, *BUILD_NODES, END], BUILD_EDGES, build_graph(FakeBuildLLM({}), None).get_graph())
    if graph == "ask":
        from governor.ask.graph import build_graph
        from governor.ask.llm_testing import FakeLLM

        drawable = build_graph(llm=FakeLLM(), checkpointer=None).get_graph()
        return _drawn("ask", [ASK_START, *ASK_NODES, ASK_END], ASK_EDGES, drawable)
    raise KeyError(graph)
