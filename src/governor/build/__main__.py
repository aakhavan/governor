"""CLI: python -m governor.build init --target <dir> --project-name <name>
       python -m governor.build profile --schema raw [--policy <file>] [--out <file>]"""

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


def _fail(what: str, e: Exception) -> int:
    """One readable line, never the connection string."""
    first = str(e).splitlines()[0] if str(e) else ""
    print(f"{what}: {type(e).__name__}: {first}", file=sys.stderr)
    return 1


def _init(args: argparse.Namespace) -> int:
    try:
        tables = raw_tables()
    except Exception as e:  # noqa: BLE001
        return _fail("cannot read raw", e)
    init_target(args.target, args.project_name)
    write_sources(args.target, tables)
    print(json.dumps({"target": str(args.target), "tables": sorted(tables)}))
    return 0


def _profile(args: argparse.Namespace) -> int:
    from governor.build.profile import load_policy, profile_schema

    try:
        policy = load_policy(args.policy) if args.policy else None
    except Exception as e:  # noqa: BLE001
        return _fail("cannot read policy", e)
    try:
        profile = profile_schema(build_dsn(), args.schema, policy)
    except Exception as e:  # noqa: BLE001
        return _fail(f"cannot profile {args.schema}", e)
    text = json.dumps(profile)
    if args.out is None:
        print(text)
        return 0
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n", encoding="utf-8")
    print(json.dumps({"out": str(args.out), "schema": args.schema, "tables": len(profile["tables"]),
                      "relationships": len(profile["relationships"]), "pii_policy": bool(policy)}))
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="governor.build")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="create the target dbt project and write models/sources.yml")
    p.add_argument("--target", required=True, type=Path)
    p.add_argument("--project-name", required=True)
    p.set_defaults(func=_init)
    p = sub.add_parser("profile", help="profile a raw schema (counts only for PII columns)")
    p.add_argument("--schema", default="raw")
    p.add_argument("--policy", type=Path, help="column -> PII tag file, e.g. knowledge/shop/policy.yaml")
    p.add_argument("--out", type=Path, help="write the profile here and print a one-line summary")
    p.set_defaults(func=_profile)
    args = ap.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
