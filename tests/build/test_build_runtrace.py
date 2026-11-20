"""Build graph tracing: registry, a full offline run, and events that stay put (batch4.md section 35)."""
import json
from pathlib import Path

from governor.build import graph, gold
from governor.build.dbt import DbtResult
from governor.build.llm import FakeBuildLLM
from governor.build.models import Proposal
from governor.core.runtrace import RunLog, topology
from governor.core.runtrace.registry import BUILD_NODES

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "build"
SILVER = json.loads((FIXTURES / "sample_silver.json").read_text(encoding="utf-8"))
GOOD_SILVER = {**SILVER["intermediate"], "int_order_lines": SILVER["repair"]["int_order_lines"]}
MARKER = "ZZMARKER_7781"
APPROVER = "APPROVER_TOKEN_9f3c"


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _start(tmp_path, profile, replies, **kw):
    llm = FakeBuildLLM({"propose": [json.dumps(r) if isinstance(r, dict) else r for r in replies]})
    out = graph.start(tmp_path / "target", "shop", llm, profile=profile,
                      checkpoints=tmp_path / "state" / graph.CHECKPOINT_FILE, **kw)
    return out, llm


class _FakeDbt:
    """Silver and gold succeed; every test passes. Same shape as the gold-graph fake."""

    def __init__(self, design):
        self.design = Proposal.model_validate(design)

    def __call__(self, target, args):
        if "marts" in args:
            names = [gold.model_name(k.id) for k in gold.built_kpis(self.design)]
            res = [{"unique_id": f"model.shop.{n}", "status": "success", "message": "SELECT 3"} for n in names]
            res += [{"unique_id": f"test.shop.not_null_{n}_month.abc", "status": "pass", "message": None}
                    for n in names if n != "kpi_repeat_purchase_rate"]
        else:
            res = [{"unique_id": f"model.shop.{m.name}", "status": "success", "message": "OK"}
                   for m in self.design.silver_models]
            res += [{"unique_id": f"test.shop.unique_{m.name}_x.abc", "status": "pass", "message": None}
                    for m in self.design.silver_models]
        return DbtResult(True, 0, res, "")

    def columns(self, names):
        return {m.name: m.column_names() for m in self.design.silver_models}


def test_build_registry_matches_graph():
    compiled = build_nodes()
    registered = {spec.id for spec in BUILD_NODES if not spec.planned}
    assert registered == compiled
    assert all(len(spec.description) <= 100 for spec in BUILD_NODES)


def test_build_conditional_edges_labelled():
    drawn = topology("build")
    labels = {(edge["source"], edge["target"]): edge["label"] for edge in drawn["edges"]}
    assert labels[("compare", "end")] == "up to date"
    assert labels[("validate", "propose")] == "findings: repair"
    assert labels[("design_gate", "propose")] == "rejected"
    assert labels[("dbt_build_silver", "repair_silver")] == "test failed"
    assert labels[("silver_done", "end")] == "escalated"
    missing = [edge for edge in drawn["edges"] if edge["conditional"] and not edge["label"]]
    assert missing == []


def build_nodes() -> set[str]:
    compiled = graph.build_graph(FakeBuildLLM({}), None).get_graph()
    return {node for node in compiled.nodes if node not in ("__start__", "__end__")}


def test_build_run_log_full_run(tmp_path, profile, good):
    dbt = _FakeDbt(good)
    kw = {"checkpoints": tmp_path / "cp.sqlite", "dbt_runner": dbt, "inspector": dbt.columns,
          "row_counter": lambda names: {n: 3 for n in names}}
    out = graph.start(tmp_path / "t", "shop", FakeBuildLLM({"propose": [json.dumps(good)]}), profile=profile, **kw)
    paused = _events(RunLog("build", out["thread_id"]).path)
    assert paused[0]["type"] == "run_started"
    assert "run_finished" not in [row["type"] for row in paused]
    gate = [row for row in paused if row["type"] == "run_paused"]
    assert len(gate) == 1 and gate[0]["node"] == "design_gate" and gate[0]["status"] == "awaiting_approval"
    assert [row["attempt"] for row in paused if row["type"] == "node_started" and row["node"] == "design_gate"] == [1]

    done_summary = graph.approve(out["thread_id"], APPROVER, FakeBuildLLM({"intermediate": GOOD_SILVER}), **kw)
    assert done_summary["status"] == "built"
    path = RunLog("build", out["thread_id"]).path
    done = _events(path)
    assert [row["type"] for row in done if row["type"] in ("run_started", "run_paused", "run_resumed", "run_finished")] == [
        "run_started", "run_paused", "run_resumed", "run_finished"]
    assert done[-1]["type"] == "run_finished" and done[-1]["status"] == "built"
    assert [row["attempt"] for row in done if row["type"] == "node_started" and row["node"] == "design_gate"] == [1, 2]
    finished = [row for row in done if row["type"] == "node_finished"]
    assert finished and all(isinstance(row["summary"], str) and 0 < len(row["summary"]) <= 80 for row in finished)
    assert any(row["node"] == "design_gate" and "approved" in row["summary"] for row in finished)
    assert any(row["node"] == "write_silver" for row in finished)
    assert any(row["node"] == "write_gold" for row in finished)
    text = path.read_text(encoding="utf-8")
    assert APPROVER not in text


def test_build_run_log_has_no_data_values(tmp_path, profile, good):
    for table in profile["tables"]:
        for column in table["columns"]:
            column["min"] = MARKER
            column["max"] = MARKER
    out, _ = _start(tmp_path, profile, [good])
    path = RunLog("build", out["thread_id"]).path
    text = path.read_text(encoding="utf-8")
    assert MARKER not in text
    assert any(row["type"] == "node_finished" and row["node"] == "profile" for row in _events(path))


def test_build_events_unchanged(tmp_path, profile, good, monkeypatch):
    monkeypatch.setenv("GOVERNOR_RUNTRACE", "0")
    off, _ = _start(tmp_path, profile, [good])
    monkeypatch.setenv("GOVERNOR_RUNTRACE", "1")
    on, _ = _start(tmp_path, profile, [good])

    def kinds(thread_id: str) -> list[str]:
        path = tmp_path / "state" / "events.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        return [row["kind"] for row in rows if row["thread_id"] == thread_id]

    assert kinds(on["thread_id"]) == kinds(off["thread_id"])
    assert not RunLog("build", off["thread_id"]).path.exists()
    assert RunLog("build", on["thread_id"]).path.is_file()
