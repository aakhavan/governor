"""Validator in the Postgres dialect, offline, on its own access and metadata fixtures."""

from __future__ import annotations

import duckdb
import pytest
import sqlglot

from governor.ask.validator import POSTGRES_FUNCTIONS, validate

ACCESS = """
version: 1
allowlist:
  models: [customers, orders]
limits:
  default_limit: 7
  row_cap: 20
  timeout_s: 5
mask_value: "<hidden>"
roles:
  analyst:
    pii: aggregate_only
    grants: []
  finance_admin:
    pii: mask
    grants:
      - customers.city
"""

COLUMNS = [
    ("model.shop.customers", "customer_id", "TEXT", None),
    ("model.shop.customers", "unique_id", "TEXT", "person_id"),
    ("model.shop.customers", "city", "TEXT", "location"),
    ("model.shop.customers", "state", "TEXT", None),
    ("model.shop.orders", "order_id", "TEXT", None),
    ("model.shop.orders", "customer_id", "TEXT", None),
    ("model.shop.orders", "amount", "NUMERIC(18,2)", None),
    ("model.shop.orders", "ordered_at", "TIMESTAMP", None),
]


@pytest.fixture
def check(tmp_path):
    access = tmp_path / "access.yaml"
    access.write_text(ACCESS, encoding="utf-8")
    meta = tmp_path / "meta.duckdb"
    con = duckdb.connect(str(meta))
    con.execute("CREATE TABLE nodes (unique_id VARCHAR, resource_type VARCHAR, name VARCHAR)")
    con.execute(
        'CREATE TABLE columns (unique_id VARCHAR, "column" VARCHAR, data_type VARCHAR, '
        "description VARCHAR, pii_tag VARCHAR)"
    )
    for uid in {c[0] for c in COLUMNS}:
        con.execute("INSERT INTO nodes VALUES (?, 'model', ?)", [uid, uid.rsplit(".", 1)[1]])
    for uid, col, typ, tag in COLUMNS:
        con.execute("INSERT INTO columns VALUES (?, ?, ?, '', ?)", [uid, col, typ, tag])
    con.close()

    def run(sql, role="analyst", dialect="postgres"):
        return validate(sql, role, access_path=access, meta_path=meta, dialect=dialect)

    return run


def test_validator_postgres_rejects_select_star(check):
    for sql in (
        "SELECT * FROM serve_analyst.orders",
        "SELECT o.* FROM serve_analyst.orders o",
        "WITH x AS (SELECT order_id FROM serve_analyst.orders) SELECT * FROM x",
    ):
        r = check(sql)
        assert not r.ok and "STAR" in r.codes, sql
    assert check("SELECT count(*) AS n FROM serve_analyst.orders").ok


def test_validator_postgres_injects_limit(check):
    r = check("SELECT order_id FROM serve_analyst.orders")
    assert r.ok
    tree = sqlglot.parse_one(r.sql, read="postgres")
    assert tree.args["limit"].expression.name == "7"
    r = check("SELECT order_id FROM serve_analyst.orders LIMIT 500")
    assert r.ok and sqlglot.parse_one(r.sql, read="postgres").args["limit"].expression.name == "20"
    r = check("SELECT order_id FROM serve_analyst.orders LIMIT 3")
    assert r.ok and sqlglot.parse_one(r.sql, read="postgres").args["limit"].expression.name == "3"
    r = check("SELECT order_id FROM serve_analyst.orders FETCH FIRST 900 ROWS ONLY")
    assert r.ok and sqlglot.parse_one(r.sql, read="postgres").args["limit"].expression.name == "20"


