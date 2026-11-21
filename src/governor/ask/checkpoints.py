"""governor's LangGraph checkpoint store (``paths.CHECKPOINTS``, SQLite) and its privacy rules.

A checkpoint holds the whole graph state: the question, the SQL and the
result rows. So, unless ``GOVERNOR_TRACE_TEXT=1``:

- a thread's checkpoints are deleted as soon as its run ends (answered,
  refused, unanswerable or an error): ``invoke`` does it;
- only a thread paused at ``clarify`` keeps them, and ``prune_stale`` (called
  at the start of every new ask) deletes paused threads older than
  ``GOVERNOR_THREAD_TTL_H`` hours (default 24).

Deletion goes through ``SqliteSaver.delete_thread`` (LangGraph's public API:
``DELETE`` of the thread's rows in ``checkpoints`` and ``writes``). SQLite
would keep the deleted bytes in free pages and in the WAL, so every
connection runs with ``PRAGMA secure_delete=ON`` (deleted content is
overwritten with zeros) and the WAL is checkpointed and truncated after each
delete.

A finished thread leaves a tombstone (thread id, role, time; no text) in
``governor_finished_threads``, so the service can still tell "finished"
(409) from "never existed" (404). Tombstones expire with the same TTL.
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.errors import GraphInterrupt
from langgraph.types import Command

from governor.ask import traces
from governor.core import paths
from governor.core.runtrace.log import RunLog, bind_run, call_metrics

TTL_ENV = "GOVERNOR_THREAD_TTL_H"
DEFAULT_TTL_H = 24.0
FINISHED = "governor_finished_threads"


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    """A connection to the checkpoint database with ``secure_delete`` on."""
    target = Path(path or paths.CHECKPOINTS)
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(target), check_same_thread=False)
    connection.execute("PRAGMA secure_delete = ON")
    connection.execute(
        f"CREATE TABLE IF NOT EXISTS {FINISHED} (thread_id TEXT PRIMARY KEY, role TEXT, finished_at TEXT NOT NULL)"
    )
    connection.commit()
    return connection


@contextmanager
def open_saver(path: str | Path | None = None) -> Iterator[SqliteSaver]:
    """A SqliteSaver on the checkpoint database; the connection is closed on exit."""
    connection = connect(path)
    try:
        yield SqliteSaver(connection)
    finally:
        connection.close()


def ttl_hours() -> float:
    raw = os.environ.get(TTL_ENV)
    try:
        return float(raw) if raw not in (None, "") else DEFAULT_TTL_H
    except ValueError:
        return DEFAULT_TTL_H


def _now() -> datetime:
    # Housekeeping clock for the store, not data logic (data time is as_of).
    return datetime.now(timezone.utc)


def _scrub(store: SqliteSaver) -> None:
    """Move the WAL into the database file and truncate it, so no old page copy stays in the WAL."""
    with store.lock:
        store.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")


def finish(store: SqliteSaver, thread_id: str, role: str | None) -> None:
    """The run on ``thread_id`` ended: leave a tombstone and (unless trace text is on) delete its checkpoints."""
    _write(store, f"INSERT OR REPLACE INTO {FINISHED} (thread_id, role, finished_at) VALUES (?, ?, ?)",
           (thread_id, role, _now().isoformat()))
    if not traces.store_text():
        store.delete_thread(thread_id)
        _scrub(store)


def finished_role(store: SqliteSaver, thread_id: str) -> str | None:
    """The role that ran ``thread_id`` to the end, or None when there is no tombstone."""
    with store.lock:
        row = store.conn.execute(f"SELECT role FROM {FINISHED} WHERE thread_id = ?", (thread_id,)).fetchone()
    return row[0] if row else None


def _write(store: SqliteSaver, sql: str, params: tuple) -> None:
    """One statement on the tombstone table, under the saver's lock, committed."""
    with store.lock:
        store.conn.execute(sql, params)
        store.conn.commit()


def run_status(outcome: str | None) -> str:
    """Map a graph outcome to a run-log status: ``answered``, ``refused``, ``blocked`` or ``error``.

    A guard refusal is ``blocked``. Other refusals, an unanswerable plan and a
    failed clarification are ``refused``. A warehouse failure or an unknown end
    is ``error``.
    """
    if outcome == "answer":
        return "answered"
    if outcome == "refused_guard":
        return "blocked"
    if outcome in {"refused_policy", "refused_repair", "unanswerable", "clarify_failed"}:
        return "refused"
    return "error"


def _is_resume(payload: Any) -> bool:
    return isinstance(payload, Command) and payload.resume is not None


def _outcome(result: dict) -> str | None:
    outcome = result.get("outcome")
    if isinstance(outcome, str) and outcome:
        return outcome
    trace = result.get("trace")
    if isinstance(trace, dict):
        recorded = trace.get("outcome")
        if isinstance(recorded, str) and recorded:
            return recorded
    return None


def _run_metrics(result: dict | None) -> dict | None:
    if not isinstance(result, dict):
        return None
    usage = result.get("usage")
    if not isinstance(usage, list) or not usage:
        return None
    return call_metrics(usage)


def _emit_finished(run_log: RunLog, result: dict | None) -> None:
    """``run_finished`` for a thread that ended. Never raises into the caller."""
    try:
        status = run_status(_outcome(result)) if isinstance(result, dict) else "error"
        metrics = _run_metrics(result)
        if metrics is None:
            run_log.emit("run_finished", status=status)
        else:
            run_log.emit("run_finished", status=status, metrics=metrics)
    except Exception:  # noqa: BLE001 — tracing must not change the ask result
        run_log.emit("run_finished", status="error")


def invoke(graph: Any, store: SqliteSaver, payload: Any, config: dict, role: str | None) -> dict:
    """``graph.invoke`` that drops the thread's checkpoints unless the run paused at clarify.

    This is the one funnel for ask calls. A new thread emits ``run_started``; a
    ``Command(resume=...)`` emits ``run_resumed``. ``run_finished`` is written
    only when the thread ends. A clarify interrupt stays a pause.
    """
    thread_id = config["configurable"]["thread_id"]
    run_log = RunLog("ask", thread_id)
    run_log.emit("run_resumed" if _is_resume(payload) else "run_started")
    paused = False
    result: dict | None = None
    try:
        with bind_run(thread_id):
            result = graph.invoke(payload, config)
        paused = bool(isinstance(result, dict) and result.get("__interrupt__"))
        return result
    except GraphInterrupt:
        paused = True
        raise
    finally:
        if not paused:
            _emit_finished(run_log, result if isinstance(result, dict) else None)
            finish(store, thread_id, role)


def prune_stale(store: SqliteSaver, *, ttl_h: float | None = None, now: datetime | None = None) -> list[str]:
    """Delete threads whose newest checkpoint is older than the TTL (and old tombstones); returns their ids."""
    cutoff = (now or _now()) - timedelta(hours=ttl_hours() if ttl_h is None else ttl_h)
    newest: dict[str, datetime] = {}
    for item in store.list(None):
        thread_id = item.config["configurable"]["thread_id"]
        ts = datetime.fromisoformat(item.checkpoint["ts"])
        if thread_id not in newest or ts > newest[thread_id]:
            newest[thread_id] = ts
    stale = sorted(t for t, ts in newest.items() if ts < cutoff)
    for thread_id in stale:
        store.delete_thread(thread_id)
    _write(store, f"DELETE FROM {FINISHED} WHERE finished_at < ?", (cutoff.isoformat(),))
    if stale:
        _scrub(store)
    return stale
