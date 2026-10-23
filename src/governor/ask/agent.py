"""The governed ask graph as an evaluation system (``--system agent``).

Each question runs on its own thread. A clarify interrupt is the behaviour
``clarify``: the harness never answers it. Graph outcomes map to behaviours:

* ``answer``: answer, with the executed SQL and its rows;
* ``refused_guard`` / ``refused_policy``: refuse;
* ``unanswerable``: unanswerable;
* ``refused_repair`` / ``refused_error``: an answer that failed, with the
  last SQL attempt and its error (wrong on every item, as for the baseline).
"""

from __future__ import annotations

import uuid
from typing import Any

from governor.ask.graph import build_graph
from governor.eval.golden import Question
from governor.eval.systems import SystemOutput, register

BEHAVIOUR = {
    "answer": "answer",
    "refused_guard": "refuse",
    "refused_policy": "refuse",
    "unanswerable": "unanswerable",
    "clarify_failed": "clarify",
}


def _attempt_error(attempt: dict) -> str | None:
    if attempt.get("stage") == "execute" and not attempt.get("codes"):
        return None
    return attempt.get("error") or ", ".join(attempt.get("codes") or []) or "rejected"


def to_output(state: dict) -> SystemOutput:
    """A graph result (final or paused) as a SystemOutput."""
    usage = state.get("usage") or []
    costs = [u.get("cost_usd") for u in usage]
    meter = {
        "tokens_in": sum(int(u.get("tokens_in") or 0) for u in usage),
        "tokens_out": sum(int(u.get("tokens_out") or 0) for u in usage),
        "cost_usd": round(sum(costs), 6) if all(c is not None for c in costs) else None,
    }
    if state.get("__interrupt__"):
        return SystemOutput(behaviour="clarify", **meter)
    attempts = state.get("sql_attempts") or []
    repair = {"sql_attempts": max(len(attempts), 1), "first_sql_error": _attempt_error(attempts[0]) if attempts else None}
    outcome = state.get("outcome") or "refused_error"
    behaviour = BEHAVIOUR.get(outcome)
    if behaviour == "answer":
        return SystemOutput(
            behaviour="answer",
            sql=state.get("executed_sql"),
            columns=list(state.get("columns") or []),
            rows=[tuple(r) for r in state.get("rows") or []],
            **repair,
            **meter,
        )
    if behaviour is not None:
        return SystemOutput(behaviour=behaviour, **meter)
    last = attempts[-1] if attempts else {}
    return SystemOutput(
        behaviour="answer", sql=last.get("sql") or None, error=outcome, **repair, **meter
    )


@register("agent")
class AgentSystem:
    name = "agent"

    def __init__(self, llm: Any = None, **graph_options: Any) -> None:
        self.graph = build_graph(llm=llm, **graph_options)

    def answer(self, q: Question | str, role: str) -> SystemOutput:
        question = q.question if isinstance(q, Question) else str(q)
        config = {"configurable": {"thread_id": f"eval-{uuid.uuid4()}"}}
        return to_output(self.graph.invoke({"question": question, "role": role}, config))
