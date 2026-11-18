"""F1 connection timeout (batch3.md section 27.1). Offline: no Postgres needed."""
import socket
import time

import pytest
import yaml
from psycopg.conninfo import conninfo_to_dict

from governor.build.workspace import build_address, build_dsn, init_target
from governor.core.pgconn import connect_timeout_s, with_timeout


def test_with_timeout_adds_connect_timeout_once(monkeypatch):
    monkeypatch.delenv("GOVERNOR_PG_CONNECT_TIMEOUT", raising=False)
    for dsn in ("host=localhost port=55432 dbname=shop user=u", "postgresql://u@localhost:55432/shop"):
        out = with_timeout(dsn)
        params = conninfo_to_dict(out)
        assert params["connect_timeout"] == "10" and params["host"] == "localhost" and params["dbname"] == "shop"
        assert with_timeout(out).count("connect_timeout") == 1  # idempotent
    # an existing timeout is kept, in either form
    assert conninfo_to_dict(with_timeout("host=h connect_timeout=3"))["connect_timeout"] == "3"
    assert conninfo_to_dict(with_timeout("postgresql://h/db?connect_timeout=4"))["connect_timeout"] == "4"
    monkeypatch.setenv("GOVERNOR_PG_CONNECT_TIMEOUT", "5")
    assert conninfo_to_dict(with_timeout("host=h"))["connect_timeout"] == "5"


def test_connect_timeout_env_default_and_minimum(monkeypatch):
    monkeypatch.delenv("GOVERNOR_PG_CONNECT_TIMEOUT", raising=False)
    assert connect_timeout_s() == 10
    for raw, want in (("7", 7), ("0", 1), ("-3", 1), ("soon", 10), ("", 10)):
        monkeypatch.setenv("GOVERNOR_PG_CONNECT_TIMEOUT", raw)
        assert connect_timeout_s() == want, raw


def test_build_dsn_has_connect_timeout(monkeypatch):
    monkeypatch.delenv("GOVERNOR_PG_CONNECT_TIMEOUT", raising=False)
    assert "connect_timeout=10" in build_dsn()
    monkeypatch.setenv("GOVERNOR_PG_CONNECT_TIMEOUT", "3")
    assert "connect_timeout=3" in build_dsn() and build_dsn().count("connect_timeout") == 1


def test_dbt_profile_template_has_connect_timeout(tmp_path):
    init_target(tmp_path, "shop")
    outputs = yaml.safe_load((tmp_path / "profiles" / "profiles.yml").read_text())["governor"]["outputs"]
    for name in ("dev", "prod"):
        assert "env_var('GOVERNOR_PG_CONNECT_TIMEOUT', '10')" in outputs[name]["connect_timeout"], name


def test_build_address_has_no_secrets(monkeypatch):
    monkeypatch.setenv("GOVERNOR_PG_HOST", "db.example")
    monkeypatch.setenv("GOVERNOR_PG_PORT", "55433")
    monkeypatch.setenv("GOVERNOR_PG_DB", "shop")
    monkeypatch.setenv("GOVERNOR_BUILD_PASSWORD", "s3cret-pw")
    assert build_address() == "db.example:55433/shop"


def test_unreachable_database_fails_within_timeout(monkeypatch):
    """17 Nov: a container up without its port; profiling waited forever. A socket that listens but never answers."""
    from governor.build.profile import profile_schema

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.bind(("127.0.0.1", 0))
    srv.listen(1)  # the kernel completes the TCP handshake; nobody ever sends a byte
    port = srv.getsockname()[1]
    monkeypatch.setenv("GOVERNOR_PG_CONNECT_TIMEOUT", "2")
    try:
        started = time.monotonic()
        with pytest.raises(Exception):
            profile_schema(f"host=127.0.0.1 port={port} dbname=shop user=nobody password=x sslmode=disable")
        assert time.monotonic() - started < 10
    finally:
        srv.close()
