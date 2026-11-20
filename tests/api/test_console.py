"""Console API: auth, topology, runs, SSE and artifacts (batch4.md section 36). Offline."""

from __future__ import annotations

import json
from pathlib import Path

from governor.core.runtrace import fold, topology
from governor.core.runtrace.log import RunLog
from governor.integrations.console.stream import timing

ANALYST = {"Authorization": "Bearer test-analyst-token"}
MARKER = "ZZMARKER_7781"


def _write(state: Path, graph: str, run_id: str, events: list[dict]) -> None:
    path = state / "runs" / graph / f"{run_id}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(event) + "\n" for event in events), encoding="utf-8")


def _parse_sse(body: str) -> list[dict]:
    frames = []
    for block in body.split("\n\n"):
        if not block.strip() or block.lstrip().startswith(":"):
            continue
        item: dict = {}
        data = []
        for line in block.splitlines():
            if line.startswith(":"):
                continue
            if line.startswith("id:"):
                item["id"] = line.split(":", 1)[1].strip()
            elif line.startswith("event:"):
                item["event"] = line.split(":", 1)[1].strip()
            elif line.startswith("data:"):
                data.append(line.split(":", 1)[1].strip())
        if data:
            item["data"] = json.loads("".join(data))
            frames.append(item)
    return frames


def test_console_requires_token(client, monkeypatch):
    monkeypatch.delenv("GOVERNOR_CONSOLE_OPEN", raising=False)
    denied = client.get("/v1/console/graphs/build")
    assert denied.status_code == 401
    assert denied.json()["code"] == "unauthorized"
    bad = client.get("/v1/console/graphs/build", headers={"Authorization": "Bearer nope"})
    assert bad.status_code == 401
    ok = client.get("/v1/console/graphs/build", headers=ANALYST)
    assert ok.status_code == 200
    assert ok.json()["graph"] == "build"


def test_console_open_mode_allows_reads_only(client, monkeypatch):
    monkeypatch.setenv("GOVERNOR_CONSOLE_OPEN", "1")
    read = client.get("/v1/console/graphs/ask")
    assert read.status_code == 200
    assert read.json()["graph"] == "ask"
    posted = client.post("/v1/console/graphs/ask")
    assert posted.status_code == 405
    assert posted.json()["code"] == "method_not_allowed"
    assert client.delete("/v1/console/runs").status_code == 405
    ask = client.post("/v1/ask", json={"question": "how many accounts are there"})
    assert ask.status_code == 401
    assert ask.json()["code"] == "unauthorized"


def test_console_graph_topology(client):
    for name in ("build", "ask"):
        body = client.get(f"/v1/console/graphs/{name}", headers=ANALYST)
        assert body.status_code == 200
        assert body.json() == topology(name)
    missing = client.get("/v1/console/graphs/other", headers=ANALYST)
    assert missing.status_code == 404
    assert missing.json()["code"] == "not_found"


def test_console_runs_lists_live_and_demo(client, _state_dir):
    shipped = client.get("/v1/console/runs/build-full/artifacts", headers=ANALYST)
    assert shipped.status_code == 200
    assert shipped.json()["repairs"] == 1
    assert shipped.json()["kpis"]
    assert "SELECT" not in shipped.text
    _write(_state_dir, "build", "live-new", [
        {"v": 1, "ts": "2026-06-01T00:00:00.000+00:00", "run_id": "live-new", "graph": "build", "seq": 1,
         "type": "run_started"},
        {"v": 1, "ts": "2026-06-01T00:00:01.000+00:00", "run_id": "live-new", "graph": "build", "seq": 2,
         "type": "run_finished", "status": "built"},
    ])
    _write(_state_dir, "build", "build-full", [
        {"v": 1, "ts": "2026-06-02T00:00:00.000+00:00", "run_id": "build-full", "graph": "build", "seq": 1,
         "type": "run_started"},
        {"v": 1, "ts": "2026-06-02T00:00:01.000+00:00", "run_id": "build-full", "graph": "build", "seq": 2,
         "type": "run_finished", "status": "built"},
    ])
    listed = client.get("/v1/console/runs?limit=50", headers=ANALYST)
    assert listed.status_code == 200
    rows = listed.json()["runs"]
    by_id = {row["run_id"]: row for row in rows}
    assert by_id["live-new"]["source"] == "live"
    assert by_id["live-new"]["status"] == "built"
    assert by_id["live-new"]["graph"] == "build"
    assert by_id["build-full"]["source"] == "live"
    assert by_id["ask-blocked"]["source"] == "demo"
    assert by_id["ask-repaired"]["source"] == "demo"
    ask_only = client.get("/v1/console/runs?graph=ask", headers=ANALYST).json()["runs"]
    assert ask_only and all(row["graph"] == "ask" for row in ask_only)
    started = [row["started"] for row in rows]
    assert started == sorted(started, reverse=True)


