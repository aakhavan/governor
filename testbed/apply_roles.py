"""Apply testbed/sql/roles.sql as the admin, with the login passwords from env.

    python testbed/apply_roles.py --dsn <admin dsn>

Passwords: GOVERNOR_ASK_PASSWORD and GOVERNOR_BUILD_PASSWORD, with the test-bed
defaults governor_ask_local and governor_build_local (laptop only). The psql
variables :'ask_password' and :'build_password' in roles.sql are replaced by
quoted literals and the script runs in one transaction. Idempotent.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

ROLES_SQL = Path(__file__).resolve().parent / "sql" / "roles.sql"
PASSWORDS = {
    "ask_password": ("GOVERNOR_ASK_PASSWORD", "governor_ask_local"),
    "build_password": ("GOVERNOR_BUILD_PASSWORD", "governor_build_local"),
}
_VARIABLE = re.compile(r":'([A-Za-z_][A-Za-z0-9_]*)'")


def render(script: str, values: dict[str, str], quote) -> str:
    """``script`` with every psql :'name' variable replaced by ``quote(value)``."""

    def replace(match: re.Match) -> str:
        name = match.group(1)
        if name not in values:
            raise KeyError(f"roles.sql uses unknown variable :'{name}'")
        return quote(values[name])

    return _VARIABLE.sub(replace, script)


def passwords() -> dict[str, str]:
    return {var: os.environ.get(env) or default for var, (env, default) in PASSWORDS.items()}


def apply(dsn: str) -> None:
    import psycopg
    from psycopg import sql

    with psycopg.connect(dsn, autocommit=False) as conn:
        script = render(ROLES_SQL.read_text(encoding="utf-8"), passwords(),
                        lambda v: sql.Literal(v).as_string(conn))
        conn.execute(script)  # no parameters: simple protocol, several statements, one transaction
        conn.commit()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dsn", default=None, help="admin DSN (default: env GOVERNOR_PG_ADMIN_DSN)")
    args = ap.parse_args(argv)
    dsn = args.dsn or os.environ.get("GOVERNOR_PG_ADMIN_DSN")
    if not dsn:
        print("No DSN: pass --dsn or set GOVERNOR_PG_ADMIN_DSN", file=sys.stderr)
        return 2
    try:
        apply(dsn)
    except Exception as e:  # noqa: BLE001 - one readable line, never the DSN
        print(f"roles not applied: {type(e).__name__}: {str(e).splitlines()[0] if str(e) else ''}", file=sys.stderr)
        return 1
    print("roles applied")
    return 0


if __name__ == "__main__":
    sys.exit(main())
