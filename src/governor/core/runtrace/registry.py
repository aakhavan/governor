"""Node specs and the build topology (batch4.md section 35).

``topology`` compiles the build graph with a fake model and no checkpointer, so it
never touches the network or a database. Ask nodes arrive in a later step.
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


def _public(node_id: str) -> str:
    return {"__start__": "start", "__end__": "end"}.get(node_id, node_id)


def topology(graph: str) -> dict:
    """``{graph, nodes, edges}`` for a compiled graph. Only ``build`` exists in this step."""
    if graph != "build":
        raise KeyError(graph)
    from governor.build.graph import build_graph
    from governor.build.llm import FakeBuildLLM

    drawable = build_graph(FakeBuildLLM({}), None).get_graph()
    nodes = [spec.model_dump() for spec in (START, *BUILD_NODES, END)]
    edges = [{"source": _public(edge.source), "target": _public(edge.target),
              "label": BUILD_EDGES.get((edge.source, edge.target), ""),
              "conditional": bool(edge.conditional)}
             for edge in drawable.edges]
    return {"graph": "build", "nodes": nodes, "edges": edges}
