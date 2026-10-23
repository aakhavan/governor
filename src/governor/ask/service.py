"""governor-ask as a service: the one entry point the API (and later the UI and MCP) calls.

The graph is compiled once per process on a SqliteSaver over
``paths.CHECKPOINTS``, so a paused question can be resumed by a later
request. ``configure`` sets the chat model (None = the real per-node models)
and fixture options and drops the compiled graph; the next call compiles it
again.

Ownership: a thread belongs to the role that created it (the ``role`` in its
checkpointed state), and a trace to the role in its row. Another role gets
``NotFound``, exactly as for an id that does not exist.

Results never quote the question: refusal texts are fixed in the graph.
"""

from __future__ import annotations

import sqlite3
import threading
import uuid
from importlib import metadata
from pathlib import Path
from typing import Any, Literal

import pydantic
import yaml
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from governor.ask import traces
from governor.ask.graph import build_graph
from governor.ask.policy import roles
from governor.core import paths

Status = Literal["answered", "clarify", "refused", "unanswerable", "error"]

# Graph outcome -> API status. clarify_failed is final (no second question is
# asked), so a client must not offer a resume: it reads as unanswerable.
STATUS: dict[str, Status] = {
    "answer": "answered",
    "refused_guard": "refused",
    "refused_policy": "refused",
    "unanswerable": "unanswerable",
    "clarify_failed": "unanswerable",
    "refused_repair": "error",
    "refused_error": "error",
}


class ServiceError(Exception):
    """A request the service turns down; ``code`` is machine-readable, the message is safe to show."""

    code = "bad_request"

    def __init__(self, message: str, code: str | None = None) -> None:
        super().__init__(message)
        if code:
            self.code = code


class NotFound(ServiceError):
    code = "not_found"


class Conflict(ServiceError):
    code = "conflict"


class AskResult(pydantic.BaseModel):
    status: Status
    answer: str | None = None
    result_columns: list[str] = pydantic.Field(default_factory=list)
    result_rows: list[list[Any]] = pydantic.Field(default_factory=list)
    clarify_question: str | None = None
    sql: str | None = None
    models: list[str] = pydantic.Field(default_factory=list)
    lineage: list[str] = pydantic.Field(default_factory=list)
    freshness: list[dict] = pydantic.Field(default_factory=list)
    cost_usd: float | None = None
    trace_id: str | None = None
    thread_id: str


# ---------------------------------------------------------------------------
# the compiled graph (one per process)

_lock = threading.Lock()
_llm: Any = None
_llm_kind = "openrouter"
_options: dict[str, Any] = {}
_graph: Any = None
_connection: sqlite3.Connection | None = None


def configure(llm: Any = None, *, llm_kind: str | None = None, **graph_options: Any) -> None:
    """Set the chat model and graph options; the graph is compiled again on next use."""
    global _llm, _llm_kind, _options
    with _lock:
        _close()
        _llm = llm
        _llm_kind = llm_kind or ("openrouter" if llm is None else "fake")
        _options = dict(graph_options)


def reset() -> None:
    """Close the checkpoint connection and forget the compiled graph."""
    with _lock:
        _close()


def _close() -> None:
    global _graph, _connection
    if _connection is not None:
        _connection.close()
    _graph, _connection = None, None


def graph() -> Any:
    """The compiled ask graph on the SQLite checkpointer, built on first use."""
    global _graph, _connection
    with _lock:
        if _graph is None:
            target = Path(paths.CHECKPOINTS)
            target.parent.mkdir(parents=True, exist_ok=True)
            _connection = sqlite3.connect(str(target), check_same_thread=False)
            _graph = build_graph(llm=_llm, checkpointer=SqliteSaver(_connection), **_options)
        return _graph


# ---------------------------------------------------------------------------
# results


def _cost(state: dict) -> float | None:
    costs = [u.get("cost_usd") for u in state.get("usage") or []]
    if not costs:
        return 0.0
    return round(sum(costs), 6) if all(c is not None for c in costs) else None


