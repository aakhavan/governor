"""warehouse.connect(): read-only, marts resolve without a schema prefix."""

from __future__ import annotations

import duckdb
import pytest

from governor.core.warehouse import connect

MARTS = ("dim_accounts", "fct_invoices", "fct_revenue_daily", "mrr_monthly")


def test_marts_resolve_unqualified():
    connection = connect()
    try:
        for name in MARTS:
            assert connection.execute(f"select count(*) from {name}").fetchone()[0] > 0
        columns = [
            row[0]
            for row in connection.execute(
                "select column_name from information_schema.columns "
                "where table_schema = 'marts' and table_name = 'dim_accounts'"
            ).fetchall()
        ]
        assert {"account_id", "company_name", "contact_name", "contact_email", "country"} <= set(columns)
    finally:
        connection.close()


@pytest.mark.parametrize(
    "statement",
    [
        "create table zz_probe as select 1 as a",
        "delete from dim_accounts",
        "update fct_invoices set amount_eur = 0",
    ],
)
def test_writes_are_refused(statement):
    connection = connect()
    try:
        with pytest.raises(duckdb.Error):
            connection.execute(statement)
    finally:
        connection.close()


def test_missing_warehouse_names_the_build_command(tmp_path):
    with pytest.raises(FileNotFoundError, match="build_green.py"):
        connect(tmp_path / "nope.duckdb")
