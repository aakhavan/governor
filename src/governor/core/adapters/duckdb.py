"""DuckDB warehouse adapter: the green billing mart, read-only.

Every call opens its own connection through ``warehouse.connect()`` (read-only,
marts first on the search path), switches off external access and extension
autoloading, locks the configuration, and closes the connection afterwards
(Windows keeps a file lock while it is open). Timeouts interrupt the
connection from a timer thread.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Callable, Iterator

import duckdb

from governor.core import warehouse
from governor.core.adapters.base import (
    ColumnInfo,
    DryRun,
    QueryError,
    QueryTimeout,
    error_message,
    json_safe,
)

# Applied in order to every connection; lock_configuration last, so a query
# cannot switch any of them back on.
HARDENING = (
    "SET enable_external_access = false",
    "SET autoinstall_known_extensions = false",
    "SET autoload_known_extensions = false",
    "SET allow_community_extensions = false",
    "SET lock_configuration = true",
)

_SYSTEM_SCHEMAS = ("information_schema", "pg_catalog")


def open_connection(database: str | Path | None = None) -> duckdb.DuckDBPyConnection:
    """A hardened read-only connection to ``database`` (default: the green warehouse)."""
    connection = warehouse.connect(database)
    try:
        for statement in HARDENING:
            connection.execute(statement)
    except Exception:
        connection.close()
        raise
    return connection


@contextmanager
def deadline(connection: Any, timeout_s: float) -> Iterator[None]:
    """Interrupt ``connection`` after ``timeout_s``; a duckdb error after that is a QueryTimeout."""
    fired = threading.Event()

    def interrupt() -> None:
        fired.set()
        connection.interrupt()

    timer = threading.Timer(timeout_s, interrupt)
    timer.daemon = True
    timer.start()
    try:
        yield
    except duckdb.Error:
        if fired.is_set():
            raise QueryTimeout(f"query interrupted after {timeout_s}s") from None
        raise
    finally:
        timer.cancel()


class DuckDBAdapter:
    name = "duckdb"
    dialect = "duckdb"

    def __init__(
        self,
        database: str | Path | None = None,
        connect: Callable[[], Any] | None = None,
    ) -> None:
        self.database = database
        self._connect = connect or (lambda: open_connection(self.database))

    def dry_run(self, sql: str, *, timeout_s: float) -> DryRun:
        try:
            connection = self._connect()
        except duckdb.Error as error:
            return DryRun(ok=False, error=error_message(error))
        try:
            with deadline(connection, timeout_s):
                connection.execute(f"EXPLAIN {sql}").fetchall()
            return DryRun(ok=True)
        except duckdb.Error as error:
            return DryRun(ok=False, error=error_message(error))
        finally:
            connection.close()

    def run(
        self, sql: str, *, timeout_s: float, row_cap: int, native: bool = False
    ) -> tuple[list[str], list[list[Any]]]:
        try:
            connection = self._connect()
        except duckdb.Error as error:
            raise QueryError(error_message(error)) from None
        try:
            with deadline(connection, timeout_s):
                cursor = connection.execute(sql)
                columns = [d[0] for d in cursor.description or []]
                rows = cursor.fetchmany(row_cap) if row_cap > 0 else []
        except duckdb.Error as error:
            raise QueryError(error_message(error)) from None
        finally:
            connection.close()
        if native:
            return columns, [list(row) for row in rows]
        return columns, [[json_safe(v) for v in row] for row in rows]

    def list_columns(self, schemas: list[str] | None = None) -> list[ColumnInfo]:
        query = (
            "SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_catalog = current_database()"
        )
        params: list[Any] = []
        if schemas:
            query += f" AND table_schema IN ({', '.join('?' for _ in schemas)})"
            params.extend(schemas)
        else:
            query += f" AND table_schema NOT IN ({', '.join('?' for _ in _SYSTEM_SCHEMAS)})"
            params.extend(_SYSTEM_SCHEMAS)
        query += " ORDER BY table_schema, table_name, ordinal_position"
        connection = self._connect()
        try:
            rows = connection.execute(query, params).fetchall()
        except duckdb.Error as error:
            raise QueryError(error_message(error)) from None
        finally:
            connection.close()
        return [ColumnInfo(schema=s, table=t, column=c, data_type=d) for s, t, c, d in rows]

    def close(self) -> None:
        """Nothing to release: every call closes its own connection."""
