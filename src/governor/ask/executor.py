"""Read-only executor: the second half of the security boundary.

The validator decides what may run; this module makes sure that even a wrong
validator cannot write, read files or run forever. ``execute`` validates,
dry-runs the rewritten SQL with ``EXPLAIN`` and runs it with the access.yaml
limits. Every connection comes from ``warehouse.connect()`` (read-only), has
external access and extension autoloading switched off and its configuration
locked, and is always closed.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import duckdb

from governor.ask.policy import Policy
from governor.ask.validator import validate
from governor.core import warehouse

# Applied in order to every connection; lock_configuration last, so a query
# cannot switch any of them back on.
_HARDENING = (
    "SET enable_external_access = false",
    "SET autoinstall_known_extensions = false",
    "SET autoload_known_extensions = false",
    "SET allow_community_extensions = false",
    "SET lock_configuration = true",
)


class QueryError(Exception):
    """The database refused or failed the query."""


class QueryTimeout(QueryError):
    """The query ran longer than the timeout and was interrupted."""


@dataclass
class DryRun:
    ok: bool
    error: str | None = None


@dataclass
class ExecResult:
    ok: bool
    codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    row_count: int = 0


def _open(database: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    connection = warehouse.connect(database)
    try:
        for statement in _HARDENING:
            connection.execute(statement)
    except Exception:
        connection.close()
        raise
    return connection


def dry_run(sql: str, *, database: str | Path | None = None) -> DryRun:
    """Plan ``sql`` with EXPLAIN on a read-only connection; nothing is executed."""
    try:
        connection = _open(database)
    except duckdb.Error as error:
        return DryRun(ok=False, error=_message(error))
    try:
        connection.execute(f"EXPLAIN {sql}").fetchall()
        return DryRun(ok=True)
    except duckdb.Error as error:
        return DryRun(ok=False, error=_message(error))
    finally:
        connection.close()


def run_readonly(
    sql: str,
    *,
    timeout_s: float,
    row_cap: int,
    database: str | Path | None = None,
) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Run ``sql`` read-only and return (columns, at most ``row_cap`` rows).

    Raises QueryTimeout when the query outlives ``timeout_s`` and QueryError on
    any database error (a write on the read-only connection included).
    """
    try:
        connection = _open(database)
    except duckdb.Error as error:
        raise QueryError(_message(error)) from None
    fired = threading.Event()

    def interrupt() -> None:
        fired.set()
        connection.interrupt()

    timer = threading.Timer(timeout_s, interrupt)
    timer.daemon = True
    timer.start()
    try:
        cursor = connection.execute(sql)
        columns = [d[0] for d in cursor.description or []]
        rows = cursor.fetchmany(row_cap) if row_cap > 0 else []
        return columns, rows
    except duckdb.Error as error:
        if fired.is_set():
            raise QueryTimeout(f"query interrupted after {timeout_s}s") from None
        raise QueryError(_message(error)) from None
    finally:
        timer.cancel()
        connection.close()


def execute(
    sql: str,
    role: str,
    *,
    access_path: Path | None = None,
    meta_path: Path | None = None,
    database: str | Path | None = None,
) -> ExecResult:
    """Validate ``sql`` for ``role``, dry-run the rewritten SQL, then run it with the role's limits."""
    checked = validate(sql, role, access_path=access_path, meta_path=meta_path)
    if not checked.ok or checked.sql is None:
        return ExecResult(ok=False, codes=list(checked.codes), reasons=list(checked.reasons))
    policy = Policy.for_role(role, access_path=access_path, meta_path=meta_path)
    safe_sql = checked.sql
    plan = dry_run(safe_sql, database=database)
    if not plan.ok:
        return ExecResult(ok=False, codes=["DRY_RUN_FAILED"], reasons=[plan.error or "EXPLAIN failed"], sql=safe_sql)
    try:
        columns, rows = run_readonly(safe_sql, timeout_s=policy.timeout_s, row_cap=policy.row_cap, database=database)
    except QueryTimeout as error:
        return ExecResult(ok=False, codes=["TIMEOUT"], reasons=[str(error)], sql=safe_sql)
    except QueryError as error:
        return ExecResult(ok=False, codes=["EXEC_ERROR"], reasons=[str(error)], sql=safe_sql)
    return ExecResult(ok=True, sql=safe_sql, columns=columns, rows=rows, row_count=len(rows))


def _message(error: Exception) -> str:
    return str(error).splitlines()[0][:300] if str(error) else type(error).__name__
