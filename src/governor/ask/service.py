"""governor-ask as a service: the one entry point the API (and later the UI and MCP) calls.

The graph is compiled once per process on a SqliteSaver over
``paths.CHECKPOINTS``, so a paused question can be resumed by a later
request. A finished run's checkpoints are deleted, and paused threads past
their TTL are pruned at the start of each ask (``governor.ask.checkpoints``). ``configure`` sets the chat model (None = the real per-node models)
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

import duckdb
import pydantic
import yaml
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command
from pydantic_core import to_jsonable_python

from governor.ask import catalog, checkpoints, executor, retrieval, traces, validator
from governor.ask.graph import build_graph
from governor.ask.policy import Policy, roles
from governor.core import lineage, paths

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
_saver: SqliteSaver | None = None


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
    global _graph, _connection, _saver
    if _connection is not None:
        _connection.close()
    _graph, _connection, _saver = None, None, None


def graph() -> Any:
    """The compiled ask graph on the SQLite checkpointer, built on first use."""
    global _graph, _connection, _saver
    with _lock:
        if _graph is None:
            _connection = checkpoints.connect(paths.CHECKPOINTS)
            _saver = SqliteSaver(_connection)
            _graph = build_graph(llm=_llm, checkpointer=_saver, **_options)
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
    checkpoints.prune_stale(_saver)
    existing = compiled.get_state(config).values
    owner = existing.get("role") if existing else checkpoints.finished_role(_saver, thread_id)
    if owner is not None and owner != role:
        raise NotFound("thread not found")
    if owner is not None:
        raise Conflict("this thread already exists; resume it or start a new one", "thread_exists")
    state = checkpoints.invoke(compiled, _saver, {"question": question, "role": role}, config, role)
    return to_result(state, thread_id)


def resume(thread_id: str, answer: str, role: str) -> AskResult:
    """Answer the clarifying question of a paused thread that ``role`` created."""
    _check_role(role)
    compiled = graph()
    config = {"configurable": {"thread_id": thread_id}}
    snapshot = compiled.get_state(config)
    owner = snapshot.values.get("role") if snapshot.values else checkpoints.finished_role(_saver, thread_id)
    if owner is None or owner != role:
        raise NotFound("thread not found")
    if not snapshot.next:
        raise Conflict("this thread is not waiting for an answer", "not_waiting")
    return to_result(checkpoints.invoke(compiled, _saver, Command(resume=answer), config, role), thread_id)


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


# ---------------------------------------------------------------------------
# read-only catalog and query tools (MCP calls these; no LLM, no writes)

MAX_LINEAGE_DEPTH = 3
MAX_SEARCH_K = 20


def search_catalog(query: str, k: int = 5) -> dict:
    """BM25 over the catalog and metric cards (offline: no embedding calls)."""
    k = max(1, min(int(k), MAX_SEARCH_K))
    by_id = {c["id"]: c for c in retrieval.load_cards()}
    hits = retrieval.search(query, k=k, mode="bm25", cards=list(by_id.values()))
    return {
        "hits": [
            {
                "card_id": h.card_id,
                "kind": by_id[h.card_id]["kind"],
                "name": by_id[h.card_id]["name"],
                "tables": h.tables,
                "score": h.score,
            }
            for h in hits
        ]
    }


def _meta_path() -> Path:
    return Path(_options.get("meta_path") or paths.META)


def _visible_model(name: str, role: str) -> str | None:
    """The lower-case model name when ``role`` may query it, else None."""
    _check_role(role)
    policy = Policy.for_role(role, access_path=_options.get("access_path"), meta_path=_options.get("meta_path"))
    name = (name or "").strip().lower()
    return name if name in policy.models else None


def describe_model(name: str, role: str) -> dict:
    """Description, owner, grain, columns (with PII tags) and tests of a model ``role`` may query."""
    model = _visible_model(name, role)
    if model is None:
        return {"error": f"unknown model {name!r}"}
    connection = duckdb.connect(str(_meta_path()), read_only=True)
    try:
        unique_id, owner, description = connection.execute(
            "SELECT unique_id, owner, description FROM nodes WHERE resource_type = 'model' AND lower(name) = ?",
            [model],
        ).fetchone()
        columns = connection.execute(
            'SELECT "column", data_type, description, pii_tag FROM columns WHERE unique_id = ? ORDER BY "column"',
            [unique_id],
        ).fetchall()
        tests = connection.execute(
            'SELECT attached_node, "column", test_type, severity FROM tests WHERE attached_node = ? '
            'ORDER BY test_type, "column"',
            [unique_id],
        ).fetchall()
    finally:
        connection.close()
    description = (description or "").strip()
    return {
        "name": model,
        "description": description,
        "owner": owner,
        "grain": catalog._grain(description, tests),
        "columns": [
            {"name": c, "type": t, "description": (d or "").strip(), "pii_tag": tag} for c, t, d, tag in columns
        ],
        "tests": [{"type": t, "column": c, "severity": s} for _node, c, t, s in tests],
    }


def get_lineage(name: str, role: str, direction: str = "upstream", depth: int = 2) -> dict:
    """Upstream or downstream nodes of a model ``role`` may query, at most MAX_LINEAGE_DEPTH hops."""
    if direction not in ("upstream", "downstream"):
        return {"error": "direction must be 'upstream' or 'downstream'"}
    model = _visible_model(name, role)
    if model is None:
        return {"error": f"unknown model {name!r}"}
    depth = max(1, min(int(depth), MAX_LINEAGE_DEPTH))
    connection = duckdb.connect(str(_meta_path()), read_only=True)
    try:
        nodes = connection.execute("SELECT unique_id, resource_type, name FROM nodes").fetchall()
        edges = connection.execute("SELECT parent, child FROM edges").fetchall()
    finally:
        connection.close()
    info = {uid: (kind, node_name) for uid, kind, node_name in nodes}
    start = next(uid for uid, (kind, n) in info.items() if kind == "model" and n.lower() == model)
    graph = {"nodes": list(info), "edges": [{"parent": p, "child": c} for p, c in edges]}
    walk = lineage.upstream if direction == "upstream" else lineage.downstream
    return {
        "name": model,
        "direction": direction,
        "depth": depth,
        "nodes": [
            {"unique_id": uid, "kind": info.get(uid, ("unknown", uid))[0], "name": info.get(uid, ("", uid))[1]}
            for uid in walk(start, graph, depth)
        ],
    }


def validate_sql(sql: str, role: str) -> dict:
    """The validator's verdict for ``role``; ``sql`` is the rewritten query when ok."""
    _check_role(role)
    checked = validator.validate(sql, role, access_path=_options.get("access_path"), meta_path=_options.get("meta_path"))
    return {"ok": checked.ok, "codes": list(checked.codes), "reasons": list(checked.reasons), "sql": checked.sql}


def run_query(sql: str, role: str) -> dict:
    """Validate, dry-run and run ``sql`` read-only as ``role`` (executor.execute; never skips the validator)."""
    _check_role(role)
    result = executor.execute(sql, role, access_path=_options.get("access_path"), meta_path=_options.get("meta_path"))
    return {
        "ok": result.ok,
        "codes": list(result.codes),
        "reasons": list(result.reasons),
        "columns": list(result.columns),
        "rows": to_jsonable_python([list(r) for r in result.rows]),
        "row_count": result.row_count,
    }


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
    "describe_model",
    "get_lineage",
    "get_trace",
    "graph",
    "list_traces",
    "reset",
    "resume",
    "run_query",
    "search_catalog",
    "settings",
    "validate_sql",
]
