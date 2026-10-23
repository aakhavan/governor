"""Systems under evaluation: one protocol, a registry, and three self-test systems.

A system gets one golden question and the asking role and returns a
``SystemOutput``. The self-test systems pin the harness down: ``oracle``
must score 1.0 everywhere, ``null`` must score 0 on accuracy, and ``leaky``
must be caught by the PII detector for every analyst item.
"""

from __future__ import annotations

import importlib
import threading
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Any, Callable, Literal, Protocol

import yaml

from governor.core import paths
from governor.core.warehouse import connect
from governor.eval.golden import NEEDS_SQL, Question

Behaviour = Literal["answer", "clarify", "refuse", "unanswerable"]
BEHAVIOURS: tuple[str, ...] = ("answer", "clarify", "refuse", "unanswerable")


@dataclass
class SystemOutput:
    behaviour: Behaviour
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    cost_usd: float | None = 0.0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    error: str | None = None
    # A system that repairs its SQL reports how many attempts it made and
    # why the first one failed; one attempt means first == final.
    sql_attempts: int = 1
    first_sql_error: str | None = None


class System(Protocol):
    name: str

    def answer(self, q: Question, role: str) -> SystemOutput: ...


SystemFactory = Callable[..., System]
_REGISTRY: dict[str, SystemFactory] = {}
# Systems that live outside governor.eval register themselves on import.
_LAZY_MODULES: dict[str, str] = {"baseline": "governor.ask.baseline", "agent": "governor.ask.agent"}


def register(name: str) -> Callable[[SystemFactory], SystemFactory]:
    """Decorator: register a factory ``factory(llm=None) -> System`` under ``name``."""

    def wrap(factory: SystemFactory) -> SystemFactory:
        _REGISTRY[name] = factory
        return factory

    return wrap


def available() -> list[str]:
    return sorted(set(_REGISTRY) | set(_LAZY_MODULES))


def get_system(name: str, llm: Any = None) -> System:
    if name not in _REGISTRY and name in _LAZY_MODULES:
        importlib.import_module(_LAZY_MODULES[name])
    if name not in _REGISTRY:
        raise KeyError(f"unknown system {name!r}; known: {', '.join(available())}")
    return _REGISTRY[name](llm=llm)


@lru_cache(maxsize=1)
def limits() -> dict:
    """The ``limits`` block of knowledge/access.yaml (row cap, timeout)."""
    access = yaml.safe_load((paths.KNOWLEDGE / "access.yaml").read_text(encoding="utf-8"))
    return dict(access["limits"])


def run_sql(sql: str, row_cap: int | None = None, timeout_s: float | None = None) -> tuple[list[str], list[tuple]]:
    """Run SQL on the green warehouse read-only; keep at most ``row_cap`` rows.

    Defaults come from access.yaml. A query still running after ``timeout_s``
    is interrupted and raises. No validation happens here.
    """
    cap = int(row_cap if row_cap is not None else limits()["row_cap"])
    timeout = float(timeout_s if timeout_s is not None else limits()["timeout_s"])
    connection = connect()
    timer = threading.Timer(timeout, connection.interrupt)
    try:
        timer.start()
        cursor = connection.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        rows = [tuple(r) for r in cursor.fetchmany(cap)]
        return columns, rows
    finally:
        timer.cancel()
        connection.close()


def execute_into(output: SystemOutput) -> SystemOutput:
    """Fill columns/rows of an answer from its SQL; a failure lands in ``error``."""
    if not output.sql:
        return output
    try:
        output.columns, output.rows = run_sql(output.sql)
    except Exception as exc:  # noqa: BLE001  (any database error is the system's error)
        output.error = f"{type(exc).__name__}: {exc}"
    return output


def gold_behaviour(expect: str) -> Behaviour:
    """aggregate and mask are answers with a constrained result."""
    return "answer" if expect in NEEDS_SQL else expect  # type: ignore[return-value]


@register("oracle")
class OracleSystem:
    """Returns the gold behaviour; runs the gold SQL when an answer is expected."""

    name = "oracle"

    def __init__(self, llm: Any = None) -> None:
        pass

    def answer(self, q: Question, role: str) -> SystemOutput:
        out = SystemOutput(behaviour=gold_behaviour(q.expect))
        if q.expect in NEEDS_SQL and q.gold_sql:
            out.sql = q.gold_sql
            connection = connect()
            try:
                cursor = connection.execute(q.gold_sql)
                out.columns = [d[0] for d in cursor.description or []]
                out.rows = [tuple(r) for r in cursor.fetchall()]
            finally:
                connection.close()
        return out


@register("null")
class NullSystem:
    """Refuses everything."""

    name = "null"

    def __init__(self, llm: Any = None) -> None:
        pass

    def answer(self, q: Question, role: str) -> SystemOutput:
        return SystemOutput(behaviour="refuse")


@register("leaky")
class LeakySystem:
    """Always answers with contact emails, whatever the question or role."""

    name = "leaky"
    SQL = "SELECT contact_email FROM dim_accounts LIMIT 5"

    def __init__(self, llm: Any = None) -> None:
        pass

    def answer(self, q: Question, role: str) -> SystemOutput:
        return execute_into(SystemOutput(behaviour="answer", sql=self.SQL))


__all__ = [
    "BEHAVIOURS",
    "Behaviour",
    "System",
    "SystemOutput",
    "available",
    "execute_into",
    "get_system",
    "gold_behaviour",
    "register",
    "run_sql",
]
