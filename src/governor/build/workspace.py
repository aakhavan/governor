"""The target dbt project: layout, sources.yml and the build login DSN (batch2.md sections 3 and 4)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from psycopg.conninfo import make_conninfo

from governor.core.pgconn import with_timeout

DIRS = ("models/staging", "models/intermediate", "models/marts", "tests", "governor", "profiles")

# Every connection setting is an env_var(...) call. The password has no default in the file:
# the test-bed default lives in build_dsn() only.
_PROFILES = """\
governor:
  target: dev
  outputs:
    dev:
      type: postgres
      host: "{{ env_var('GOVERNOR_PG_HOST', 'localhost') }}"
      port: "{{ env_var('GOVERNOR_PG_PORT', '55432') | as_number }}"
      dbname: "{{ env_var('GOVERNOR_PG_DB', 'shop') }}"
      user: "{{ env_var('GOVERNOR_BUILD_USER', 'governor_build') }}"
      password: "{{ env_var('GOVERNOR_BUILD_PASSWORD') }}"
      schema: dev_governor
      connect_timeout: "{{ env_var('GOVERNOR_PG_CONNECT_TIMEOUT', '10') | as_number }}"
      threads: 4
"""

# Target prod (batch2b section 13): certify deploys to analytics as governor_deploy.
_PROD = """\
    prod:
      type: postgres
      host: "{{ env_var('GOVERNOR_PG_HOST', 'localhost') }}"
      port: "{{ env_var('GOVERNOR_PG_PORT', '55432') | as_number }}"
      dbname: "{{ env_var('GOVERNOR_PG_DB', 'shop') }}"
      user: "{{ env_var('GOVERNOR_DEPLOY_USER', 'governor_deploy') }}"
      password: "{{ env_var('GOVERNOR_DEPLOY_PASSWORD') }}"
      schema: analytics
      connect_timeout: "{{ env_var('GOVERNOR_PG_CONNECT_TIMEOUT', '10') | as_number }}"
      threads: 4
"""


def _project_yml(project_name: str) -> str:
    return yaml.safe_dump(
        {
            "name": project_name,
            "version": "1.0.0",
            "config-version": 2,
            "profile": "governor",
            "model-paths": ["models"],
            "test-paths": ["tests"],
            "models": {project_name: {"marts": {"+materialized": "table"}}},
        },
        sort_keys=False,
    )


def _write_if_missing(path: Path, text: str) -> None:
    if not path.exists():
        path.write_text(text, encoding="utf-8")


def init_target(target: Path, project_name: str) -> None:
    """Create the layout; never overwrites an existing file. A profiles.yml written before target ``prod`` existed
    gets the ``prod`` output appended (its last block is ``outputs``)."""
    target = Path(target)
    for d in DIRS:
        (target / d).mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "dbt_project.yml", _project_yml(project_name))
    profiles = target / "profiles" / "profiles.yml"
    _write_if_missing(profiles, _PROFILES + _PROD)
    text = profiles.read_text(encoding="utf-8")
    if "\n    prod:" not in text:
        profiles.write_text(text.rstrip("\n") + "\n" + _PROD, encoding="utf-8")


def write_sources(target: Path, tables: dict[str, list[str]]) -> Path:
    """Write models/sources.yml: source ``raw`` (schema ``raw``) with every table and its columns."""
    doc = {
        "version": 2,
        "sources": [
            {
                "name": "raw",
                "schema": "raw",
                "tables": [{"name": t, "columns": [{"name": c} for c in cols]} for t, cols in sorted(tables.items())],
            }
        ],
    }
    path = Path(target) / "models" / "sources.yml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")
    return path


def _source_table_names(path: Path) -> set[str] | None:
    """Table names of source ``raw`` in an existing sources.yml; ``None`` when unreadable or another layout."""
    try:
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        raw = next(s for s in doc.get("sources") or [] if s.get("name") == "raw")
        return {str(t["name"]) for t in raw.get("tables") or []}
    except Exception:  # noqa: BLE001 (any unreadable file is rewritten from the profile)
        return None


def sync_sources(target: Path, profile: dict) -> bool:
    """Make ``models/sources.yml`` match the profiled raw tables, for every entry point (CLI, Slack, eval).

    Written when missing (a target never given ``init``, found on 17 Nov with a Slack run on a fresh target) or
    when the set of raw tables changed since it was written. Left alone when the tables match, so a file written by
    ``init`` (which also lists ``_``-prefixed load columns the profile leaves out) stays as it is. Returns whether
    the file was written."""
    tables = {str(t["name"]): [str(c["name"]) for c in t.get("columns") or []] for t in profile.get("tables") or []}
    if not tables:
        return False
    path = Path(target) / "models" / "sources.yml"
    if path.is_file() and _source_table_names(path) == set(tables):
        return False
    write_sources(Path(target), tables)
    return True


def build_dsn() -> str:
    """The build login as a libpq connection string, from env (test-bed password default, laptop only)."""
    return with_timeout(make_conninfo(
        host=os.environ.get("GOVERNOR_PG_HOST") or "localhost",
        port=os.environ.get("GOVERNOR_PG_PORT") or "55432",
        dbname=os.environ.get("GOVERNOR_PG_DB") or "shop",
        user=os.environ.get("GOVERNOR_BUILD_USER") or "governor_build",
        password=os.environ.get("GOVERNOR_BUILD_PASSWORD") or "governor_build_local",
    ))


def build_address() -> str:
    """The build database as ``host:port/db`` for messages: never a user, password or full DSN."""
    host = os.environ.get("GOVERNOR_PG_HOST") or "localhost"
    port = os.environ.get("GOVERNOR_PG_PORT") or "55432"
    db = os.environ.get("GOVERNOR_PG_DB") or "shop"
    return f"{host}:{port}/{db}"


def deploy_env(base: dict[str, str] | None = None) -> dict[str, str]:
    """Env for ``dbt --target prod``: the deploy login, with the test-bed password default (laptop only).
    ``base`` (a tenant's ``dbt_env()``) replaces ``os.environ`` as the starting point."""
    env = dict(os.environ if base is None else base)
    env["GOVERNOR_DEPLOY_USER"] = os.environ.get("GOVERNOR_DEPLOY_USER") or "governor_deploy"
    env["GOVERNOR_DEPLOY_PASSWORD"] = os.environ.get("GOVERNOR_DEPLOY_PASSWORD") or "governor_deploy_local"
    return env
