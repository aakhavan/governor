"""Load every *.csv in a folder into schema `raw` (all columns text plus _loaded_at), one transaction per table.

Usage: python testbed/load_csv_dir.py --source <dir> [--dsn <dsn>] [--replace]   (DSN defaults to env GOVERNOR_PG_DSN)

`--replace` first drops every table in `raw`; it is required when `raw` already holds tables, so two datasets never
mix. Only schema `raw` is touched (no CASCADE: a drop that something else depends on fails instead).
Prints one JSON line {"<table>": rows, ...}.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path

from psycopg import sql

SCHEMA = "raw"
LOADED_AT = "_loaded_at"


class LoaderError(Exception):
    pass


def read_tables(source: Path) -> dict[str, list[str]]:
    """{file stem: header} for every *.csv in ``source``, sorted by name."""
    files = sorted(source.glob("*.csv"))
    if not files:
        raise LoaderError(f"no *.csv files in {source}")
    tables: dict[str, list[str]] = {}
    for p in files:
        with p.open(newline="", encoding="utf-8-sig") as f:
            header = next(csv.reader(f), [])
        if not header or any(not c for c in header):
            raise LoaderError(f"{p.name}: empty header or column name")
        if len(set(header)) != len(header) or LOADED_AT in header:
            raise LoaderError(f"{p.name}: duplicate column names or a column named {LOADED_AT}")
        tables[p.stem] = header
    return tables


def check_raw(existing: list[str], replace: bool) -> None:
    """Refuse to load into a non-empty `raw` unless --replace was given."""
    if existing and not replace:
        raise LoaderError(f"schema {SCHEMA} already holds {len(existing)} table(s); pass --replace to drop them first")


def drop_statements(existing: list[str]) -> list[sql.Composed]:
    return [sql.SQL("DROP TABLE {}").format(sql.Identifier(SCHEMA, t)) for t in sorted(existing)]


def create_statement(table: str, cols: list[str]) -> sql.Composed:
    col_defs = sql.SQL(", ").join(sql.SQL("{} text").format(sql.Identifier(c)) for c in cols)
    return sql.SQL("CREATE TABLE {} ({}, {} timestamptz NOT NULL DEFAULT now())").format(
        sql.Identifier(SCHEMA, table), col_defs, sql.Identifier(LOADED_AT))


def copy_statement(table: str, cols: list[str]) -> sql.Composed:
    col_list = sql.SQL(", ").join(sql.Identifier(c) for c in cols)
    return sql.SQL("COPY {} ({}) FROM STDIN WITH (FORMAT csv, HEADER true)").format(
        sql.Identifier(SCHEMA, table), col_list)


def count_statement(table: str) -> sql.Composed:
    return sql.SQL("SELECT count(*) FROM {}").format(sql.Identifier(SCHEMA, table))


LIST_RAW = "SELECT tablename FROM pg_catalog.pg_tables WHERE schemaname = %s ORDER BY tablename"


def load(source: Path, dsn: str, replace: bool = False) -> dict[str, int]:
    import psycopg

    tables = read_tables(source)
    counts: dict[str, int] = {}
    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(SCHEMA)))
        existing = [r[0] for r in conn.execute(LIST_RAW, (SCHEMA,)).fetchall()]
        check_raw(existing, replace)
        if existing:
            with conn.transaction():
                for stmt in drop_statements(existing):
                    conn.execute(stmt)
        for table, cols in tables.items():
            with conn.transaction():
                conn.execute(create_statement(table, cols))
                with conn.cursor() as cur:
                    with cur.copy(copy_statement(table, cols)) as cp:
                        data = (source / f"{table}.csv").read_bytes()
                        if data.startswith(b"\xef\xbb\xbf"):
                            data = data[3:]
                        cp.write(data)
                counts[table] = conn.execute(count_statement(table)).fetchone()[0]
    return counts


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", required=True, type=Path)
    ap.add_argument("--dsn", default=None)
    ap.add_argument("--replace", action="store_true", help=f"drop every table in {SCHEMA} first")
    args = ap.parse_args(argv)
    dsn = args.dsn or os.environ.get("GOVERNOR_PG_DSN")
    try:
        read_tables(args.source)
        if not dsn:
            raise LoaderError("No DSN: pass --dsn or set GOVERNOR_PG_DSN")
        counts = load(args.source, dsn, args.replace)
    except LoaderError as e:
        print(str(e), file=sys.stderr)
        return 2
    print(json.dumps(counts))
    return 0


if __name__ == "__main__":
    sys.exit(main())