def test_console_run_view_matches_fold(client, _state_dir):
    events = [
        {"v": 1, "ts": "2026-01-15T12:00:00.000+00:00", "run_id": "view-1", "graph": "ask", "seq": 1,
         "type": "run_started"},
        {"v": 1, "ts": "2026-01-15T12:00:00.250+00:00", "run_id": "view-1", "graph": "ask", "seq": 2,
         "type": "node_started", "node": "guard"},
        {"v": 1, "ts": "2026-01-15T12:00:00.500+00:00", "run_id": "view-1", "graph": "ask", "seq": 3,
         "type": "node_finished", "node": "guard", "summary": "ok", "duration_ms": 40},
        {"v": 1, "ts": "2026-01-15T12:00:00.750+00:00", "run_id": "view-1", "graph": "ask", "seq": 4,
         "type": "run_finished", "status": "answered"},
    ]
    _write(_state_dir, "ask", "view-1", events)
    body = client.get("/v1/console/runs/view-1", headers=ANALYST)
    assert body.status_code == 200
    assert body.json() == fold(events)
    assert client.get("/v1/console/runs/missing-run", headers=ANALYST).status_code == 404


def test_console_sse_frames_and_last_event_id(client, _state_dir, monkeypatch):
    sleeps: list[float] = []

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        if len(sleeps) > 3:
            raise AssertionError("live tail slept on a finished run")

    monkeypatch.setattr(timing, "sleep", sleep)
    events = [
        {"v": 1, "ts": "2026-01-15T12:00:00.000+00:00", "run_id": "sse-1", "graph": "build", "seq": 1,
         "type": "run_started", "note": "hidden"},
        {"v": 1, "ts": "2026-01-15T12:00:01.000+00:00", "run_id": "sse-1", "graph": "build", "seq": 2,
         "type": "node_finished", "node": "compare", "summary": "up to date"},
        {"v": 1, "ts": "2026-01-15T12:00:02.000+00:00", "run_id": "sse-1", "graph": "build", "seq": 3,
         "type": "run_finished", "status": "up_to_date"},
    ]
    _write(_state_dir, "build", "sse-1", events)
    full = client.get("/v1/console/runs/sse-1/events", headers=ANALYST)
    assert full.status_code == 200
    assert full.headers["content-type"].startswith("text/event-stream")
    frames = _parse_sse(full.text)
    assert [frame["id"] for frame in frames] == ["1", "2", "3"]
    assert [frame["event"] for frame in frames] == ["run_started", "node_finished", "run_finished"]
    assert frames[0]["data"]["type"] == "run_started"
    assert "note" not in frames[0]["data"]
    assert sleeps == []
    resumed = client.get("/v1/console/runs/sse-1/events", headers={**ANALYST, "Last-Event-ID": "1"})
    assert [frame["id"] for frame in _parse_sse(resumed.text)] == ["2", "3"]


def test_console_replay_pacing_capped(client, _state_dir, monkeypatch):
    sleeps: list[float] = []
    monkeypatch.setattr(timing, "sleep", lambda seconds: sleeps.append(seconds))
    events = [
        {"v": 1, "ts": "2026-01-15T12:00:00.000+00:00", "run_id": "pace-1", "graph": "build", "seq": 1,
         "type": "run_started"},
        {"v": 1, "ts": "2026-01-15T12:00:30.000+00:00", "run_id": "pace-1", "graph": "build", "seq": 2,
         "type": "node_finished", "node": "profile", "summary": "1 tables"},
        {"v": 1, "ts": "2026-01-15T12:01:00.000+00:00", "run_id": "pace-1", "graph": "build", "seq": 3,
         "type": "run_finished", "status": "built"},
    ]
    _write(_state_dir, "build", "pace-1", events)
    capped = client.get("/v1/console/runs/pace-1/events?replay=1&speed=1", headers=ANALYST)
    assert capped.status_code == 200
    assert [frame["event"] for frame in _parse_sse(capped.text)] == ["run_started", "node_finished", "run_finished"]
    assert sleeps == [2.0, 2.0]
    sleeps.clear()
    fast = client.get("/v1/console/runs/pace-1/events?replay=1&speed=100", headers=ANALYST)
    assert fast.status_code == 200
    assert sleeps == [30 / 32, 30 / 32]


