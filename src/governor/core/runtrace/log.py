"""Append-only run log and the node wrapper (batch4.md section 34).

A write failure is logged once and never raised into the graph. ``GOVERNOR_RUNTRACE=0``
turns writing off. Sequence numbers continue from the last line of the file, so a
new process keeps the count.
"""

from __future__ import annotations

import contextvars
import datetime as dt
import inspect
import json
import logging
import os
import string
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

from langgraph.errors import GraphInterrupt

from governor.core import paths

log = logging.getLogger(__name__)

VERSION = 1
TYPES = ("run_started", "node_started", "node_finished", "node_failed", "run_paused", "run_resumed", "run_finished")
_FIELDS = ("node", "attempt", "duration_ms", "summary", "status", "metrics", "error_code")
_METRIC_KEYS = ("llm_calls", "tokens_in", "tokens_out", "cost_usd")
_NODE_ATTEMPTS = ("node_started", "node_finished", "node_failed", "run_paused")
_LIMIT = 80
_PAUSE = {
    "awaiting_design_approval": "awaiting_approval",
    "awaiting_approval": "awaiting_approval",
    "awaiting_clarification": "awaiting_clarification",
}

_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("governor_run_id", default=None)
_write_warned = False


def _warn_once(exc: BaseException) -> None:
    global _write_warned
    if _write_warned:
        return
    _write_warned = True
    log.warning("run log write failed: %s", type(exc).__name__)


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="milliseconds")


def _part(value: str) -> str:
    cleaned = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value))
    return cleaned[:_LIMIT] or "x"


def log_path(graph: str, run_id: str) -> Path:
    raw = os.environ.get("GOVERNOR_STATE_DIR")
    base = paths.ROOT / raw if raw else paths.STATE
    return base / "runs" / _part(graph) / f"{_part(run_id)}.jsonl"


def _enabled() -> bool:
    return os.environ.get("GOVERNOR_RUNTRACE") != "0"


def _plain(value: float) -> int | float:
    rounded = round(float(value), 6)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def _as_int(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


_NAME_CHARS = frozenset(string.ascii_letters + string.digits + "_.-")


def _target_name(value: Any) -> str | None:
    """A directory name for the build target. A path, a slash or ``..`` is dropped."""
    if not isinstance(value, str):
        return None
    name = value.strip()
    if not name or len(name) > 80 or not name[0].isalnum():
        return None
    if any(ch not in _NAME_CHARS for ch in name):
        return None
    return name


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    flat = " ".join(value.split())[:_LIMIT]
    return flat or None


def _metrics(value: Any) -> dict | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, Any] = {}
    for key in _METRIC_KEYS:
        if key not in value:
            continue
        item = value[key]
        if key == "cost_usd" and item is None:
            out[key] = None
            continue
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            continue
        out[key] = _plain(item) if isinstance(item, float) else item
    return out or None


def _token(row: dict, *keys: str) -> int:
    """The first present token count. Build rows use ``input_tokens``; ask usage uses ``tokens_in``."""
    for key in keys:
        if key in row:
            found = _as_int(row.get(key))
            if found is not None:
                return found
    return 0


def call_metrics(calls: list | None) -> dict:
    """Totals for the ``calls`` a node added, or for the whole run. Cost is null when any call's cost is unknown."""
    rows = [row for row in (calls or []) if isinstance(row, dict)]
    tokens_in = tokens_out = 0
    costs: list[float] = []
    unknown = False
    for row in rows:
        tokens_in += _token(row, "input_tokens", "tokens_in")
        tokens_out += _token(row, "output_tokens", "tokens_out")
        if "cost_usd" not in row or row.get("cost_usd") is None:
            unknown = True
            continue
        cost = row.get("cost_usd")
        if isinstance(cost, bool) or not isinstance(cost, (int, float)):
            unknown = True
            continue
        costs.append(float(cost))
    return {"llm_calls": len(rows), "tokens_in": tokens_in, "tokens_out": tokens_out,
            "cost_usd": None if unknown else _plain(sum(costs))}


