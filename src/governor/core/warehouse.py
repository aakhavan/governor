"""Read-only access to the green warehouse.

Every query path opens the warehouse through ``connect()``: read-only, with
the marts schema first on the search path, so ``SELECT ... FROM dim_accounts``
resolves without a schema prefix. Close the connection when done (Windows
keeps a file lock while it is open).
"""

from __future__ import annotations

from pathlib import Path

import duckdb

from governor.core import paths

MARTS_SCHEMA = "marts"


def connect(database: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    """Open the warehouse read-only with ``search_path`` set to the marts schema."""
    path = Path(database) if database is not None else paths.WAREHOUSE
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing. run: uv run python fixture/build_green.py")
    connection = duckdb.connect(str(path), read_only=True)
    try:
        connection.execute(f"SET search_path = '{MARTS_SCHEMA}'")
    except Exception:
        connection.close()
        raise
    return connection
