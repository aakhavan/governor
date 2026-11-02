"""Load the 9 Olist CSVs into schema `raw` (all columns text plus _loaded_at). Typing happens later in silver.

Usage: python testbed/load_olist.py --source <dir> [--dsn <dsn>]   (DSN defaults to env GOVERNOR_PG_DSN)
Prints one JSON line {"<table>": rows, ...}.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

EXPECTED: dict[str, list[str]] = {
    "olist_customers_dataset.csv": ["customer_id", "customer_unique_id", "customer_zip_code_prefix", "customer_city", "customer_state"],
    "olist_geolocation_dataset.csv": ["geolocation_zip_code_prefix", "geolocation_lat", "geolocation_lng", "geolocation_city", "geolocation_state"],
    "olist_order_items_dataset.csv": ["order_id", "order_item_id", "product_id", "seller_id", "shipping_limit_date", "price", "freight_value"],
    "olist_order_payments_dataset.csv": ["order_id", "payment_sequential", "payment_type", "payment_installments", "payment_value"],
    "olist_order_reviews_dataset.csv": ["review_id", "order_id", "review_score", "review_comment_title", "review_comment_message", "review_creation_date", "review_answer_timestamp"],
    "olist_orders_dataset.csv": ["order_id", "customer_id", "order_status", "order_purchase_timestamp", "order_approved_at", "order_delivered_carrier_date", "order_delivered_customer_date", "order_estimated_delivery_date"],
    "olist_products_dataset.csv": ["product_id", "product_category_name", "product_name_lenght", "product_description_lenght", "product_photos_qty", "product_weight_g", "product_length_cm", "product_height_cm", "product_width_cm"],
    "olist_sellers_dataset.csv": ["seller_id", "seller_zip_code_prefix", "seller_city", "seller_state"],
    "product_category_name_translation.csv": ["product_category_name", "product_category_name_english"],
}


class HeaderError(Exception):
    pass


def validate_source(source: Path) -> None:
    """Raise HeaderError naming every missing file or header difference."""
    problems: list[str] = []
    for name, want in EXPECTED.items():
        p = source / name
        if not p.is_file():
            problems.append(f"{name}: file missing")
            continue
        with p.open(newline="", encoding="utf-8-sig") as f:
            got = next(csv.reader(f), [])
        if got != want:
            missing = [c for c in want if c not in got]
            extra = [c for c in got if c not in want]
            detail = f"missing columns {missing}, unexpected columns {extra}" if (missing or extra) else "same columns in a different order"
            problems.append(f"{name}: header differs ({detail}); expected {want}, got {got}")
    if problems:
        raise HeaderError("Olist source check failed:\n  " + "\n  ".join(problems))


def load(source: Path, dsn: str) -> dict[str, int]:
    import psycopg
    from psycopg import sql

    validate_source(source)
    counts: dict[str, int] = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute("CREATE SCHEMA IF NOT EXISTS raw")
        for name, cols in EXPECTED.items():
            table = name.removesuffix(".csv")
            ident = sql.Identifier("raw", table)
            col_defs = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in cols)
            col_list = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
            with conn.transaction():
                conn.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} ({}, _loaded_at timestamptz NOT NULL DEFAULT now())").format(ident, col_defs))
                conn.execute(sql.SQL("TRUNCATE {}").format(ident))
                with conn.cursor() as cur:
                    with cur.copy(sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(ident, col_list)) as cp:
                        with (source / name).open("rb") as f:
                            data = f.read()
                        if data.startswith(b"\xef\xbb\xbf"):
                            data = data[3:]
                        cp.write(data)
                counts[table] = conn.execute(sql.SQL("SELECT count(*) FROM {}").format(ident)).fetchone()[0]
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--dsn", default=None)
    args = ap.parse_args(argv)
    dsn = args.dsn or os.environ.get("GOVERNOR_PG_DSN")
    try:
        validate_source(args.source)
    except HeaderError as e:
        print(str(e), file=sys.stderr)
        return 2
    if not dsn:
        print("No DSN: pass --dsn or set GOVERNOR_PG_DSN", file=sys.stderr)
        return 2
    print(json.dumps(load(args.source, dsn)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
