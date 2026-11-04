"""Target dbt workspace and runner tests. Offline, except the live ones (skip without a build password and a database)."""
import json
import os
import re
import sys

import pytest
import yaml

from governor.build import __main__ as build_cli
from governor.build.dbt import run_dbt
from governor.build.workspace import build_dsn, init_target, write_sources

TABLES = {"orders": ["order_id", "status"], "items": ["order_id", "price"]}


def test_layout(tmp_path):
    init_target(tmp_path, "shop")
    for rel in ("models/staging", "models/intermediate", "models/marts", "tests", "governor"):
        assert (tmp_path / rel).is_dir()
    project = yaml.safe_load((tmp_path / "dbt_project.yml").read_text())
    assert project["name"] == "shop" and project["profile"] == "governor"
    assert project["models"]["shop"]["marts"]["+materialized"] == "table"
    text = (tmp_path / "profiles" / "profiles.yml").read_text()
    assert "type: postgres" in text and "schema: dev_governor" in text and "target: dev" in text
    for key in ("host", "port", "dbname", "user", "password"):
        assert re.search(rf"{key}: .*env_var\(", text), key


def test_no_secret_and_password_has_no_default(tmp_path):
    init_target(tmp_path, "shop")
    write_sources(tmp_path, TABLES)
    text = (tmp_path / "profiles" / "profiles.yml").read_text()
    assert "governor_build_local" not in text
    assert "env_var('GOVERNOR_BUILD_PASSWORD')" in text
    for p in tmp_path.rglob("*"):
        if p.is_file():
            assert "governor_build_local" not in p.read_text()


def test_idempotent_keeps_existing_files(tmp_path):
    init_target(tmp_path, "shop")
    (tmp_path / "dbt_project.yml").write_text("name: mine\n")
    (tmp_path / "models" / "staging" / "stg_x.sql").write_text("select 1")
    init_target(tmp_path, "other")
    assert (tmp_path / "dbt_project.yml").read_text() == "name: mine\n"
    assert (tmp_path / "models" / "staging" / "stg_x.sql").read_text() == "select 1"


def test_sources(tmp_path):
    path = write_sources(tmp_path, TABLES)
    assert path == tmp_path / "models" / "sources.yml"
    src = yaml.safe_load(path.read_text())["sources"][0]
    assert src["name"] == "raw" and src["schema"] == "raw"
    by_name = {t["name"]: [c["name"] for c in t["columns"]] for t in src["tables"]}
    assert by_name == TABLES


def test_build_dsn_from_env(monkeypatch):
    monkeypatch.setenv("GOVERNOR_PG_HOST", "db.example")
    monkeypatch.setenv("GOVERNOR_PG_PORT", "55433")
    monkeypatch.setenv("GOVERNOR_BUILD_PASSWORD", "pw")
    dsn = build_dsn()
    for part in ("host=db.example", "port=55433", "dbname=shop", "user=governor_build", "password=pw"):
        assert part in dsn
    monkeypatch.delenv("GOVERNOR_PG_HOST")
    assert "host=localhost" in build_dsn()


def test_run_dbt_missing_executable(monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "executable", str(tmp_path / "python"))
    with pytest.raises(FileNotFoundError):
        run_dbt(tmp_path, ["parse"])


# ---- live ----

def _database_up() -> bool:
    if not os.environ.get("GOVERNOR_BUILD_PASSWORD"):
        return False
    try:
        import psycopg

        with psycopg.connect(build_dsn(), connect_timeout=3):
            return True
    except Exception:  # noqa: BLE001
        return False


live = pytest.mark.skipif(not _database_up(), reason="needs GOVERNOR_BUILD_PASSWORD and a reachable database")


@live
def test_live_init_and_parse(tmp_path, monkeypatch, capsys):
    target = tmp_path / "company-dbt"
    assert build_cli.main(["init", "--target", str(target), "--project-name", "shop"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["target"] == str(target) and out["tables"]
    assert (target / "models" / "sources.yml").is_file()
    result = run_dbt(target, ["parse"])
    assert result.ok, result.log_tail