def test_console_live_tail_ends_on_run_finished(client, _state_dir, monkeypatch):
    path = _state_dir / "runs" / "build" / "tail-1.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    started = {"v": 1, "ts": "2026-01-15T12:00:00.000+00:00", "run_id": "tail-1", "graph": "build", "seq": 1,
               "type": "run_started"}
    path.write_text(json.dumps(started) + "\n", encoding="utf-8")
    clock = {"t": 0.0}
    appended = {"done": False}
    sleeps: list[float] = []

    def now() -> float:
        return clock["t"]

    def sleep(seconds: float) -> None:
        sleeps.append(seconds)
        assert seconds <= 0.5
        clock["t"] += seconds
        if clock["t"] >= 1.5 and not appended["done"]:
            appended["done"] = True
            finish = {"v": 1, "ts": "2026-01-15T12:00:01.000+00:00", "run_id": "tail-1", "graph": "build",
                      "seq": 2, "type": "run_finished", "status": "built"}
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(finish) + "\n")

    monkeypatch.setattr(timing, "now", now)
    monkeypatch.setattr(timing, "sleep", sleep)
    monkeypatch.setattr(timing, "poll_s", 0.5)
    monkeypatch.setattr(timing, "heartbeat_s", 1.0)
    monkeypatch.setattr(timing, "idle_s", 30.0)
    body = client.get("/v1/console/runs/tail-1/events", headers=ANALYST)
    assert body.status_code == 200
    assert ": heartbeat" in body.text
    frames = _parse_sse(body.text)
    assert [frame["event"] for frame in frames] == ["run_started", "run_finished"]
    assert sleeps and max(sleeps) <= 0.5


