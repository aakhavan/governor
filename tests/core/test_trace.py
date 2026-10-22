"""The on-disk trace keeps no stakeholder text and stays bounded."""

import json

import triage.trace as trace_module
from triage.trace import current_trace, reset_trace, trace


def test_user_text_is_summarised_on_disk_but_kept_in_memory(tmp_path, monkeypatch):
    log = tmp_path / "trace.jsonl"
    monkeypatch.setattr(trace_module, "LOG_PATH", log)
    reset_trace()

    secret = "Our patient records from Klinik Nord need a nightly export"
    trace("retrieve", question=secret, queries=[secret, "nightly export"], mode="hybrid")

    written = log.read_text(encoding="utf-8")
    assert "Klinik Nord" not in written
    record = json.loads(written)
    assert record["question"] == {"chars": len(secret), "sha256": record["question"]["sha256"]}
    assert record["queries"] == {"count": 2}
    assert record["mode"] == "hybrid"
    assert current_trace()[-1]["question"] == secret


def test_log_rotates_when_it_grows_past_the_limit(tmp_path, monkeypatch):
    log = tmp_path / "trace.jsonl"
    monkeypatch.setattr(trace_module, "LOG_PATH", log)
    monkeypatch.setattr(trace_module, "MAX_LOG_BYTES", 200)

    for index in range(20):
        trace("tool", name="price_pattern", index=index)

    previous = tmp_path / "trace.jsonl.1"
    assert previous.is_file()
    assert log.stat().st_size < 200 + 100
    assert sorted(path.name for path in tmp_path.iterdir()) == ["trace.jsonl", "trace.jsonl.1"]
