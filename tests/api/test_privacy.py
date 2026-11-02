"""C1: checkpoint privacy (no question or rows kept after a run) and the hidden OpenAPI schema."""

from __future__ import annotations

import json
import sqlite3

from governor.ask import service
from governor.ask.llm_testing import scripted
from governor.core import paths

ANALYST = {"Authorization": "Bearer test-analyst-token"}
MARKER = "qqmarkerzz"


def _plan(intent: str = "answer", **extra) -> str:
    return json.dumps({"intent": intent, "models": ["dim_accounts"], **extra})


def _llm(clarify: bool = False):
    plans = [_plan("clarify", missing_slot="Active accounts only, or all of them?")] if clarify else []
    return scripted(
        {
            "plan": [*plans, _plan()],
            "sql": [json.dumps({"sql": "SELECT count(*) AS accounts FROM dim_accounts"})],
            "answer": [json.dumps({"text_with_placeholders": "There are {r0c0} accounts."})],
        }
    )


def _rows(thread_id: str) -> int:
    con = sqlite3.connect(str(paths.CHECKPOINTS))
    try:
        return sum(
            con.execute(f"SELECT count(*) FROM {table} WHERE thread_id = ?", [thread_id]).fetchone()[0]
            for table in ("checkpoints", "writes")
        )
    finally:
        con.close()


def _leaks(*needles: str) -> list[str]:
    """State files that still contain any of ``needles`` (checkpoint connection closed first)."""
    service.reset()
    files = [p for p in paths.STATE.rglob("*") if p.is_file()]
    assert files
    return sorted(p.name for p in files if any(n.encode() in p.read_bytes() for n in needles))


def test_checkpoints_deleted_after_answer(make_client):
    client = make_client(llm=_llm())
    r = client.post("/v1/ask", json={"question": f"how many accounts {MARKER}", "thread_id": "t-done"},
                    headers=ANALYST)
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["status"] == "answered" and done["result_rows"]
    assert _rows("t-done") == 0

    # a finished thread id still cannot be reused or resumed (tombstone, no text)
    again = client.post("/v1/ask", json={"question": "again", "thread_id": "t-done"}, headers=ANALYST)
    assert again.status_code == 409 and again.json()["code"] == "thread_exists"
    late = client.post("/v1/threads/t-done/resume", json={"answer": "x"}, headers=ANALYST)
    assert late.status_code == 409 and late.json()["code"] == "not_waiting"

    assert _leaks(MARKER) == []


def test_refused_run_leaves_no_checkpoints(make_client):
    client = make_client(llm=scripted({"plan": [_plan("unanswerable")]}))
    r = client.post("/v1/ask", json={"question": f"what is the weather {MARKER}", "thread_id": "t-no"},
                    headers=ANALYST)
    assert r.status_code == 200, r.text
    assert r.json()["status"] != "clarify"
    assert _rows("t-no") == 0
    assert _leaks(MARKER) == []


def test_paused_thread_kept_until_resume(make_client, monkeypatch):
    client = make_client(llm=_llm(clarify=True))
    r = client.post("/v1/ask", json={"question": f"how many accounts {MARKER}", "thread_id": "t-wait"},
                    headers=ANALYST)
    assert r.json()["status"] == "clarify"
    assert _rows("t-wait") > 0  # kept while paused

    r = client.post("/v1/threads/t-wait/resume", json={"answer": "all of them"}, headers=ANALYST)
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "answered"
    assert _rows("t-wait") == 0
    assert _leaks(MARKER) == []


def test_stale_paused_thread_pruned_at_next_ask(make_client, monkeypatch):
    client = make_client(llm=_llm(clarify=True))
    r = client.post("/v1/ask", json={"question": f"how many accounts {MARKER}", "thread_id": "t-old"},
                    headers=ANALYST)
    assert r.json()["status"] == "clarify" and _rows("t-old") > 0

    monkeypatch.setenv("GOVERNOR_THREAD_TTL_H", "0")  # every paused thread is now past its TTL
    client = make_client(llm=_llm())
    r = client.post("/v1/ask", json={"question": "how many accounts", "thread_id": "t-new"}, headers=ANALYST)
    assert r.status_code == 200, r.text
    assert _rows("t-old") == 0
    assert client.post("/v1/threads/t-old/resume", json={"answer": "all"}, headers=ANALYST).status_code == 404
    assert _leaks(MARKER) == []


def test_secure_delete_is_on():
    from governor.ask import checkpoints

    con = checkpoints.connect(paths.CHECKPOINTS)
    try:
        assert con.execute("PRAGMA secure_delete").fetchone()[0] == 1
    finally:
        con.close()


def test_openapi_hidden_by_default(make_client, monkeypatch):
    monkeypatch.delenv("GOVERNOR_API_DOCS", raising=False)
    client = make_client()
    hidden = client.get("/openapi.json")
    assert hidden.status_code == 404 and hidden.json()["code"] == "not_found"
    assert client.get("/docs").status_code == 404 and client.get("/redoc").status_code == 404
    assert client.get("/health").status_code == 200

    monkeypatch.setenv("GOVERNOR_API_DOCS", "1")
    shown = make_client().get("/openapi.json")
    assert shown.status_code == 200 and "/v1/ask" in shown.json()["paths"]