def test_console_artifacts_names_and_counts_only(client, _state_dir, monkeypatch, tmp_path):
    root = tmp_path / "targets"
    folder = root / "shop"
    (folder / "governor").mkdir(parents=True)
    (folder / "target").mkdir()
    design = {
        "silver_models": [
            {"name": "stg_orders", "folder": "staging", "source_table": "orders",
             "columns": [{"name": "order_id", "expr": f"SELECT {MARKER}", "description": MARKER}]},
            {"name": "int_orders", "folder": "intermediate", "refs": ["stg_orders"]},
        ],
        "kpis": [
            {"id": "gmv", "decision": "build", "mapping": {"orders": "int_orders", "note": f"CASE {MARKER}"}},
            {"id": "churn", "decision": "decline", "reason": MARKER,
             "gap": {"missing": ["tenure"], "next_step": MARKER}},
            {"id": "voided", "decision": "decline", "reason": MARKER},
        ],
    }
    build = {
        "status": "built", "approved_by": MARKER, "thread_id": "art-1",
        "models": {"silver": ["stg_orders", "int_orders"], "gold": ["kpi_gmv"]},
        "tests_passed": {"silver": 2, "gold": 1, "total": 3},
        "kpis_built": [{"id": "gmv", "model": "kpi_gmv", "rows": 9}],
        "gaps": [{"id": "churn", "reason": MARKER}],
        "repairs": 2,
        "blueprint": [
            {"rule": "L2", "problem": MARKER},
            {"code": "MAPPING_UNKNOWN_COLUMN", "problem": MARKER},
            {"code": "MAPPING_UNKNOWN_COLUMN", "problem": "again"},
        ],
    }
    manifest = {"nodes": {
        "source.shop.raw.orders": {"resource_type": "source", "name": "orders", "description": MARKER},
        "model.shop.stg_orders": {
            "resource_type": "model", "name": "stg_orders", "fqn": ["shop", "staging", "stg_orders"],
            "depends_on": {"nodes": ["source.shop.raw.orders"]},
            "original_file_path": f"C:/secret/{MARKER}.sql", "description": MARKER,
        },
        "model.shop.int_orders": {
            "resource_type": "model", "name": "int_orders", "fqn": ["shop", "intermediate", "int_orders"],
            "depends_on": {"nodes": ["model.shop.stg_orders"]},
        },
        "model.shop.kpi_gmv": {
            "resource_type": "model", "name": "kpi_gmv", "fqn": ["shop", "marts", "kpi_gmv"],
            "depends_on": {"nodes": ["model.shop.int_orders"]}, "description": MARKER,
        },
    }}
    (folder / "governor" / "design.json").write_text(json.dumps(design), encoding="utf-8")
    (folder / "governor" / "build.json").write_text(json.dumps(build), encoding="utf-8")
    (folder / "target" / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    monkeypatch.setenv("GOVERNOR_TARGETS_DIR", str(root))
    _write(_state_dir, "build", "art-1", [
        {"v": 1, "ts": "2026-01-15T12:00:00.000+00:00", "run_id": "art-1", "graph": "build", "seq": 1,
         "type": "run_started", "target_name": "shop"},
        {"v": 1, "ts": "2026-01-15T12:00:01.000+00:00", "run_id": "art-1", "graph": "build", "seq": 2,
         "type": "run_finished", "status": "built"},
    ])
    body = client.get("/v1/console/runs/art-1/artifacts", headers=ANALYST)
    assert body.status_code == 200
    assert MARKER not in body.text
    assert "SELECT" not in body.text
    assert "approved_by" not in body.text
    assert "C:/" not in body.text
    payload = body.json()
    assert payload["tests_passed"] == 3
    assert payload["repairs"] == 2
    assert payload["finding_codes"] == {"L2": 1, "MAPPING_UNKNOWN_COLUMN": 2}
    assert {item["id"]: item["status"] for item in payload["kpis"]} == {
        "gmv": "built", "churn": "gap", "voided": "declined",
    }
    assert next(item for item in payload["kpis"] if item["id"] == "gmv")["models"] == ["int_orders"]
    assert payload["models"] == [
        {"name": "stg_orders", "layer": "staging"},
        {"name": "int_orders", "layer": "silver"},
        {"name": "kpi_gmv", "layer": "gold"},
    ]
    assert {item["id"]: item["layer"] for item in payload["lineage"]["nodes"]} == {
        "orders": "raw", "stg_orders": "silver", "int_orders": "silver", "kpi_gmv": "kpi",
    }
    assert payload["funnel"]["computable"] == 1
    assert payload["funnel"]["proposed"] == 3
    assert payload["funnel"]["validated"] == 3
    assert payload["funnel"]["built"] == 1
    assert isinstance(payload["funnel"]["requested"], int)


def test_console_artifacts_missing_inputs(client, _state_dir, monkeypatch, tmp_path):
    monkeypatch.setenv("GOVERNOR_TARGETS_DIR", str(tmp_path / "targets"))
    (tmp_path / "targets" / "empty").mkdir(parents=True)
    _write(_state_dir, "build", "bare-1", [
        {"v": 1, "ts": "2026-01-15T12:00:00.000+00:00", "run_id": "bare-1", "graph": "build", "seq": 1,
         "type": "run_started"},
        {"v": 1, "ts": "2026-01-15T12:00:01.000+00:00", "run_id": "bare-1", "graph": "build", "seq": 2,
         "type": "run_finished", "status": "built"},
    ])
    _write(_state_dir, "build", "empty-1", [
        {"v": 1, "ts": "2026-01-15T12:00:00.000+00:00", "run_id": "empty-1", "graph": "build", "seq": 1,
         "type": "run_started", "target_name": "empty"},
        {"v": 1, "ts": "2026-01-15T12:00:01.000+00:00", "run_id": "empty-1", "graph": "build", "seq": 2,
         "type": "run_finished", "status": "built"},
    ])
    for run_id in ("bare-1", "empty-1"):
        body = client.get(f"/v1/console/runs/{run_id}/artifacts", headers=ANALYST)
        assert body.status_code == 200
        payload = body.json()
        assert payload["kpis"] == []
        assert payload["models"] == []
        assert payload["tests_passed"] is None
        assert payload["repairs"] is None
        assert payload["finding_codes"] == {}
        assert payload["lineage"] == {"nodes": [], "edges": []}
        assert set(payload["funnel"].values()) == {None}
    assert client.get("/v1/console/runs/no-such-run/artifacts", headers=ANALYST).status_code == 404


def test_ask_routes_unchanged_with_console(client, monkeypatch):
    monkeypatch.setenv("GOVERNOR_CONSOLE_OPEN", "1")
    health = client.get("/health", headers={"Origin": "http://localhost:5173"})
    assert health.status_code == 200
    assert "access-control-allow-origin" not in health.headers
    ask = client.post("/v1/ask", json={"question": "how many accounts are there"},
                      headers={"Origin": "http://localhost:5173"})
    assert ask.status_code == 401
    assert ask.json() == {"error": "missing bearer token", "code": "unauthorized"}
    assert "access-control-allow-origin" not in ask.headers
    opened = client.get("/v1/console/graphs/build", headers={"Origin": "http://localhost:5173"})
    assert opened.status_code == 200
    assert opened.headers["access-control-allow-origin"] == "http://localhost:5173"
    foreign = client.get("/v1/console/graphs/build", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in foreign.headers
    preflight = client.options("/v1/console/graphs/build", headers={
        "Origin": "http://localhost:5173",
        "Access-Control-Request-Method": "GET",
    })
    assert preflight.status_code == 204
    assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
