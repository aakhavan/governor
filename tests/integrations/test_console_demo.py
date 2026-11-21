"""Shipped demo runs and the Studio graphs (batch4.md section 36). Offline."""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

from governor.core.runtrace.fold import fold
from governor.core.runtrace.registry import ASK_NODES, BUILD_NODES

ROOT = Path(__file__).resolve().parents[2]
DEMO = ROOT / "src" / "governor" / "integrations" / "console" / "demo"


def _script():
    spec = importlib.util.spec_from_file_location("make_console_demo", ROOT / "scripts" / "make_console_demo.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _events(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _files(folder: Path) -> dict[str, bytes]:
    return {path.relative_to(folder).as_posix(): path.read_bytes() for path in sorted(folder.rglob("*")) if path.is_file()}


def test_demo_runs_deterministic(tmp_path):
    script = _script()
    first, second = tmp_path / "a", tmp_path / "b"
    script.generate(first)
    script.generate(second)
    assert _files(first) == _files(second)
    assert _files(first) == _files(DEMO)


def test_demo_runs_cover_required_cases():
    build_full = _events(DEMO / "build" / "build-full.jsonl")
    assert [row["type"] for row in build_full if row["type"] in ("run_paused", "run_resumed", "run_finished")] == [
        "run_paused", "run_resumed", "run_finished"]
    assert build_full[-1]["status"] == "built"
    validate = [row for row in build_full if row.get("node") == "validate" and row["type"] == "node_started"]
    assert [row["attempt"] for row in validate] == [1, 2]
    assert any(row["type"] == "run_paused" and row["node"] == "design_gate" for row in build_full)
    assert any(row["type"] == "node_finished" and row["node"] == "design_gate" and row["summary"] == "approved"
               for row in build_full)
    assert any(row["type"] == "node_started" and row["node"] == "repair_silver" for row in build_full)
    assert "APPROVER_TOKEN_9f3c" not in (DEMO / "build" / "build-full.jsonl").read_text(encoding="utf-8")

    current = _events(DEMO / "build" / "build-current.jsonl")
    assert current[-1]["type"] == "run_finished" and current[-1]["status"] == "up_to_date"
    view = fold(current)
    skipped = [node for node, item in view["nodes"].items() if item["state"] == "skipped"]
    assert len(skipped) > len(BUILD_NODES) / 2

    repaired = _events(DEMO / "ask" / "ask-repaired.jsonl")
    assert repaired[-1]["status"] == "answered"
    attempts = [row["attempt"] for row in repaired if row.get("node") == "validate" and row["type"] == "node_started"]
    assert attempts == [1, 2]
    assert any(row.get("node") == "repair" and row["type"] == "node_finished" for row in repaired)
    text = (DEMO / "ask" / "ask-repaired.jsonl").read_text(encoding="utf-8")
    assert "SELECT" not in text
    assert "How much was billed in total?" not in text

    blocked = _events(DEMO / "ask" / "ask-blocked.jsonl")
    assert blocked[-1]["status"] == "blocked"
    guard = [row for row in blocked if row["type"] == "node_finished" and row["node"] == "guard"]
    assert len(guard) == 1 and guard[0]["summary"].startswith("blocked")
    blocked_view = fold(blocked)
    skipped_ask = [node for node, item in blocked_view["nodes"].items() if item["state"] == "skipped"]
    assert len(skipped_ask) > len(ASK_NODES) / 2
    assert "Ignore all previous instructions" not in (DEMO / "ask" / "ask-blocked.jsonl").read_text(encoding="utf-8")

    artifacts = json.loads((DEMO / "build" / "build-full.artifacts.json").read_text(encoding="utf-8"))
    assert artifacts["kpis"] and artifacts["models"]
    assert isinstance(artifacts["tests_passed"], int)
    assert isinstance(artifacts["repairs"], int)
    assert "SELECT" not in json.dumps(artifacts)


def test_studio_graphs_compile_offline(monkeypatch):
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    from governor.integrations import studio

    built = studio.build()
    asked = studio.ask()
    assert "design_gate" in built.get_graph().nodes
    assert "validate" in asked.get_graph().nodes
    assert getattr(built, "checkpointer", None) is None
    assert getattr(asked, "checkpointer", None) is None