def _read_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _append_line(path: Path, line: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(line + "\n")


def _attempt(rows: list[dict], node: str | None, type_: str) -> int | None:
    if type_ not in _NODE_ATTEMPTS or not node:
        return None
    started = sum(1 for row in rows if row.get("type") == "node_started" and row.get("node") == node)
    if type_ == "node_started":
        return started + 1
    return started or None


class RunLog:
    """One JSONL file: ``GOVERNOR_STATE_DIR/runs/<graph>/<run_id>.jsonl``."""

    def __init__(self, graph: str, run_id: str) -> None:
        self.graph = graph
        self.run_id = run_id
        self.path = log_path(graph, run_id)

    def emit(self, type: str, **fields: Any) -> None:
        """Append one event. Unknown fields are dropped. Never raises."""
        if not _enabled():
            return
        try:
            self._write(type, fields)
        except Exception as exc:  # noqa: BLE001 — a log failure must not stop the run
            _warn_once(exc)

    def _write(self, type: str, fields: dict[str, Any]) -> None:
        if type not in TYPES:
            return
        rows = _read_events(self.path)
        last = rows[-1].get("seq") if rows else 0
        seq = last + 1 if isinstance(last, int) and not isinstance(last, bool) else 1
        event: dict[str, Any] = {"v": VERSION, "ts": _now(), "run_id": self.run_id, "graph": self.graph,
                                 "seq": seq, "type": type}
        node = _text(fields.get("node")) if "node" in fields else None
        if node is not None:
            event["node"] = node
        attempt = _as_int(fields["attempt"]) if "attempt" in fields else _attempt(rows, node, type)
        if attempt is not None:
            event["attempt"] = attempt
        duration = _as_int(fields.get("duration_ms")) if "duration_ms" in fields else None
        if duration is not None:
            event["duration_ms"] = duration
        summary = _text(fields.get("summary")) if "summary" in fields else None
        if summary is not None:
            event["summary"] = summary
        status = _text(fields.get("status")) if "status" in fields else None
        if status is not None:
            event["status"] = status
        if "metrics" in fields:
            metrics = _metrics(fields.get("metrics"))
            if metrics is not None:
                event["metrics"] = metrics
        error = _text(fields.get("error_code")) if "error_code" in fields else None
        if error is not None:
            event["error_code"] = error
        if type == "run_started":
            target = _target_name(fields.get("target_name")) if "target_name" in fields else None
            if target is not None:
                event["target_name"] = target
        _append_line(self.path, json.dumps(event, ensure_ascii=False))


@contextmanager
def bind_run(run_id: str) -> Iterator[None]:
    """The run id for nodes whose signature has no ``config``."""
    token = _run_id.set(run_id)
    try:
        yield
    finally:
        _run_id.reset(token)


def _run_from(config: Any, takes_config: bool) -> str | None:
    if takes_config and isinstance(config, dict):
        configurable = config.get("configurable")
        if isinstance(configurable, dict):
            thread = configurable.get("thread_id")
            if isinstance(thread, str) and thread.strip():
                return thread
    current = _run_id.get()
    if isinstance(current, str) and current.strip():
        return current
    return None


def _pause_status(exc: GraphInterrupt, node_id: str) -> str:
    raw = ""
    try:
        interrupts = exc.args[0] if exc.args else ()
        for item in interrupts:
            value = getattr(item, "value", None)
            if isinstance(value, dict) and isinstance(value.get("status"), str):
                raw = value["status"]
                break
    except Exception:  # noqa: BLE001 — the pause is still recorded
        raw = ""
    if raw in _PAUSE:
        return _PAUSE[raw]
    if node_id == "clarify":
        return "awaiting_clarification"
    return "awaiting_approval"


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _summary_text(summarise: Callable | None, update: Any, state: Any) -> str | None:
    if summarise is None or not isinstance(update, dict):
        return None
    try:
        text = summarise(update, state)
    except Exception:  # noqa: BLE001 — a bad summary must not fail the node
        return None
    return _text(text)


def _update_metrics(update: Any) -> dict | None:
    """Metrics for the calls a node just added: build's ``calls`` list, or ask's ``usage`` list."""
    if not isinstance(update, dict):
        return None
    calls = update.get("calls")
    if isinstance(calls, list):
        return call_metrics(calls)
    usage = update.get("usage")
    if isinstance(usage, list):
        return call_metrics(usage)
    return None


def traced(graph: str, node_id: str, fn: Callable, summarise: Callable | None):
    """Wrap a node. The signature and the return value stay; interrupts pause, other errors record the class name."""
    signature = inspect.signature(fn)
    takes_config = "config" in signature.parameters

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        state = args[0] if args else kwargs.get("state")
        config = kwargs.get("config")
        if config is None and len(args) > 1:
            config = args[1]
        run_id = _run_from(config, takes_config)
        run_log = RunLog(graph, run_id) if run_id else None
        if run_log is not None:
            run_log.emit("node_started", node=node_id)
        started = time.perf_counter()
        try:
            update = fn(state, config) if takes_config else fn(state)
        except GraphInterrupt as exc:
            if run_log is not None:
                run_log.emit("run_paused", node=node_id, status=_pause_status(exc, node_id))
            raise
        except Exception as exc:
            if run_log is not None:
                run_log.emit("node_failed", node=node_id, duration_ms=_elapsed_ms(started),
                             error_code=type(exc).__name__)
            raise
        if run_log is not None:
            run_log.emit("node_finished", node=node_id, duration_ms=_elapsed_ms(started),
                         summary=_summary_text(summarise, update, state), metrics=_update_metrics(update))
        return update

    wrapper.__signature__ = signature  # type: ignore[attr-defined]
    wrapper.__name__ = getattr(fn, "__name__", node_id)
    wrapper.__doc__ = getattr(fn, "__doc__", None)
    wrapper.__annotations__ = dict(getattr(fn, "__annotations__", {}))
    return wrapper
