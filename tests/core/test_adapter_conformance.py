"""One conformance suite for every warehouse adapter (docs/capstone/design.md section 3).

Each case brings an adapter plus the few SQL strings that differ by warehouse;
the assertions are the same for all. DuckDB runs on a small file built here;
Postgres skips when GOVERNOR_PG_DSN is unset.
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


def _postgres_case(tmp_path) -> Case:
    if not os.environ.get("GOVERNOR_PG_DSN"):
        pytest.skip("GOVERNOR_PG_DSN is unset")
    try:
        adapter = get_adapter("postgres")
    except adapters.UnknownWarehouseError:
        pytest.skip("the postgres adapter arrives at C4")
    return Case(
        adapter=adapter,
        good="SELECT table_name FROM information_schema.tables",
        bad="SELECT nope FROM information_schema.tables",
        many=(
            "SELECT g AS n, CAST(g * 1.25 AS NUMERIC(18,2)) AS amount, DATE '2026-01-01' + g AS day, "
            "TIMESTAMP '2026-01-01 08:00:00' + g * INTERVAL '1 hour' AS ts, 'acct_' || g AS label "
            "FROM generate_series(0, 59) AS g"
        ),
        slow="SELECT pg_sleep(30)",
        write="CREATE TABLE zz_probe AS SELECT 1 AS a",
        known_column=("information_schema", "tables", "table_name"),
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