def to_result(state: dict, thread_id: str) -> AskResult:
    """A graph result (final or paused) as an AskResult."""
    if state.get("__interrupt__"):
        slot = state["__interrupt__"][0].value.get("missing_slot")
        return AskResult(status="clarify", clarify_question=slot, cost_usd=_cost(state), thread_id=thread_id)
    trace = state.get("trace") or {}
    card = state.get("answer") or {}
    outcome = state.get("outcome") or "refused_error"
    status = STATUS.get(outcome, "error")
    answered = status == "answered"
    return AskResult(
        status=status,
        answer=card.get("text") or state.get("refusal"),
        result_columns=list(card.get("columns") or []) if answered else [],
        result_rows=[list(r) for r in card.get("rows") or []] if answered else [],
        sql=state.get("executed_sql") if answered else None,
        models=list(card.get("models") or []),
        lineage=list(card.get("sources") or []),
        freshness=list(card.get("freshness") or []),
        cost_usd=trace.get("cost_usd", _cost(state)),
        trace_id=trace.get("trace_id"),
        thread_id=thread_id,
    )


def _check_role(role: str) -> None:
    if role not in roles(_options.get("access_path")):
        raise ServiceError("unknown role", "unknown_role")


# ---------------------------------------------------------------------------
# the service


def ask(question: str, role: str, thread_id: str | None = None) -> AskResult:
    """Ask one question as ``role`` on a new thread (``thread_id`` names it)."""
    _check_role(role)
    compiled = graph()
    thread_id = thread_id or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    existing = compiled.get_state(config).values
    if existing and existing.get("role") != role:
        raise NotFound("thread not found")
    if existing:
        raise Conflict("this thread already exists; resume it or start a new one", "thread_exists")
    return to_result(compiled.invoke({"question": question, "role": role}, config), thread_id)


def resume(thread_id: str, answer: str, role: str) -> AskResult:
    """Answer the clarifying question of a paused thread that ``role`` created."""
    _check_role(role)
    compiled = graph()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = compiled.get_state(config)
    if not snapshot.values or snapshot.values.get("role") != role:
        raise NotFound("thread not found")
    if not snapshot.next:
        raise Conflict("this thread is not waiting for an answer", "not_waiting")
    return to_result(compiled.invoke(Command(resume=answer), config), thread_id)


def list_traces(role: str, outcome: str | None = None, limit: int = 50) -> list[dict]:
    """The role's own decision traces, newest first (redacted rows)."""
    _check_role(role)
    return traces.list_traces(role=role, outcome=outcome, limit=limit, path=_options.get("trace_path"))


def get_trace(trace_id: str, role: str) -> dict:
    """One decision trace, only if ``role`` created it."""
    _check_role(role)
    row = traces.get_trace(trace_id, path=_options.get("trace_path"))
    if row is None or row.get("role") != role:
        raise NotFound("trace not found")
    return row


def version() -> str:
    try:
        return metadata.version("governor")
    except metadata.PackageNotFoundError:
        return "unknown"


def as_of() -> str | None:
    """The green build instant, or None when the warehouse is not built."""
    moment = _options.get("as_of")
    if moment is not None:
        return moment.isoformat()
    try:
        return paths.as_of().isoformat()
    except FileNotFoundError:
        return None


def settings() -> dict:
    """Public, non-secret settings: version, as_of, chat model kind, roles and query limits."""
    access_path = Path(_options.get("access_path") or paths.KNOWLEDGE / "access.yaml")
    access = yaml.safe_load(access_path.read_text(encoding="utf-8"))
    return {
        "version": version(),
        "as_of": as_of(),
        "llm": _llm_kind,
        "roles": roles(_options.get("access_path")),
        "limits": access.get("limits", {}),
    }


__all__ = [
    "AskResult",
    "Conflict",
    "NotFound",
    "ServiceError",
    "ask",
    "configure",
    "get_trace",
    "graph",
    "list_traces",
    "reset",
    "resume",
    "settings",
]
