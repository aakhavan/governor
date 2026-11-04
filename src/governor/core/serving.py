"""Serving schemas on the Postgres warehouse (docs/capstone/design.md section 5).

``python -m governor.core.serving apply --source <schema> --policy <file> [--access <file>]``
builds, for every table in the source schema, one view per reader role:

- ``serve_analyst.<table>``: each PII column becomes
  ``encode(sha256(convert_to(salt || value, 'UTF8')), 'hex')``, so equality and
  ``COUNT(DISTINCT ...)`` still work but raw values are not in the view;
- ``serve_finance_admin.<table>``: each PII column becomes the access file's mask
  value unless the access file grants ``table.column`` to ``finance_admin``.

Other columns pass through unchanged. The salt comes from env
``GOVERNOR_PII_SALT`` and is stored in ``private.pii_salt`` (one row, replaced on
each apply). Views read it with a scalar subquery under the view owner's
rights, so the value never appears in a view definition and the reader roles
never get access to ``private``.

Each reader role gets USAGE on its own serving schema and SELECT on its views,
nothing else; ``PUBLIC`` and the other governor roles get nothing. The whole
apply is one transaction and drops and recreates every view, so it is
idempotent. Admin DSN from env ``GOVERNOR_PG_ADMIN_DSN``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path

import psycopg
import yaml
from psycopg import sql

from governor.core import paths

ENV_ADMIN_DSN = "GOVERNOR_PG_ADMIN_DSN"
ENV_SALT = "GOVERNOR_PII_SALT"
DEFAULT_ACCESS = paths.KNOWLEDGE / "access.yaml"

SALT_SCHEMA = "private"
SALT_TABLE = "pii_salt"
SERVING_PREFIX = "serve_"
# access.yaml role -> database reader role (testbed/sql/roles.sql).
READER_ROLES = {"analyst": "governor_analyst", "finance_admin": "governor_finance_admin"}
# Roles that never get anything on a serving schema they do not own.
OTHER_ROLES = ("governor_ask", "governor_build")


class ServingError(Exception):
    """Bad input or configuration; nothing was changed."""


@dataclass(frozen=True)
class ServingPolicy:
    pii: dict[str, str]  # column (lower case) -> PII tag, for every table
    mask_value: str
    finance_grants: frozenset[tuple[str, str]]  # (table, column), lower case


def load_policy(policy_path: Path, access_path: Path) -> ServingPolicy:
    policy = yaml.safe_load(Path(policy_path).read_text(encoding="utf-8")) or {}
    if not isinstance(policy, dict):
        raise ServingError(f"{policy_path}: expected a mapping of column name to PII tag")
    access = yaml.safe_load(Path(access_path).read_text(encoding="utf-8")) or {}
    if "mask_value" not in access:
        raise ServingError(f"{access_path}: mask_value is missing")
    spec = ((access.get("roles") or {}).get("finance_admin")) or {}
    grants = set()
    for grant in spec.get("grants") or []:
        table, _, column = str(grant).lower().partition(".")
        if not table or not column:
            raise ServingError(f"{access_path}: grant {grant!r} is not table.column")
        grants.add((table, column))
    return ServingPolicy(
        pii={str(k).lower(): str(v) for k, v in policy.items()},
        mask_value=str(access["mask_value"]),
        finance_grants=frozenset(grants),
    )


def _column_expr(role: str, table: str, column: str, policy: ServingPolicy) -> sql.Composable:
    ident = sql.Identifier(column)
    name = column.lower()
    if name not in policy.pii:
        return ident
    if role == "analyst":
        salt = sql.SQL("(SELECT {} FROM {})").format(
            sql.Identifier("salt"), sql.Identifier(SALT_SCHEMA, SALT_TABLE)
        )
        value = sql.SQL("encode(sha256(convert_to({} || CAST({} AS text), 'UTF8')), 'hex')").format(salt, ident)
    elif (table.lower(), name) in policy.finance_grants:
        return ident
    else:
        value = sql.SQL("CAST({} AS text)").format(sql.Literal(policy.mask_value))
    return sql.SQL("{} AS {}").format(value, ident)


def _source_columns(connection: psycopg.Connection, source: str) -> dict[str, list[str]]:
    rows = connection.execute(
        """
        SELECT c.table_name, c.column_name
        FROM information_schema.columns c
        JOIN information_schema.tables t
          ON t.table_schema = c.table_schema AND t.table_name = c.table_name
        WHERE c.table_schema = %s AND t.table_type IN ('BASE TABLE', 'VIEW')
        ORDER BY c.table_name, c.ordinal_position
        """,
        [source],
    ).fetchall()
    tables: dict[str, list[str]] = {}
    for table, column in rows:
        tables.setdefault(table, []).append(column)
    return tables


def apply(source: str, policy: ServingPolicy, *, dsn: str, salt: str) -> dict:
    """Store the salt, rebuild every serving view and its grants; one transaction."""
    if not salt:
        raise ServingError(f"{ENV_SALT} is empty")
    if source.startswith(SERVING_PREFIX) or source == SALT_SCHEMA:
        raise ServingError(f"source schema {source!r} cannot be a serving or private schema")
    with psycopg.connect(dsn, autocommit=False) as connection:
        tables = _source_columns(connection, source)
        if not tables:
            raise ServingError(f"source schema {source!r} has no tables")

        salt_table = sql.Identifier(SALT_SCHEMA, SALT_TABLE)
        connection.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(sql.Identifier(SALT_SCHEMA)))
        connection.execute(sql.SQL("CREATE TABLE IF NOT EXISTS {} (salt text NOT NULL)").format(salt_table))
        connection.execute(sql.SQL("REVOKE ALL ON TABLE {} FROM PUBLIC").format(salt_table))
        connection.execute(sql.SQL("DELETE FROM {}").format(salt_table))
        connection.execute(sql.SQL("INSERT INTO {} (salt) VALUES (%s)").format(salt_table), [salt])

        views: dict[str, list[str]] = {}
        for role, reader in READER_ROLES.items():
            schema = f"{SERVING_PREFIX}{role}"
            schema_id = sql.Identifier(schema)
            connection.execute(sql.SQL("CREATE SCHEMA IF NOT EXISTS {}").format(schema_id))
            # Drop every existing view first, so a table gone from the source leaves no stale view.
            for (old,) in connection.execute(
                "SELECT viewname FROM pg_views WHERE schemaname = %s", [schema]
            ).fetchall():
                connection.execute(sql.SQL("DROP VIEW IF EXISTS {}").format(sql.Identifier(schema, old)))
            for table, columns in tables.items():
                projection = sql.SQL(", ").join(_column_expr(role, table, c, policy) for c in columns)
                connection.execute(
                    sql.SQL("CREATE VIEW {} AS SELECT {} FROM {}").format(
                        sql.Identifier(schema, table), projection, sql.Identifier(source, table)
                    )
                )
            others = [r for r in (*READER_ROLES.values(), *OTHER_ROLES) if r != reader]
            for grantee in ("PUBLIC", *others):
                target = sql.SQL(grantee) if grantee == "PUBLIC" else sql.Identifier(grantee)
                connection.execute(sql.SQL("REVOKE ALL ON SCHEMA {} FROM {}").format(schema_id, target))
                connection.execute(
                    sql.SQL("REVOKE ALL ON ALL TABLES IN SCHEMA {} FROM {}").format(schema_id, target)
                )
            connection.execute(sql.SQL("GRANT USAGE ON SCHEMA {} TO {}").format(schema_id, sql.Identifier(reader)))
            connection.execute(
                sql.SQL("GRANT SELECT ON ALL TABLES IN SCHEMA {} TO {}").format(schema_id, sql.Identifier(reader))
            )
            views[schema] = sorted(tables)
        connection.commit()
    return {
        "source": source,
        "tables": len(tables),
        "views": sum(len(v) for v in views.values()),
        "schemas": sorted(views),
        "pii_columns": sorted(
            f"{t}.{c}" for t, cols in tables.items() for c in cols if c.lower() in policy.pii
        ),
        "finance_grants": sorted(f"{t}.{c}" for t, c in policy.finance_grants),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m governor.core.serving")
    sub = parser.add_subparsers(dest="command", required=True)
    cmd = sub.add_parser("apply", help="rebuild the serving views for every table in a source schema")
    cmd.add_argument("--source", required=True, help="source schema, e.g. raw")
    cmd.add_argument("--policy", required=True, type=Path, help="column -> PII tag YAML")
    cmd.add_argument("--access", type=Path, default=DEFAULT_ACCESS, help="access YAML (mask value, grants)")
    args = parser.parse_args(argv)

    dsn = os.environ.get(ENV_ADMIN_DSN)
    if not dsn:
        print(f"serving: set {ENV_ADMIN_DSN}", file=sys.stderr)
        return 2
    salt = os.environ.get(ENV_SALT, "")
    try:
        policy = load_policy(args.policy, args.access)
        summary = apply(args.source, policy, dsn=dsn, salt=salt)
    except (ServingError, OSError, yaml.YAMLError) as error:
        print(f"serving: {error}", file=sys.stderr)
        return 2
    except psycopg.Error as error:
        print(f"serving: database error: {type(error).__name__}: {str(error).splitlines()[0][:200]}", file=sys.stderr)
        return 1
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
