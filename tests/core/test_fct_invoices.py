"""fct_invoices.days_outstanding is measured against the build's as_of, not the wall clock."""

from __future__ import annotations

from datetime import timezone

from governor.core import paths
from governor.core.warehouse import connect

SQL = paths.DBT_PROJECT / "models" / "marts" / "fct_invoices.sql"


def test_sql_reads_the_as_of_var_and_never_the_clock():
    text = SQL.read_text(encoding="utf-8").lower()
    assert "var(\"as_of\")" in text or "var('as_of')" in text
    for banned in ("now()", "current_date", "current_timestamp", "get_current_timestamp"):
        assert banned not in text


def test_days_outstanding_counts_days_from_issue_to_as_of():
    as_of = paths.as_of().astimezone(timezone.utc).date()
    connection = connect()
    try:
        rows = connection.execute(
            "select issued_at, is_fully_paid, days_outstanding from fct_invoices"
        ).fetchall()
    finally:
        connection.close()
    assert rows
    open_rows = [row for row in rows if not row[1]]
    paid_rows = [row for row in rows if row[1]]
    assert open_rows and paid_rows
    for issued_at, _paid, days in open_rows:
        assert days == (as_of - issued_at.date()).days
    assert {days for _issued, _paid, days in paid_rows} == {0}
