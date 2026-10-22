"""Load the raw CSVs into a DuckDB warehouse.

The connection is closed before this function returns. On Windows DuckDB
locks the file, and dbt has to open the same path afterwards.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb

import generate_raw
from governor.core import paths

FIXTURE_DIR = paths.FIXTURE
WAREHOUSE = FIXTURE_DIR / "billing_mart" / "warehouse.duckdb"
RAW_DIR = FIXTURE_DIR / "raw"

TIMESTAMP_FORMAT = "%Y-%m-%d %H:%M:%S"


def _csv(path: Path, columns: tuple[str, ...]) -> str:
    mapping = ", ".join(f"'{column}': 'VARCHAR'" for column in columns)
    posix = path.resolve().as_posix().replace("'", "''")
    return (
        f"read_csv('{posix}', header=true, nullstr='', "
        f"columns={{{mapping}}})"
    )


def _timestamp(column: str) -> str:
    return f"strptime({column}, '{TIMESTAMP_FORMAT}')"


def _as_utc_naive(value: datetime) -> datetime:
    if value.tzinfo is None:
        value = value.astimezone()
    return value.astimezone(timezone.utc).replace(tzinfo=None, microsecond=0)


def _replace_file(warehouse: Path) -> None:
    warehouse.parent.mkdir(parents=True, exist_ok=True)
    for path in (warehouse, Path(str(warehouse) + ".wal")):
        if path.exists():
            path.unlink()


def load(warehouse: Path, raw_dir: Path, loaded_at: datetime) -> dict[str, int]:
    """Create schema raw and replace its tables. Closes the connection."""
    _replace_file(warehouse)
    # dbt treats a timezone-naive timestamp as UTC when it computes
    # freshness age. Local wall time would be shifted by the UTC offset.
    stamp = _as_utc_naive(loaded_at)
    connection = duckdb.connect(str(warehouse))
    try:
        connection.execute("create schema if not exists raw")
        _load_plans(connection, raw_dir / "plans.csv")
        _load_accounts(connection, raw_dir / "accounts.csv", stamp)
        _load_subscriptions(connection, raw_dir / "subscriptions.csv")
        _load_invoices(connection, raw_dir / "invoices.csv")
        _load_payments(connection, raw_dir / "payments.csv", stamp)
        counts = {}
        for name in ("plans", "accounts", "subscriptions", "invoices", "payments"):
            counts[name] = connection.execute(f"select count(*) from raw.{name}").fetchone()[0]
        return counts
    finally:
        connection.close()


def _load_plans(connection: duckdb.DuckDBPyConnection, path: Path) -> None:
    connection.execute(
        f"""
        create or replace table raw.plans as
        select
            plan_id::varchar as plan_id,
            plan_name::varchar as plan_name,
            cast(monthly_price_eur as decimal(18, 2)) as monthly_price_eur
        from {_csv(path, generate_raw.PLAN_COLUMNS)}
        """
    )


def _load_accounts(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    loaded_at: datetime,
) -> None:
    connection.execute(
        f"""
        create or replace table raw.accounts as
        select
            account_id::varchar as account_id,
            company_name::varchar as company_name,
            contact_name::varchar as contact_name,
            contact_email::varchar as contact_email,
            country::varchar as country,
            {_timestamp("created_at")} as created_at,
            ?::timestamp as _loaded_at
        from {_csv(path, generate_raw.ACCOUNT_COLUMNS)}
        """,
        [loaded_at],
    )


def _load_subscriptions(connection: duckdb.DuckDBPyConnection, path: Path) -> None:
    connection.execute(
        f"""
        create or replace table raw.subscriptions as
        select
            subscription_id::varchar as subscription_id,
            account_id::varchar as account_id,
            plan_id::varchar as plan_id,
            status::varchar as status,
            {_timestamp("started_at")} as started_at,
            {_timestamp("cancelled_at")} as cancelled_at
        from {_csv(path, generate_raw.SUBSCRIPTION_COLUMNS)}
        """
    )


def _load_invoices(connection: duckdb.DuckDBPyConnection, path: Path) -> None:
    connection.execute(
        f"""
        create or replace table raw.invoices as
        select
            invoice_id::varchar as invoice_id,
            subscription_id::varchar as subscription_id,
            account_id::varchar as account_id,
            {_timestamp("issued_at")} as issued_at,
            cast(amount_eur as decimal(18, 2)) as amount_eur,
            status::varchar as status
        from {_csv(path, generate_raw.INVOICE_COLUMNS)}
        """
    )


def _load_payments(
    connection: duckdb.DuckDBPyConnection,
    path: Path,
    loaded_at: datetime,
) -> None:
    connection.execute(
        f"""
        create or replace table raw.payments as
        select
            payment_id::varchar as payment_id,
            invoice_id::varchar as invoice_id,
            {_timestamp("paid_at")} as paid_at,
            cast(amount_eur as decimal(18, 2)) as amount_eur,
            method::varchar as method,
            card_last4::varchar as card_last4,
            ?::timestamp as _loaded_at
        from {_csv(path, generate_raw.PAYMENT_COLUMNS)}
        """,
        [loaded_at],
    )


def main() -> None:
    loaded_at = datetime.now().replace(microsecond=0)
    counts = load(WAREHOUSE, RAW_DIR, loaded_at)
    for name, count in counts.items():
        print(f"raw.{name} {count}")


if __name__ == "__main__":
    main()
