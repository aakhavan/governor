"""One-request trace for the UI, plus an append-only log on disk.

The file (logs/trace.jsonl in the sprint folder) keeps events across requests.
The in-memory list is only the request in progress, because a Streamlit
process stays up and the UI needs this request's events without rereading
the whole log. Call reset_trace() at the start of each request.

What reaches the disk is reduced: the stakeholder's own words (the question
and the query rewrites made from it) are replaced by their length and a short
hash, so the log can still group events by request without keeping the text.
The file is rotated at MAX_LOG_BYTES, keeping one previous file, so local
retention is bounded. The in-memory copy keeps the full text for this request.
"""

from __future__ import annotations

import contextvars
import hashlib
import json
from datetime import datetime, timezone

from triage.config import PROJECT_DIR

LOG_PATH = PROJECT_DIR / "logs" / "trace.jsonl"
MAX_LOG_BYTES = 5 * 1024 * 1024

# Fields that carry user text. Kept in memory, summarised on disk.
USER_TEXT_FIELDS = frozenset({"question", "queries"})

# Events since the last reset_trace(). Not cleared when the process starts
# a new Streamlit rerun unless the caller resets it.
_current: list[dict] = []
_enabled: contextvars.ContextVar[bool] = contextvars.ContextVar(
    "triage_trace_enabled", default=True
)


def set_trace_enabled(enabled: bool):
    """Turn disk and memory tracing on or off for the current task."""
    return _enabled.set(bool(enabled))


def reset_trace_enabled(token) -> None:
    _enabled.reset(token)


def reset_trace() -> None:
    """Clear the in-memory events for the current request. The log file stays append-only."""
    _current.clear()


def current_trace() -> list[dict]:
    """A copy of the events recorded for the current request."""
    return list(_current)


def _summarise(value) -> dict:
    """Length and a short hash instead of the text itself."""
    if isinstance(value, (list, tuple)):
        return {"count": len(value)}
    text = str(value)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
    return {"chars": len(text), "sha256": digest}


def _rotate_if_large() -> None:
    try:
        if LOG_PATH.stat().st_size >= MAX_LOG_BYTES:
            LOG_PATH.replace(LOG_PATH.with_name(LOG_PATH.name + ".1"))
    except FileNotFoundError:
        pass


def trace(event: str, **fields) -> dict:
    """Append one JSON line and keep the same record in memory.

    `default=str` is there so a later tool result (a datetime, a pydantic
    model) can be logged without the request dying on a type error.
    """
    if not _enabled.get():
        return {"event": event, "skipped": True}
    payload = {key: value for key, value in fields.items() if key not in {"ts", "event"}}
    record = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        **payload,
    }
    _current.append(record)
    on_disk = {
        key: (_summarise(value) if key in USER_TEXT_FIELDS and value is not None else value)
        for key, value in record.items()
    }
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    _rotate_if_large()
    with LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(on_disk, ensure_ascii=False, default=str) + "\n")
    return record
