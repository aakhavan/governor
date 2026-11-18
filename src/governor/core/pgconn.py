"""Postgres connection timeout (batch3.md section 27.1).

A database that listens but never answers (a container up without its port) used to make governor wait forever.
Every connection string governor opens goes through ``with_timeout``, so a dead database fails within
``GOVERNOR_PG_CONNECT_TIMEOUT`` seconds instead.
"""

from __future__ import annotations

import os

from psycopg.conninfo import conninfo_to_dict, make_conninfo

ENV_TIMEOUT = "GOVERNOR_PG_CONNECT_TIMEOUT"
DEFAULT_TIMEOUT_S = 10


def connect_timeout_s() -> int:
    """``GOVERNOR_PG_CONNECT_TIMEOUT`` as whole seconds: default 10, minimum 1 (an unreadable value is the default)."""
    raw = (os.environ.get(ENV_TIMEOUT) or "").strip()
    try:
        value = int(raw) if raw else DEFAULT_TIMEOUT_S
    except ValueError:
        value = DEFAULT_TIMEOUT_S
    return max(1, value)


def with_timeout(dsn: str) -> str:
    """``dsn`` with ``connect_timeout`` set; a timeout the DSN already sets is kept. URI and key-value DSNs both work."""
    if "connect_timeout" in conninfo_to_dict(dsn or ""):
        return dsn
    return make_conninfo(dsn or "", connect_timeout=connect_timeout_s())
