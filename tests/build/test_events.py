"""Build events (batch2b section 12): the JSON lines log, notifiers, and the stages the graph reports."""
import json
import sys
import types

from governor.build import events, graph
from governor.build.llm import FakeBuildLLM

CALLS: list[dict] = []


def _read(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _notifiers(monkeypatch):
    mod = types.ModuleType("d6_fake_notifiers")

    def boom(event):
        raise RuntimeError("slack is down")

    mod.boom = boom
    mod.record = CALLS.append
    monkeypatch.setitem(sys.modules, "d6_fake_notifiers", mod)
    CALLS.clear()


def test_emit_appends_a_line(tmp_path):
    ev = events.emit("built", thread_id="t-1", kpis_built=8, gaps=["conversion_rate"], cost_usd=0.0)
    lines = _read(events.events_path())
    assert events.events_path().parent == tmp_path / "state"
    assert lines == [ev] and ev["kind"] == "built" and ev["thread_id"] == "t-1" and ev["ts"]
    assert ev["kpis_built"] == 8 and ev["gaps"] == ["conversion_rate"]


def test_failing_notifier_is_ignored(monkeypatch):
    _notifiers(monkeypatch)
    monkeypatch.setenv(events.NOTIFIERS_ENV, "d6_fake_notifiers:boom, no_such_module:x ,d6_fake_notifiers:record")
    ev = events.emit("published", thread_id="t-2", branch="governor/build-t-2")
    assert CALLS == [ev]
    assert _read(events.events_path())[-1]["kind"] == "published"


def test_unwritable_log_does_not_raise(monkeypatch, tmp_path):
    blocker = tmp_path / "file"
    blocker.write_text("x", encoding="utf-8")
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(blocker / "sub"))
    assert events.emit("built", thread_id="t")["kind"] == "built"


def test_graph_reports_its_stages_without_data_values(tmp_path, profile, good):
    llm = FakeBuildLLM({"propose": [json.dumps(good)]})
    out = graph.start(tmp_path / "target", "shop", llm, profile=profile, checkpoints=tmp_path / "cp.sqlite")
    graph.reject(out["thread_id"], "use payments for GMV", FakeBuildLLM({"propose": [json.dumps(good)]}),
                 checkpoints=tmp_path / "cp.sqlite")
    evs = _read(events.events_path())
    kinds = [e["kind"] for e in evs]
    assert kinds[:6] == ["run_started", "profiled", "proposed", "validated", "design_gate", "rejected"]
    assert kinds.count("design_gate") == 2 and all(e["thread_id"] == out["thread_id"] for e in evs)
    assert next(e for e in evs if e["kind"] == "proposed")["kpis_build"] == 8
    text = events.events_path().read_text(encoding="utf-8")
    assert "use payments" not in text  # the reviewer's note is not an event value
    for col in ("customer_unique_id", "order_id"):
        assert col not in text


def test_events_drop_nested_values():
    ev = events.emit("built", thread_id="t", n=3, names=["a", "b"], nested={"x": 1},
                     rows=[{"id": "c1"}, {"id": "c2"}], mixed=["a", {"id": 1}])
    assert ev["n"] == 3 and ev["names"] == ["a", "b"]
    assert not {"nested", "rows", "mixed"} & set(ev)
    assert "c1" not in events.events_path().read_text(encoding="utf-8")
