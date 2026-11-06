"""Build events (batch2b section 12): the seam for Slack in D9.

``emit(kind, **data)`` appends one JSON line ``{ts, thread_id, kind, ...}`` to ``GOVERNOR_STATE_DIR/events.jsonl``
and calls each notifier named in ``GOVERNOR_BUILD_NOTIFIERS`` (comma-separated ``module:function`` paths) with the
event dict. A failing notifier, or a log file that cannot be written, is logged and never stops a build.

Events carry counts, names, codes, status, cost and seconds; never data values. Callers pass only those. As a
guard, values are kept only when they are scalars or flat lists of scalars (nested values are dropped), and strings are cut at 300 characters.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import logging
import os
from pathlib import Path
from typing import Any, Callable

from governor.core import paths

log = logging.getLogger(__name__)

EVENTS_FILE = "events.jsonl"
NOTIFIERS_ENV = "GOVERNOR_BUILD_NOTIFIERS"
KINDS = ("run_started", "profiled", "proposed", "validated", "design_gate", "approved", "rejected", "silver_built",
         "repair", "escalated", "gold_built", "built", "published", "certified")
_MAX_TEXT = 300


def events_path() -> Path:
    raw = os.environ.get("GOVERNOR_STATE_DIR")
    return (paths.ROOT / raw if raw else paths.STATE) / EVENTS_FILE


def _scalar(v: Any) -> Any:
    if isinstance(v, str):
        return v[:_MAX_TEXT]
    if v is None or isinstance(v, (bool, int, float)):
        return v
    return str(v)[:_MAX_TEXT]


_DROP = object()


def _is_scalar(v: Any) -> bool:
    return v is None or isinstance(v, (str, bool, int, float))


def _clean(v: Any) -> Any:
    """Scalars and flat lists of scalars are kept; anything nested (dicts, lists of dicts) is dropped."""
    if isinstance(v, (list, tuple, set)):
        return [_scalar(x) for x in v] if all(_is_scalar(x) for x in v) else _DROP
    if isinstance(v, dict):
        return _DROP
    return _scalar(v)


def _notifiers() -> list[tuple[str, Callable[[dict], Any] | None]]:
    out: list[tuple[str, Callable[[dict], Any] | None]] = []
    for spec in (os.environ.get(NOTIFIERS_ENV) or "").split(","):
        spec = spec.strip()
        if not spec:
            continue
        try:
            module, _, name = spec.partition(":")
            out.append((spec, getattr(importlib.import_module(module), name)))
        except Exception as exc:  # noqa: BLE001
            log.warning("build notifier %s cannot be loaded: %s: %s", spec, type(exc).__name__, exc)
            out.append((spec, None))
    return out


def emit(kind: str, **data: Any) -> dict:
    """Record one event and tell the notifiers. Returns the event; never raises."""
    if kind not in KINDS:
        log.warning("unknown build event kind %r", kind)
    event: dict[str, Any] = {"ts": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                             "thread_id": _scalar(data.pop("thread_id", None)), "kind": kind}
    cleaned = {k: _clean(v) for k, v in data.items()}
    event.update({k: v for k, v in cleaned.items() if v is not _DROP})
    try:
        path = events_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as exc:  # noqa: BLE001
        log.warning("build event %s not written: %s: %s", kind, type(exc).__name__, exc)
    for spec, fn in _notifiers():
        if fn is None:
            continue
        try:
            fn(dict(event))
        except Exception as exc:  # noqa: BLE001
            log.warning("build notifier %s failed on %s: %s: %s", spec, kind, type(exc).__name__, exc)
    return event


__all__ = ["EVENTS_FILE", "KINDS", "NOTIFIERS_ENV", "emit", "events_path"]
