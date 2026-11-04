"""CLI: python -m governor.build init --target <dir> --project-name <name>."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import psycopg

from governor.build.workspace import build_dsn, init_target, write_sources


def raw_tables() -> dict[str, list[str]]:
    """Tables and columns of schema ``raw``, read as the build login."""
    tables: dict[str, list[str]] = {}
    with psycopg.connect(build_dsn()) as conn:
        rows = conn.execute(
            "select c.table_name, c.column_name from information_schema.columns c "
            "join information_schema.tables t using (table_schema, table_name) "
            "where c.table_schema = 'raw' and t.table_type = 'BASE TABLE' "
            "order by c.table_name, c.ordinal_position"
        ).fetchall()
    for table, column in rows:
        tables.setdefault(table, []).append(column)
    return tables


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="governor.build")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create the target dbt project and write models/sources.yml")
    p.add_argument("--target", required=True, type=Path)
    p.add_argument("--project-name", required=True)
    args = ap.parse_args(argv)
    try:
        tables = raw_tables()
    except Exception as e:  # noqa: BLE001 - one readable line, never the connection string
        first = str(e).splitlines()[0] if str(e) else ""
        print(f"cannot read raw: {type(e).__name__}: {first}", file=sys.stderr)
        return 1
    init_target(args.target, args.project_name)
    write_sources(args.target, tables)
    print(json.dumps({"target": str(args.target), "tables": sorted(tables)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
