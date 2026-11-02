"""The warehouse adapter contract (docs/capstone/design.md section 3).

ask reaches the warehouse only through a ``WarehouseAdapter``: a read-only
dry run, a read-only run with a timeout and a row cap, and the column list
from ``information_schema``. Every adapter raises ``QueryTimeout`` and
``QueryError`` from this module, so callers handle one set of errors.
"""

from __future__ import annotations

import base64
import math
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Protocol, runtime_checkable
from uuid import UUID


class QueryError(Exception):
    """The database refused or failed the query."""


class QueryTimeout(QueryError):
    """The query ran longer than the timeout and was interrupted."""


class UnknownWarehouseError(ValueError):
    """``get_adapter`` was asked for a warehouse it does not know."""


@dataclass
class DryRun:
    ok: bool
    error: str | None = None


@dataclass(frozen=True)
class ColumnInfo:
    schema: str
    table: str
    column: str
    data_type: str


@runtime_checkable
class WarehouseAdapter(Protocol):
    name: str  # "duckdb" | "postgres"
    dialect: str  # sqlglot dialect the validator parses and renders in

    def dry_run(self, sql: str, *, timeout_s: float) -> DryRun:
        """Plan ``sql`` without running it; raises QueryTimeout when planning outlives ``timeout_s``."""
        ...

    def run(
        self, sql: str, *, timeout_s: float, row_cap: int, native: bool = False
    ) -> tuple[list[str], list[list[Any]]]:
        """Run ``sql`` read-only; (columns, at most ``row_cap`` rows).

        Values are JSON-safe unless ``native`` is set, in which case the driver's
        own values (Decimal, date, ...) come back unchanged.
        """
        ...

    def list_columns(self, schemas: list[str] | None = None) -> list[ColumnInfo]:
        """Columns from ``information_schema``, optionally limited to ``schemas``."""
        ...

    def close(self) -> None: ...


def json_safe(value: Any) -> Any:
    """One result value as something ``json.dumps`` accepts: Decimal and dates become strings."""
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Decimal):
        return format(value, "f") if value.is_finite() else None
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return str(value)
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return base64.b64encode(bytes(value)).decode("ascii")
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [json_safe(v) for v in value]
    return str(value)


def error_message(error: BaseException) -> str:
    """The first line of a driver error, short enough to show a user."""
    return str(error).splitlines()[0][:300] if str(error) else type(error).__name__
