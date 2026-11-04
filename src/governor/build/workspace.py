"""The target dbt project: layout, sources.yml and the build login DSN (batch2.md sections 3 and 4)."""

from __future__ import annotations

import os
from pathlib import Path

import yaml
from psycopg.conninfo import make_conninfo

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
    """Create the layout; never overwrites an existing file."""
    target = Path(target)
    for d in DIRS:
        (target / d).mkdir(parents=True, exist_ok=True)
    _write_if_missing(target / "dbt_project.yml", _project_yml(project_name))
    _write_if_missing(target / "profiles" / "profiles.yml", _PROFILES)


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


def build_dsn() -> str:
    """The build login as a libpq connection string, from env (test-bed password default, laptop only)."""
    return make_conninfo(
        host=os.environ.get("GOVERNOR_PG_HOST") or "localhost",
        port=os.environ.get("GOVERNOR_PG_PORT") or "55432",
        dbname=os.environ.get("GOVERNOR_PG_DB") or "shop",
        user=os.environ.get("GOVERNOR_BUILD_USER") or "governor_build",
        password=os.environ.get("GOVERNOR_BUILD_PASSWORD") or "governor_build_local",
    )
