"""One conformance suite for every warehouse adapter (docs/capstone/design.md section 3).

Each case brings an adapter plus the few SQL strings that differ by warehouse;
the assertions are the same for all. DuckDB runs on a small file built here;
Postgres runs on a ``conformance`` schema created as admin and skips when
GOVERNOR_PG_DSN or GOVERNOR_PG_ADMIN_DSN is unset.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

import duckdb
import pytest

from governor.ask import executor
from governor.core import adapters
from governor.core.adapters import ColumnInfo, DryRun, QueryError, QueryTimeout, WarehouseAdapter, get_adapter


@dataclass
class Case:
    adapter: WarehouseAdapter
    good: str  # plans and runs
    bad: str  # unknown column: fails to plan
    many: str  # returns at least 50 rows of mixed types (decimal, date, timestamp, text)
    slow: str  # runs far longer than a second
    write: str  # a write the read-only connection refuses
    known_column: tuple[str, str, str]  # (schema, table, column) list_columns must report


def _duckdb_case(tmp_path) -> Case:
    path = tmp_path / "warehouse.duckdb"
    con = duckdb.connect(str(path))
    try:
        con.execute("CREATE SCHEMA marts")
        con.execute(
            "CREATE TABLE marts.invoices AS SELECT range AS invoice_id, "
            "CAST(range * 1.25 AS DECIMAL(18,2)) AS amount_eur, "
            "DATE '2026-01-01' + CAST(range AS INTEGER) AS issued_on, "
            "TIMESTAMP '2026-01-01 08:00:00' + to_hours(CAST(range AS INTEGER)) AS created_at, "
            "'acct_' || range AS account_id FROM range(60)"
        )
    finally:
        con.close()
    return Case(
        adapter=get_adapter("duckdb", database=path),
        good="SELECT account_id FROM invoices",
        bad="SELECT nope FROM invoices",
        many="SELECT invoice_id, amount_eur, issued_on, created_at, account_id FROM invoices ORDER BY invoice_id",
        slow="SELECT sum(a.range * b.range) FROM range(100000) a, range(100000) b",
        write="CREATE TABLE zz_probe AS SELECT 1 AS a",
        known_column=("marts", "invoices", "amount_eur"),
    )


def _pg_env() -> tuple[str, str]:
    dsn, admin = os.environ.get("GOVERNOR_PG_DSN"), os.environ.get("GOVERNOR_PG_ADMIN_DSN")
    if not dsn or not admin:
        pytest.skip("GOVERNOR_PG_DSN or GOVERNOR_PG_ADMIN_DSN is unset")
    return dsn, admin


def _postgres_conformance_schema(admin_dsn: str) -> None:
    """As admin: a small ``conformance`` schema, readable by governor_ask when that role exists."""
    import psycopg

    with psycopg.connect(admin_dsn, autocommit=True) as c:
        c.execute("CREATE SCHEMA IF NOT EXISTS conformance")
        c.execute(
            "CREATE TABLE IF NOT EXISTS conformance.invoices AS SELECT g AS invoice_id, "
            "CAST(g * 1.25 AS NUMERIC(18,2)) AS amount_eur, 'acct_' || g AS account_id "
            "FROM generate_series(0, 59) AS g"
        )
        if c.execute("SELECT 1 FROM pg_roles WHERE rolname = 'governor_ask'").fetchone():
            c.execute("GRANT USAGE ON SCHEMA conformance TO governor_ask")
            c.execute("GRANT SELECT ON ALL TABLES IN SCHEMA conformance TO governor_ask")


def _postgres_case(tmp_path) -> Case:
    _, admin = _pg_env()
    _postgres_conformance_schema(admin)
    adapter = get_adapter("postgres")
    return Case(
        adapter=adapter,
        good="SELECT account_id FROM conformance.invoices",
        bad="SELECT nope FROM conformance.invoices",
        many=(
            "SELECT g AS n, CAST(g * 1.25 AS NUMERIC(18,2)) AS amount, DATE '2026-01-01' + g AS day, "
            "TIMESTAMP '2026-01-01 08:00:00' + g * INTERVAL '1 hour' AS ts, 'acct_' || g AS label "
            "FROM generate_series(0, 59) AS g"
        ),
        slow="SELECT pg_sleep(30)",
        write="CREATE TABLE conformance.zz_probe AS SELECT 1 AS a",
        known_column=("conformance", "invoices", "amount_eur"),
    )


@pytest.fixture(params=["duckdb", "postgres"])
def case(request, tmp_path):
    built = {"duckdb": _duckdb_case, "postgres": _postgres_case}[request.param](tmp_path)
    yield built
    built.adapter.close()


def test_names_and_protocol(case):
    assert isinstance(case.adapter, WarehouseAdapter)
    assert case.adapter.name in {"duckdb", "postgres"}
    assert case.adapter.dialect == adapters.dialect(case.adapter.name)


def test_dry_run_good_and_bad(case):
    good = case.adapter.dry_run(case.good, timeout_s=5)
    assert isinstance(good, DryRun) and good.ok is True and good.error is None
    bad = case.adapter.dry_run(case.bad, timeout_s=5)
    assert bad.ok is False and bad.error and "nope" in bad.error.lower()


def test_run_honours_row_cap(case):
    columns, rows = case.adapter.run(case.many, timeout_s=10, row_cap=7)
    assert len(columns) == 5 and len(rows) == 7
    assert all(isinstance(row, list) and len(row) == 5 for row in rows)
    _, none = case.adapter.run(case.many, timeout_s=10, row_cap=0)
    assert none == []


def test_values_are_json_safe(case):
    _, rows = case.adapter.run(case.many, timeout_s=10, row_cap=3)
    json.dumps(rows)
    amount, day, ts = rows[1][1], rows[1][2], rows[1][3]
    assert amount == "1.25"
    assert day == "2026-01-02"
    assert ts.startswith("2026-01-01") and "09:00:00" in ts


def test_native_values_are_kept_on_request(case):
    _, rows = case.adapter.run(case.many, timeout_s=10, row_cap=2, native=True)
    assert isinstance(rows[1][1], Decimal) and rows[1][1] == Decimal("1.25")
    assert isinstance(rows[1][2], date) and isinstance(rows[1][3], datetime)


def test_timeout_raises_query_timeout(case):
    with pytest.raises(QueryTimeout):
        case.adapter.run(case.slow, timeout_s=0.5, row_cap=1)


def test_timeout_is_a_query_error(case):
    assert issubclass(QueryTimeout, QueryError)


def test_write_raises_query_error(case):
    with pytest.raises(QueryError) as caught:
        case.adapter.run(case.write, timeout_s=5, row_cap=1)
    assert not isinstance(caught.value, QueryTimeout)


def test_list_columns_returns_real_columns(case):
    schema, table, column = case.known_column
    columns = case.adapter.list_columns()
    assert columns and all(isinstance(c, ColumnInfo) for c in columns)
    assert any((c.schema, c.table, c.column) == (schema, table, column) and c.data_type for c in columns)
    only = case.adapter.list_columns([schema])
    assert only and {c.schema for c in only} == {schema}


def test_unknown_adapter_name_raises(monkeypatch):
    with pytest.raises(adapters.UnknownWarehouseError, match="nosuch"):
        get_adapter("nosuch")
    monkeypatch.setenv("GOVERNOR_WAREHOUSE", "nosuch")
    with pytest.raises(adapters.UnknownWarehouseError, match="GOVERNOR_WAREHOUSE"):
        get_adapter()


def test_default_adapter_is_duckdb(monkeypatch):
    monkeypatch.delenv("GOVERNOR_WAREHOUSE", raising=False)
    adapter = get_adapter()
    try:
        assert adapter.name == "duckdb" and adapters.dialect() == "duckdb"
    finally:
        adapter.close()


def test_executor_keeps_reexporting_errors():
    assert executor.QueryTimeout is QueryTimeout and executor.QueryError is QueryError
    assert executor.DryRun is DryRun


# -- Postgres roles (design section 4): the role comes from the caller, never from SQL --


def test_postgres_refuses_unlisted_role_before_connecting(monkeypatch):
    from governor.core.adapters import postgres

    def no_connect(*_a, **_k):
        raise AssertionError("connected before the role check")

    monkeypatch.setattr(postgres.psycopg, "connect", no_connect)
    adapter = get_adapter("postgres", dsn="postgresql://nobody@localhost:1/none", allowed_roles=["governor_analyst"])
    for role in ("governor_admin", "governor_analyst; RESET ROLE", ""):
        with pytest.raises(QueryError, match="not allowed"):
            adapter.run("SELECT 1", timeout_s=1, row_cap=1, role=role)
        with pytest.raises(QueryError, match="not allowed"):
            adapter.dry_run("SELECT 1", timeout_s=1, role=role)
    with pytest.raises(QueryError, match="not allowed"):
        get_adapter("postgres", dsn="postgresql://x@localhost:1/none").run(
            "SELECT 1", timeout_s=1, row_cap=1, role="governor_analyst"
        )


def test_postgres_without_dsn_is_a_query_error(monkeypatch):
    monkeypatch.delenv("GOVERNOR_PG_DSN", raising=False)
    with pytest.raises(QueryError, match="GOVERNOR_PG_DSN"):
        get_adapter("postgres").run("SELECT 1", timeout_s=1, row_cap=1)


def test_postgres_allowed_role_is_set():
    _pg_env()
    adapter = get_adapter("postgres", allowed_roles=["governor_analyst"])
    try:
        _, rows = adapter.run("SELECT current_user", timeout_s=5, row_cap=1, role="governor_analyst")
        assert rows == [["governor_analyst"]]
        assert adapter.dry_run("SELECT 1", timeout_s=5, role="governor_analyst").ok
        _, rows = adapter.run("SELECT current_setting('transaction_read_only')", timeout_s=5, row_cap=1)
        assert rows == [["on"]]
    finally:
        adapter.close()


def test_postgres_dry_run_runs_one_statement_only():
    """A semicolon in dry_run SQL cannot SET ROLE outside allowed_roles or clear the timeout."""
    import time

    _pg_env()
    adapter = get_adapter("postgres", allowed_roles=["governor_analyst"])
    try:
        # If the role switch applied, the cast error would name governor_finance_admin.
        smuggled_role = "SELECT 1; SET ROLE governor_finance_admin; SELECT CAST(current_user AS int)"
        try:
            result = adapter.dry_run(smuggled_role, timeout_s=5, role="governor_analyst")
            assert result.ok is False
            message = result.error or ""
        except QueryError as error:
            message = str(error)
        assert "governor_finance_admin" not in message

        # If the timeout were cleared, the sleep would run its full 3 s.
        smuggled_timeout = "SELECT 1; SET statement_timeout = 0; SELECT pg_sleep(3)"
        started = time.monotonic()
        try:
            assert adapter.dry_run(smuggled_timeout, timeout_s=0.5).ok is False
        except QueryError:
            pass
        assert time.monotonic() - started < 2

        _, rows = adapter.run("SELECT current_user", timeout_s=5, row_cap=1)
        assert rows != [["governor_finance_admin"]]
    finally:
        adapter.close()


def test_postgres_run_runs_one_statement_only():
    """A semicolon in run() SQL cannot clear the timeout or SET ROLE; QueryError is a pass."""
    import time

    _pg_env()
    adapter = get_adapter("postgres", allowed_roles=["governor_analyst"])
    try:
        # If the timeout were cleared, the sleep would run its full 3 s.
        smuggled_timeout = "SELECT 1; SET statement_timeout = 0; SELECT pg_sleep(3)"
        started = time.monotonic()
        try:
            columns, _ = adapter.run(smuggled_timeout, timeout_s=0.5, row_cap=1)
            assert "pg_sleep" not in columns
        except QueryError:
            pass
        assert time.monotonic() - started < 2

        smuggled_role = "SELECT current_user; SET ROLE governor_finance_admin"
        try:
            _, rows = adapter.run(smuggled_role, timeout_s=5, row_cap=1, role="governor_analyst")
            assert rows != [["governor_finance_admin"]]
        except QueryError:
            pass

        # A literal percent sign is SQL, not a placeholder.
        _, rows = adapter.run("SELECT '100%' AS p", timeout_s=5, row_cap=1)
        assert rows == [["100%"]]
    finally:
        adapter.close()
