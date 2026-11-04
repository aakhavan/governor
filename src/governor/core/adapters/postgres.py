"""Postgres warehouse adapter (docs/capstone/design.md sections 3 and 4).

Every call opens its own connection from env ``GOVERNOR_PG_DSN``, starts a
read-only transaction (``SET TRANSACTION READ ONLY``, on top of the login's
``default_transaction_read_only``), sets a transaction-local
``statement_timeout`` from the call's ``timeout_s``, optionally switches to a
reader role with ``SET LOCAL ROLE``, and rolls back and closes afterwards.

The role always comes from the caller (later: the token), never from SQL text,
and must be in the ``allowed_roles`` given at construction; anything else is a
``QueryError`` before a connection is opened.
"""

from __future__ import annotations

import os
from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from psycopg import errors, sql

from governor.core.adapters.base import (
    ColumnInfo,
    DryRun,
    QueryError,
    QueryTimeout,
    error_message,
    json_safe,
)

ENV_DSN = "GOVERNOR_PG_DSN"
CONNECT_TIMEOUT_S = 10
_SYSTEM_SCHEMAS = ("information_schema", "pg_catalog")
# Name of the server-side cursor run() declares inside its transaction.
_CURSOR = "governor_run"


def _timeout_ms(timeout_s: float) -> int:
    # statement_timeout = 0 means "no timeout", so never send 0.
    return max(1, int(timeout_s * 1000))


class PostgresAdapter:
    name = "postgres"
    dialect = "postgres"

    def __init__(self, dsn: str | None = None, allowed_roles: Iterable[str] | None = None) -> None:
        self._dsn = dsn
        self.allowed_roles = frozenset(allowed_roles or ())

    # -- connection -----------------------------------------------------------

    def _check_role(self, role: str | None) -> None:
        if role is not None and role not in self.allowed_roles:
            raise QueryError(f"role {role!r} is not allowed")

    def _connect(self) -> psycopg.Connection:
        dsn = self._dsn or os.environ.get(ENV_DSN)
        if not dsn:
            raise QueryError(f"no Postgres connection: set {ENV_DSN}")
        try:
            return psycopg.connect(dsn, autocommit=False, connect_timeout=CONNECT_TIMEOUT_S)
        except psycopg.Error as error:
            raise QueryError(error_message(error)) from None

    @contextmanager
    def _session(self, *, timeout_s: float, role: str | None) -> Iterator[psycopg.Connection]:
        """A read-only transaction with a statement timeout and the role set; always closed."""
        self._check_role(role)
        connection = self._connect()
        try:
            # First statement opens the transaction, so READ ONLY applies to it.
            connection.execute("SET TRANSACTION READ ONLY")
            connection.execute(
                "SELECT set_config('statement_timeout', %s, true)", [f"{_timeout_ms(timeout_s)}ms"]
            )
            if role is not None:
                connection.execute(sql.SQL("SET LOCAL ROLE {}").format(sql.Identifier(role)))
            yield connection
        except errors.QueryCanceled:
            raise QueryTimeout(f"query cancelled after {timeout_s}s") from None
        except psycopg.Error as error:
            raise QueryError(error_message(error)) from None
        finally:
            try:
                connection.rollback()
            except psycopg.Error:
                pass
            connection.close()

    # -- contract -------------------------------------------------------------

    def dry_run(self, sql_text: str, *, timeout_s: float, role: str | None = None) -> DryRun:
        self._check_role(role)  # a refused role is an error, not a failed plan
        try:
            with self._session(timeout_s=timeout_s, role=role) as connection:
                # prepare=True sends one Parse message (extended protocol), so the
                # server refuses a second command instead of running it: no
                # "; SET ROLE ..." or "; SET statement_timeout = 0" after EXPLAIN.
                connection.execute(f"EXPLAIN {sql_text}", prepare=True).fetchall()
        except QueryTimeout:
            raise
        except QueryError as error:
            return DryRun(ok=False, error=str(error))
        return DryRun(ok=True)

    def run(
        self,
        sql_text: str,
        *,
        timeout_s: float,
        row_cap: int,
        native: bool = False,
        role: str | None = None,
    ) -> tuple[list[str], list[list[Any]]]:
        cap = max(0, int(row_cap))
        with self._session(timeout_s=timeout_s, role=role) as connection:
            # A server-side cursor, so the server sends at most row_cap rows. The
            # DECLARE goes out as one prepared statement (extended protocol, no
            # params so a literal "%" stays as written): the server refuses a
            # second command instead of running it, so SQL text cannot add
            # "; SET ROLE ..." or "; SET statement_timeout = 0".
            connection.execute(f"DECLARE {_CURSOR} NO SCROLL CURSOR FOR {sql_text}", prepare=True)
            cursor = connection.execute(f"FETCH FORWARD {cap} FROM {_CURSOR}")
            columns = [d.name for d in cursor.description or []]
            rows = cursor.fetchall()[:cap]
        if native:
            return columns, [list(row) for row in rows]
        return columns, [[json_safe(v) for v in row] for row in rows]

    def list_columns(self, schemas: list[str] | None = None) -> list[ColumnInfo]:
        query = (
            "SELECT table_schema, table_name, column_name, data_type FROM information_schema.columns "
            "WHERE table_catalog = current_database()"
        )
        params: list[Any]
        if schemas:
            query += " AND table_schema = ANY(%s)"
            params = [list(schemas)]
        else:
            query += " AND NOT (table_schema = ANY(%s))"
            params = [list(_SYSTEM_SCHEMAS)]
        query += " ORDER BY table_schema, table_name, ordinal_position"
        with self._session(timeout_s=30, role=None) as connection:
            rows = connection.execute(query, params).fetchall()
        return [ColumnInfo(schema=s, table=t, column=c, data_type=d) for s, t, c, d in rows]

    def close(self) -> None:
        """Nothing to release: every call closes its own connection."""
