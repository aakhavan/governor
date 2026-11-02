"""Read-only executor: the second half of the security boundary.

The validator decides what may run; this module makes sure that even a wrong
validator cannot write, read files or run forever. ``execute`` validates,
dry-runs the rewritten SQL and runs it with the access.yaml limits. The
warehouse is reached only through ``governor.core.adapters``: every
connection is read-only, hardened, timed and closed by the adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

from governor.ask.policy import ACCESS_PATH, Policy
from governor.ask.validator import validate
from governor.core import adapters
from governor.core.adapters import DryRun, QueryError, QueryTimeout, WarehouseAdapter
from governor.core.adapters import duckdb as duckdb_adapter

__all__ = ["DryRun", "ExecResult", "QueryError", "QueryTimeout", "dry_run", "execute", "run_readonly"]


@dataclass
class ExecResult:
    ok: bool
    codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    sql: str | None = None
    columns: list[str] = field(default_factory=list)
    rows: list[tuple[Any, ...]] = field(default_factory=list)
    row_count: int = 0


def _open(database: str | Path | None = None):
    """A hardened read-only DuckDB connection (the DuckDB adapter opens every connection this way)."""
    return duckdb_adapter.open_connection(database)


def _adapter(database: str | Path | None) -> WarehouseAdapter:
    name = adapters.warehouse_name()
    if name == "duckdb":
        # Looked up at call time, so a test can swap _open for a stub connection.
        return adapters.get_adapter(name, database=database, connect=lambda: _open(database))
    return adapters.get_adapter(name)


def _policy_timeout(access_path: Path | None = None) -> float:
    """``limits.timeout_s`` from access.yaml (the limits are the same for every role)."""
    access = yaml.safe_load(Path(access_path or ACCESS_PATH).read_text(encoding="utf-8"))
    return float(access["limits"]["timeout_s"])


def dry_run(sql: str, *, timeout_s: float | None = None, database: str | Path | None = None) -> DryRun:
    """Plan ``sql`` (EXPLAIN) on a read-only connection; nothing is executed.

    Raises QueryTimeout when planning outlives ``timeout_s`` (same timer as
    ``run_readonly``). Without ``timeout_s`` the access.yaml limit applies, so a
    dry run is never untimed.
    """
    if timeout_s is None:
        timeout_s = _policy_timeout()
    adapter = _adapter(database)
    try:
        return adapter.dry_run(sql, timeout_s=timeout_s)
    finally:
        adapter.close()


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
    adapter = _adapter(database)
    try:
        columns, rows = adapter.run(sql, timeout_s=timeout_s, row_cap=row_cap, native=True)
    finally:
        adapter.close()
    return columns, [tuple(row) for row in rows]


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
    try:
        plan = dry_run(safe_sql, timeout_s=policy.timeout_s, database=database)
        if not plan.ok:
            return ExecResult(ok=False, codes=["DRY_RUN_FAILED"], reasons=[plan.error or "EXPLAIN failed"], sql=safe_sql)
        columns, rows = run_readonly(safe_sql, timeout_s=policy.timeout_s, row_cap=policy.row_cap, database=database)
    except QueryTimeout as error:
        return ExecResult(ok=False, codes=["TIMEOUT"], reasons=[str(error)], sql=safe_sql)
    except QueryError as error:
        return ExecResult(ok=False, codes=["EXEC_ERROR"], reasons=[str(error)], sql=safe_sql)
    return ExecResult(ok=True, sql=safe_sql, columns=columns, rows=rows, row_count=len(rows))
