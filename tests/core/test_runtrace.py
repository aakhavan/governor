"""Run log, node wrapper and the shared fold cases (batch4.md sections 34-35). Offline."""
import inspect
import json
from pathlib import Path

import pytest
from langgraph.errors import GraphInterrupt
from langgraph.types import Interrupt

from governor.core.runtrace import RunLog, fold, traced

ROOT = Path(__file__).resolve().parents[2]
CASES = ROOT / "tests" / "fixtures" / "console" / "fold_cases.json"


def _lines(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def test_runlog_appends_and_continues_seq(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path))
    first = RunLog("build", "thread-1")
    first.emit("run_started")
    first.emit("node_started", node="profile")
    second = RunLog("build", "thread-1")
    second.emit("node_finished", node="profile", summary="2 tables", duration_ms=4)
    rows = _lines(first.path)
    assert [row["seq"] for row in rows] == [1, 2, 3]
    assert [row["type"] for row in rows] == ["run_started", "node_started", "node_finished"]
    assert rows[1]["attempt"] == 1 and rows[2]["attempt"] == 1
    assert rows[2]["summary"] == "2 tables"
    assert all(row["v"] == 1 and row["run_id"] == "thread-1" and row["graph"] == "build" for row in rows)


def test_runlog_never_raises(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path))
    import governor.core.runtrace.log as logmod

    def boom(*args, **kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(logmod, "_append_line", boom)
    log = RunLog("build", "thread-1")
    log.emit("run_started")
    log.emit("node_started", node="profile", summary="x" * 500, metrics={"llm_calls": "nope", "note": "secret"})


def test_runtrace_off_writes_nothing(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path))
    monkeypatch.setenv("GOVERNOR_RUNTRACE", "0")
    log = RunLog("build", "thread-1")
    log.emit("run_started")
    log.emit("node_finished", node="profile", summary="2 tables")
    assert not log.path.exists()
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize("case", json.loads(CASES.read_text(encoding="utf-8")), ids=lambda case: case["name"])
def test_fold_cases(case):
    assert fold(case["events"]) == case["expected"]


def test_traced_keeps_return_value(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path))

    def with_config(state, config):
        return {"n": state["n"] + 1, "thread": config["configurable"]["thread_id"]}

    def state_only(state):
        return {"ok": state["ok"], "calls": [{"input_tokens": 3, "output_tokens": 1, "cost_usd": 0.0}]}

    wrapped = traced("build", "propose", with_config, lambda update, state: f"{update['n']} models")
    bare = traced("build", "write_silver", state_only, lambda update, state: "1 models written")
    assert list(inspect.signature(wrapped).parameters) == ["state", "config"]
    assert list(inspect.signature(bare).parameters) == ["state"]
    assert wrapped({"n": 1}, {"configurable": {"thread_id": "t-1"}}) == {"n": 2, "thread": "t-1"}
    assert bare({"ok": True}) == {"ok": True, "calls": [{"input_tokens": 3, "output_tokens": 1, "cost_usd": 0.0}]}
    # the state-only node has no config: the entry point's run id is what gets logged
    from governor.core.runtrace.log import bind_run

    with bind_run("t-ctx"):
        assert bare({"ok": True})["ok"] is True
    finished = [row for row in _lines(RunLog("build", "t-ctx").path) if row["type"] == "node_finished"]
    assert finished[-1]["summary"] == "1 models written"
    assert finished[-1]["metrics"]["llm_calls"] == 1
    assert finished[-1]["metrics"]["cost_usd"] == 0


def test_interrupt_is_pause_not_failure(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path))
    exc = GraphInterrupt((Interrupt(value={"status": "awaiting_design_approval", "report": "SECRET_PATH"}),))

    def gate(state, config):
        raise exc

    wrapped = traced("build", "design_gate", gate, lambda update, state: "approved")
    with pytest.raises(GraphInterrupt) as caught:
        wrapped({"status": "awaiting_design_approval"}, {"configurable": {"thread_id": "t-pause"}})
    assert caught.value is exc
    text = RunLog("build", "t-pause").path.read_text(encoding="utf-8")
    assert "SECRET_PATH" not in text
    rows = _lines(RunLog("build", "t-pause").path)
    assert [row["type"] for row in rows] == ["node_started", "run_paused"]
    assert rows[1]["node"] == "design_gate" and rows[1]["status"] == "awaiting_approval"
    assert "node_failed" not in text


def test_failure_records_class_name_only(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path))

    def broken(state):
        raise ValueError("SECRET_MESSAGE_marker")

    wrapped = traced("build", "propose", broken, lambda update, state: "should not run")
    from governor.core.runtrace.log import bind_run

    with bind_run("t-fail"):
        with pytest.raises(ValueError, match="SECRET_MESSAGE_marker"):
            wrapped({})
    text = RunLog("build", "t-fail").path.read_text(encoding="utf-8")
    assert "ValueError" in text and "SECRET_MESSAGE_marker" not in text
    failed = [row for row in _lines(RunLog("build", "t-fail").path) if row["type"] == "node_failed"]
    assert failed[-1]["error_code"] == "ValueError" and failed[-1]["node"] == "propose"
