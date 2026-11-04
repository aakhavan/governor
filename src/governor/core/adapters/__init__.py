"""Warehouse adapters: the one way ask reaches a warehouse.

``get_adapter()`` picks the adapter by name, from the argument or env
``GOVERNOR_WAREHOUSE`` (default ``duckdb``). Connection settings come from the
environment only. governor's own stores (meta, traces, checkpoints) are not
warehouses and do not come through here.
"""

from __future__ import annotations

import os
from typing import Any

from governor.core.adapters.base import (
    ColumnInfo,
    DryRun,
    QueryError,
    QueryTimeout,
    UnknownWarehouseError,
    WarehouseAdapter,
)

ENV = "GOVERNOR_WAREHOUSE"
DEFAULT = "duckdb"
# name -> sqlglot dialect; the validator needs the dialect without opening anything.
DIALECTS = {"duckdb": "duckdb", "postgres": "postgres"}

__all__ = [
    "ColumnInfo",
    "DryRun",
    "QueryError",
    "QueryTimeout",
    "UnknownWarehouseError",
    "WarehouseAdapter",
    "dialect",
    "get_adapter",
    "warehouse_name",
]


def warehouse_name(name: str | None = None) -> str:
    """The adapter name: ``name``, else env GOVERNOR_WAREHOUSE, else duckdb; unknown names raise."""
    chosen = (name or os.environ.get(ENV) or DEFAULT).strip().lower()
    if chosen not in DIALECTS:
        known = ", ".join(sorted(DIALECTS))
        raise UnknownWarehouseError(f"unknown warehouse {chosen!r} (from {'argument' if name else ENV}); known: {known}")
    return chosen


def dialect(name: str | None = None) -> str:
    """The sqlglot dialect of the chosen warehouse."""
    return DIALECTS[warehouse_name(name)]


def get_adapter(name: str | None = None, **options: Any) -> WarehouseAdapter:
    """The adapter for ``name`` (see ``warehouse_name``); ``options`` go to its constructor."""
    chosen = warehouse_name(name)
    if chosen == "duckdb":
        from governor.core.adapters.duckdb import DuckDBAdapter

        return DuckDBAdapter(**options)
    if chosen == "postgres":
        from governor.core.adapters.postgres import PostgresAdapter

        return PostgresAdapter(**options)
    raise UnknownWarehouseError(f"no adapter for {chosen!r}")  # pragma: no cover - DIALECTS guards this
