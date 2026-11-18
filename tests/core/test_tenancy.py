"""Tenant registry (batch3.md section 31.1): derived paths, the build DSN, dbt env and every refused entry."""
import os
from pathlib import Path

import pytest
from psycopg.conninfo import conninfo_to_dict

from governor.core import tenancy
from governor.core.tenancy import TenantError, load_tenants, tenants_path


def _root(path: Path, kpis: bool = True, blueprint: bool = True) -> Path:
    k = path / "knowledge"
    k.mkdir(parents=True, exist_ok=True)
    if kpis:
        (k / "kpis.yaml").write_text("version: 1\nkpis: []\n", encoding="utf-8")
    if blueprint:
        (k / "blueprint.md").write_text("---\nversion: 1\n---\n", encoding="utf-8")
    return path


def _registry(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def test_tenant_paths_resolve_relative_to_registry(tmp_path, monkeypatch):
    _root(tmp_path / "roots" / "acme")
    _root(tmp_path / "roots" / "globex")
    reg = _registry(tmp_path / "conf" / "tenants.yaml",
                    "tenants:\n"
                    "  acme: {root: ../roots/acme, target: ../dbt/acme, pg_port: 55441}\n"
                    "  globex: {root: ../roots/globex, target: ../dbt/globex, pg_port: '55442', pg_host: db.globex,"
                    " pg_db: globex}\n")
    monkeypatch.chdir(tmp_path / "roots")  # relative paths follow the registry file, not the working folder
    tenants = load_tenants(reg)
    assert sorted(tenants) == ["acme", "globex"]
    a, g = tenants["acme"], tenants["globex"]
    root = (tmp_path / "roots" / "acme").resolve()
    assert a.root == root and a.target == (tmp_path / "dbt" / "acme").resolve()
    assert (a.pg_host, a.pg_port, a.pg_db) == ("localhost", 55441, "shop")
    assert (g.pg_host, g.pg_port, g.pg_db) == ("db.globex", 55442, "globex")
    assert a.knowledge == root / "knowledge"
    assert a.kpis_path == root / "knowledge" / "kpis.yaml"
    assert a.blueprint_path == root / "knowledge" / "blueprint.md"
    assert a.approved_default == root / "knowledge" / "approved.yaml"
    assert a.policy_path == root / "knowledge" / "shop" / "policy.yaml"
    assert a.access_path == root / "knowledge" / "shop" / "access.yaml"
    assert a.state_dir == root / "artifacts"
    assert a.checkpoints == root / "artifacts" / "build_checkpoints.sqlite"
    assert g.address == "db.globex:55442/globex"

    # the build login from env, the tenant's database, with a connect timeout
    monkeypatch.setenv("GOVERNOR_PG_HOST", "elsewhere")
    monkeypatch.setenv("GOVERNOR_PG_PORT", "1")
    monkeypatch.setenv("GOVERNOR_BUILD_USER", "builder")
    info = conninfo_to_dict(g.build_dsn())
    assert (info["host"], info["port"], info["dbname"], info["user"]) == ("db.globex", "55442", "globex", "builder")
    assert "connect_timeout" in info

    before = dict(os.environ)
    env = g.dbt_env()
    assert (env["GOVERNOR_PG_HOST"], env["GOVERNOR_PG_PORT"], env["GOVERNOR_PG_DB"]) == ("db.globex", "55442", "globex")
    assert env["GOVERNOR_BUILD_USER"] == "builder"  # the caller's env is kept
    assert dict(os.environ) == before  # never changed in place
    assert g.dbt_env({"X": "1"}) == {"X": "1", "GOVERNOR_PG_HOST": "db.globex", "GOVERNOR_PG_PORT": "55442",
                                     "GOVERNOR_PG_DB": "globex"}

    monkeypatch.delenv(tenancy.ENV_TENANTS, raising=False)
    assert tenants_path() is None
    monkeypatch.setenv(tenancy.ENV_TENANTS, "")
    assert tenants_path() is None
    monkeypatch.setenv(tenancy.ENV_TENANTS, str(reg))
    assert tenants_path() == reg


@pytest.mark.parametrize("entries, needle", [
    ("  'bad name': {root: a, target: ta, pg_port: 1}\n", "tenant 'bad name': bad name"),
    ("  a.b: {root: a, target: ta, pg_port: 1}\n", "bad name"),
    ("  a: {root: a, target: ta, pg_port: 1, password: x}\n", "tenant a: unknown key password"),
    ("  a: {root: a, target: ta}\n", "tenant a: missing pg_port"),
    ("  a: {root: a, target: ta, pg_port: many}\n", "tenant a: pg_port must be a port number"),
    ("  a: {root: nokpis, target: ta, pg_port: 1}\n", "tenant a: missing knowledge/kpis.yaml"),
    ("  a: {root: noblueprint, target: ta, pg_port: 1}\n", "tenant a: missing knowledge/blueprint.md"),
    ("  a: {root: a, target: ta, pg_port: 1}\n  b: {root: ./a, target: tb, pg_port: 2}\n",
     "tenant b: shares its root"),
    ("  a: {root: a, target: ta, pg_port: 1}\n  b: {root: b, target: ta/../ta, pg_port: 2}\n",
     "tenant b: shares its target"),
    ("  a: {root: a, target: ta, pg_port: 1}\n  b: {root: b, target: tb, pg_port: 1, pg_db: shop}\n",
     "tenant b: shares its database (localhost:1/shop) with tenant a"),
])
def test_tenant_registry_rejects_bad_entries(tmp_path, entries, needle):
    _root(tmp_path / "a")
    _root(tmp_path / "b")
    _root(tmp_path / "nokpis", kpis=False)
    _root(tmp_path / "noblueprint", blueprint=False)
    reg = _registry(tmp_path / "tenants.yaml", "tenants:\n" + entries)
    with pytest.raises(TenantError) as err:
        load_tenants(reg)
    assert needle in str(err.value)


@pytest.mark.parametrize("text, needle", [
    ("", "needs a 'tenants:' mapping"),
    ("tenants: []\n", "needs a 'tenants:' mapping"),
    ("tenants: {a: {root: a, target: ta, pg_port: 1}}\nextra: 1\n", "unknown key extra"),
])
def test_tenant_registry_rejects_bad_files(tmp_path, text, needle):
    _root(tmp_path / "a")
    with pytest.raises(TenantError, match=needle):
        load_tenants(_registry(tmp_path / "tenants.yaml", text))
    with pytest.raises(TenantError, match="cannot read the tenant registry"):
        load_tenants(tmp_path / "missing.yaml")

@pytest.mark.parametrize("name, expected", [("acme", "acme"), ("globex-eu", "globex_eu"), ("9shop", "t_9shop")])
def test_dbt_project_name_is_valid_for_dbt(name, expected):
    # the CLI (--tenant) and the Slack bot give init_target this name; dbt rejects "-" and a leading digit
    assert tenancy.dbt_project_name(name) == expected

