"""Reduce a run log to the view the console draws (batch4.md section 34).

Events apply in ``seq`` order. A duplicate ``seq`` is ignored. After ``run_finished``,
a build node that never started is ``skipped``. Cost is null when any finished
node's cost is null.
"""

from __future__ import annotations

import datetime as dt
from typing import Any


def _blank(state: str = "pending") -> dict[str, Any]:
    return {"state": state, "attempts": 0, "duration_ms": 0, "summary": None, "error_code": None}


def _seq_key(item: tuple[int, Any]) -> tuple:
    index, event = item
    if isinstance(event, dict):
        seq = event.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return (0, seq, index)
    return (1, index, 0)


def _apply_order(events: list) -> list[dict]:
    ordered = [event for _, event in sorted(enumerate(events), key=_seq_key)]
    seen: set[int] = set()
    applied: list[dict] = []
    for event in ordered:
        if not isinstance(event, dict):
            continue
        seq = event.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            if seq in seen:
                continue
            seen.add(seq)
        applied.append(event)
    return applied


def _ms(value: Any) -> int | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = dt.datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return int(parsed.timestamp() * 1000 + 0.5)


def _number(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    rounded = round(float(value), 6)
    if rounded == int(rounded):
        return int(rounded)
    return rounded


def _catalog(graph: str | None) -> list[str]:
    if graph != "build":
        return []
    from governor.core.runtrace.registry import BUILD_NODES

    return [spec.id for spec in sorted(BUILD_NODES, key=lambda spec: spec.order) if not spec.planned]


def _unrecovered(events: list[dict]) -> bool:
    last_fail = last_start = -1
    for index, event in enumerate(events):
        if event.get("type") == "node_failed":
            last_fail = index
        elif event.get("type") == "node_started":
            last_start = index
    return last_fail >= 0 and last_fail > last_start


def fold(events: list) -> dict:
    """``{run: {...}, nodes: {id: {state, attempts, duration_ms, summary, error_code}}}``."""
    applied = _apply_order(list(events or []))
    nodes: dict[str, dict[str, Any]] = {}
    recent: list[str] = []
    lifecycle = "running"
    status = None
    finished = False
    graph = None
    llm_calls = tokens_in = tokens_out = 0
    cost = 0.0
    cost_unknown = False

    def touch(node_id: str) -> None:
        if node_id in recent:
            recent.remove(node_id)
        recent.append(node_id)

    def ensure(node_id: Any) -> dict[str, Any] | None:
        if not isinstance(node_id, str) or not node_id:
            return None
        if node_id not in nodes:
            nodes[node_id] = _blank()
        return nodes[node_id]

    for event in applied:
        if graph is None and isinstance(event.get("graph"), str):
            graph = event["graph"]
        kind = event.get("type")
        node = ensure(event.get("node")) if event.get("node") else None
        if kind == "node_started" and node is not None:
            node["state"] = "running"
            node["attempts"] += 1
            touch(event["node"])
        elif kind == "node_finished" and node is not None:
            node["state"] = "done"
            duration = event.get("duration_ms")
            if isinstance(duration, int) and not isinstance(duration, bool):
                node["duration_ms"] += duration
            summary = event.get("summary")
            if isinstance(summary, str) and summary:
                node["summary"] = summary
            metrics = event.get("metrics")
            if isinstance(metrics, dict):
                for key, total in (("llm_calls", "llm_calls"), ("tokens_in", "tokens_in"), ("tokens_out", "tokens_out")):
                    part = _number(metrics.get(key))
                    if key == "llm_calls" and part is not None:
                        llm_calls += int(part)
                    elif key == "tokens_in" and part is not None:
                        tokens_in += int(part)
                    elif key == "tokens_out" and part is not None:
                        tokens_out += int(part)
                if "cost_usd" in metrics:
                    if metrics.get("cost_usd") is None:
                        cost_unknown = True
                    else:
                        part = _number(metrics.get("cost_usd"))
                        if part is None:
                            cost_unknown = True
                        else:
                            cost += float(part)
        elif kind == "node_failed" and node is not None:
            node["state"] = "failed"
            code = event.get("error_code")
            if isinstance(code, str) and code:
                node["error_code"] = code
        elif kind == "run_paused":
            lifecycle = "paused"
            status = event.get("status") if isinstance(event.get("status"), str) else status
            if node is not None:
                node["state"] = "paused"
                touch(event["node"])
        elif kind == "run_resumed":
            lifecycle = "running"
            status = None
        elif kind == "run_finished":
            lifecycle = "finished"
            finished = True
            status = event.get("status") if isinstance(event.get("status"), str) else status

    if _unrecovered(applied):
        lifecycle = "failed"
    if finished:
        for node_id in _catalog(graph):
            current = nodes.get(node_id)
            if current is None:
                nodes[node_id] = _blank("skipped")
            elif current["attempts"] == 0:
                current["state"] = "skipped"

    times = [stamp for event in applied if (stamp := _ms(event.get("ts"))) is not None]
    elapsed = times[-1] - times[0] if len(times) >= 2 else 0
    current_node = next((node_id for node_id in reversed(recent) if nodes[node_id]["state"] in ("running", "paused")), None)
    cost_usd: int | float | None
    if cost_unknown:
        cost_usd = None
    else:
        rounded = round(cost, 6)
        cost_usd = int(rounded) if rounded == int(rounded) else rounded
    return {
        "run": {"state": lifecycle, "status": status, "elapsed_ms": max(0, elapsed), "llm_calls": llm_calls,
                "tokens_in": tokens_in, "tokens_out": tokens_out, "cost_usd": cost_usd, "current_node": current_node},
        "nodes": nodes,
    }