def test_validator_postgres_default_deny(check):
    denied = [
        "SELECT order_id FROM orders",  # unqualified: search_path decides
        "SELECT order_id FROM marts.orders",
        "SELECT order_id FROM serve_finance_admin.orders",  # another role's schema
        "SELECT order_id FROM raw.orders",
        "SELECT salt FROM private.pii_salt",
        "SELECT order_id FROM shop.serve_analyst.orders",  # catalog
        "SELECT relname FROM pg_catalog.pg_class",
        "SELECT table_name FROM information_schema.tables",
        "SELECT x FROM serve_analyst.payments",  # not allowlisted
    ]
    for sql in denied:
        r = check(sql)
        assert not r.ok and "TABLE_NOT_ALLOWED" in r.codes, (sql, r.codes)
    assert check("SELECT order_id FROM serve_analyst.orders").ok
    assert check("SELECT city FROM serve_finance_admin.customers", role="finance_admin").ok
    assert not check("SELECT order_id FROM serve_analyst.orders", role="finance_admin").ok
    # Other rules hold in this dialect too.
    assert "MULTI_STATEMENT" in check("SELECT order_id FROM serve_analyst.orders; SELECT 1").codes
    assert "NOT_SELECT" in check("DELETE FROM serve_analyst.orders").codes
    assert "NOT_SELECT" in check("SELECT order_id FROM serve_analyst.orders FOR UPDATE").codes
    assert "VOLATILE_TIME" in check("SELECT order_id FROM serve_analyst.orders WHERE ordered_at < now()").codes
    assert "UNKNOWN_ROLE" in check("SELECT order_id FROM serve_analyst.orders", role="nobody").codes


def test_validator_postgres_rejects_role_switch(check):
    attacks = [
        "SELECT set_config('role', 'governor_finance_admin', true) AS r FROM serve_analyst.orders",
        "SELECT order_id FROM serve_analyst.orders WHERE set_config('role', 'governor_finance_admin', true) IS NOT NULL",
        "SELECT (SELECT set_config('role', 'governor_finance_admin', true)) AS r",
        "SELECT current_setting('role') AS r FROM serve_analyst.orders",
        "SELECT query_to_xml('SELECT city FROM serve_finance_admin.customers', true, true, '') AS x",
        "SELECT table_to_xml('serve_finance_admin.customers', true, true, '') AS x",
        "SELECT cursor_to_xml('c', 1, true, true, '') AS x",
        "SELECT dblink('dbname=shop', 'SELECT 1') AS x",
        "SELECT pg_sleep(20) AS x",
        "SELECT pg_read_file('/etc/passwd') AS x",
        "SELECT lo_import('/etc/passwd') AS x",
        "SELECT nextval('s') AS x",
        "SELECT pg_catalog.set_config('role', 'governor_finance_admin', true) AS r",
        "SELECT pg_catalog.upper(state) AS s FROM serve_analyst.customers",
        'SELECT "set_config"(\'role\', \'governor_finance_admin\', true) AS r',
    ]
    for sql in attacks:
        r = check(sql)
        assert not r.ok and "FUNCTION_NOT_ALLOWED" in r.codes, (sql, r.codes)
    for name in ("set_config", "current_setting", "query_to_xml", "table_to_xml", "dblink", "pg_sleep", "lo_import"):
        assert name not in POSTGRES_FUNCTIONS and name.upper() not in POSTGRES_FUNCTIONS
    # Ordinary read-only functions still pass.
    ok = check(
        "SELECT date_trunc('month', ordered_at) AS m, round(sum(amount), 2) AS total, count(DISTINCT customer_id) AS n "
        "FROM serve_analyst.orders WHERE coalesce(amount, 0) > 0 GROUP BY 1 ORDER BY 1"
    )
    assert ok.ok, ok.reasons
    assert check("SELECT count(DISTINCT unique_id) AS n FROM serve_analyst.customers").ok


def test_validator_duckdb_keeps_function_behaviour(check):
    # The allowlist is Postgres only; DuckDB keeps its current checks.
    r = check("SELECT md5(order_id) AS h, string_split(order_id, '-') AS p FROM orders", dialect="duckdb")
    assert r.ok, r.reasons
    assert "FUNCTION_NOT_ALLOWED" not in check("SELECT current_setting('threads') AS t FROM orders", dialect="duckdb").codes
