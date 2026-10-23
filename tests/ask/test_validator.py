"""Validator and role policy on a small fixture (own models, own PII tags)."""

from __future__ import annotations

import duckdb
import pytest

from governor.ask.policy import Policy, UnknownRoleError
from governor.ask.validator import validate

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
  viewer:
    pii: aggregate_only
    grants: []
  auditor:
    pii: mask
    grants:
      - customers.email
"""

COLUMNS = [
    ("model.shop.customers", "customer_id", "VARCHAR", None),
    ("model.shop.customers", "email", "VARCHAR", "email"),
    ("model.shop.customers", "full_name", "VARCHAR", "name"),
    ("model.shop.customers", "region", "VARCHAR", None),
    ("model.shop.orders", "order_id", "VARCHAR", None),
    ("model.shop.orders", "customer_id", "VARCHAR", None),
    ("model.shop.orders", "amount", "DECIMAL(18,2)", None),
    ("model.shop.orders", "ordered_at", "TIMESTAMP", None),
    ("model.shop.stg_customers", "phone", "VARCHAR", "phone"),
]


@pytest.fixture
def env(tmp_path):
    access = tmp_path / "access.yaml"
    access.write_text(ACCESS, encoding="utf-8")
    meta = tmp_path / "meta.duckdb"
    con = duckdb.connect(str(meta))
    con.execute("CREATE TABLE nodes (unique_id VARCHAR, resource_type VARCHAR, name VARCHAR)")
    con.execute(
        "CREATE TABLE columns (unique_id VARCHAR, \"column\" VARCHAR, data_type VARCHAR, "
        "description VARCHAR, pii_tag VARCHAR)"
    )
    for uid in {c[0] for c in COLUMNS}:
        con.execute("INSERT INTO nodes VALUES (?, 'model', ?)", [uid, uid.rsplit(".", 1)[1]])
    for uid, col, typ, tag in COLUMNS:
        con.execute("INSERT INTO columns VALUES (?, ?, ?, '', ?)", [uid, col, typ, tag])
    con.close()

    warehouse = tmp_path / "wh.duckdb"
    con = duckdb.connect(str(warehouse))
    con.execute("CREATE TABLE customers (customer_id VARCHAR, email VARCHAR, full_name VARCHAR, region VARCHAR)")
    con.execute(
        "INSERT INTO customers VALUES ('c1','a@x.io','Ann','EU'), ('c2','b@x.io','Bob','EU'), "
        "('c3','c@x.io','Cy','US'), ('c4','d@x.io','Ann','US')"
    )
    con.execute("CREATE TABLE orders (order_id VARCHAR, customer_id VARCHAR, amount DECIMAL(18,2), ordered_at TIMESTAMP)")
    con.close()

    def check(sql, role):
        return validate(sql, role, access_path=access, meta_path=meta)

    def run(sql):
        con = duckdb.connect(str(warehouse), read_only=True)
        try:
            cur = con.execute(sql)
            return [d[0] for d in cur.description], cur.fetchall()
        finally:
            con.close()

    check.run = run
    check.paths = (access, meta)
    return check


# --- policy -----------------------------------------------------------------

def test_policy_reads_files(env):
    access, meta = env.paths
    viewer = Policy.for_role("viewer", access_path=access, meta_path=meta)
    assert viewer.pii_mode == "aggregate_only"
    assert viewer.models == ("customers", "orders")
    assert set(viewer.pii["customers"]) == {"email", "full_name"}
    assert "stg_customers" not in viewer.schema
    assert (viewer.default_limit, viewer.row_cap, viewer.mask_value) == (7, 20, "<hidden>")
    auditor = Policy.for_role("auditor", access_path=access, meta_path=meta)
    assert auditor.is_hidden("customers", "full_name")
    assert not auditor.is_hidden("customers", "email")


def test_policy_unknown_role_raises(env):
    access, meta = env.paths
    with pytest.raises(UnknownRoleError):
        Policy.for_role("root", access_path=access, meta_path=meta)


def test_real_policy_loads():
    for role in ("analyst", "finance_admin"):
        assert Policy.for_role(role).models


# --- reject codes -------------------------------------------------------------

REJECTS = [
    ("viewer", "SELEC region FROM customers", "PARSE_ERROR"),
    ("viewer", "SELECT 1 AS a; SELECT 2 AS b", "MULTI_STATEMENT"),
    ("viewer", "DELETE FROM orders", "NOT_SELECT"),
    ("viewer", "SET threads = 1", "NOT_SELECT"),
    ("viewer", "INSTALL httpfs", "NOT_SELECT"),
    ("viewer", "CALL pragma_version()", "NOT_SELECT"),
    ("viewer", "SELECT a FROM read_parquet('x.parquet')", "TABLE_FUNCTION"),
    ("viewer", "SELECT g FROM generate_series(1, 3) t(g)", "TABLE_FUNCTION"),
    ("viewer", "SELECT x FROM unnest([1, 2]) t(x)", "TABLE_FUNCTION"),
    ("viewer", "SELECT database_name FROM duckdb_databases()", "TABLE_FUNCTION"),
    ("viewer", "SELECT a FROM '/tmp/x.csv'", "TABLE_FUNCTION"),
    ("viewer", "SELECT phone FROM stg_customers", "TABLE_NOT_ALLOWED"),
    ("viewer", "SELECT region FROM main.customers", "TABLE_NOT_ALLOWED"),
    ("viewer", "SELECT region FROM customers WHERE customer_id IN (SELECT id FROM raw.users)", "TABLE_NOT_ALLOWED"),
    ("viewer", "SELECT bogus FROM customers", "COLUMN_UNKNOWN"),
    ("viewer", "SELECT o.region FROM orders o", "COLUMN_UNKNOWN"),
    ("viewer", "SELECT * FROM orders", "STAR"),
    ("viewer", "SELECT o.* FROM orders o", "STAR"),
    ("auditor", "SELECT to_json(c) FROM customers c", "STAR"),
    ("viewer", "SELECT order_id FROM orders WHERE ordered_at > now() - INTERVAL 1 DAY", "VOLATILE_TIME"),
    ("viewer", "SELECT current_timestamp AS t", "VOLATILE_TIME"),
    ("viewer", "SELECT get_current_timestamp() AS t", "VOLATILE_TIME"),
    ("viewer", "SELECT localtimestamp AS t", "VOLATILE_TIME"),
    ("viewer", "SELECT email FROM customers", "PII_FORBIDDEN"),
    ("viewer", "SELECT upper(full_name) AS n FROM customers", "PII_FORBIDDEN"),
    ("viewer", "WITH c AS (SELECT email AS e FROM customers) SELECT count(*) AS n FROM c", "PII_FORBIDDEN"),
    ("viewer", "SELECT n FROM (SELECT full_name AS n FROM customers) s", "PII_FORBIDDEN"),
    ("viewer", "SELECT region FROM customers WHERE email = 'a@x.io'", "PII_FORBIDDEN"),
    ("viewer", "SELECT region, count(*) AS n FROM customers GROUP BY region, full_name", "PII_FORBIDDEN"),
    ("viewer", "SELECT region FROM customers ORDER BY full_name", "PII_FORBIDDEN"),
    ("viewer", "SELECT o.order_id FROM orders o JOIN customers c ON c.customer_id = o.customer_id "
               "AND c.email LIKE '%x.io'", "PII_FORBIDDEN"),
    ("viewer", "SELECT count(lower(email)) AS n FROM customers", "PII_FORBIDDEN"),
    ("viewer", "SELECT region FROM customers c WHERE EXISTS "
               "(SELECT 1 FROM customers d WHERE d.full_name = c.full_name AND d.customer_id <> c.customer_id)",
     "PII_FORBIDDEN"),
    ("nobody", "SELECT region FROM customers", "UNKNOWN_ROLE"),
]


@pytest.mark.parametrize("role,sql,code", REJECTS)
def test_rejects(env, role, sql, code):
    result = env(sql, role)
    assert result.ok is False
    assert code in result.codes, (result.codes, result.reasons)
    assert result.sql is None
    assert result.reasons


# --- accepted queries and rewrites ---------------------------------------------

def test_count_of_pii_is_allowed_for_aggregate_role(env):
    result = env("SELECT region, count(DISTINCT email) AS n, count(full_name) AS m FROM customers GROUP BY region",
                 "viewer")
    assert result.ok, result.reasons
    assert result.tables == ["customers"]
    assert result.pii_columns == ["customers.email", "customers.full_name"]


def test_cte_names_are_allowed_relations(env):
    result = env("WITH t AS (SELECT customer_id, sum(amount) AS s FROM orders GROUP BY customer_id) "
                 "SELECT c.region, sum(t.s) AS s FROM t JOIN customers c ON c.customer_id = t.customer_id "
                 "GROUP BY c.region", "viewer")
    assert result.ok, result.reasons
    assert result.tables == ["customers", "orders"]


def test_date_literals_are_fine(env):
    assert env("SELECT count(*) AS n FROM orders WHERE ordered_at >= DATE '2026-01-01'", "viewer").ok


def test_limit_added_when_missing(env):
    result = env("SELECT region FROM customers", "viewer")
    assert result.ok
    assert result.sql.upper().endswith("LIMIT 7")


def test_limit_kept_under_cap_and_lowered_over_cap(env):
    assert env("SELECT region FROM customers LIMIT 3", "viewer").sql.upper().endswith("LIMIT 3")
    assert env("SELECT region FROM customers LIMIT 5000", "viewer").sql.upper().endswith("LIMIT 20")


def test_non_numeric_limit_is_capped_from_outside(env):
    sql = env("SELECT region FROM customers LIMIT (SELECT 50)", "viewer").sql
    assert sql.upper().endswith("LIMIT 20")
    assert len(env.run(sql)[1]) <= 20


def test_comments_are_dropped(env):
    sql = env("SELECT 1 AS one -- */ ; DROP TABLE customers", "viewer").sql
    assert "drop" not in sql.lower()


@pytest.mark.parametrize("sql,masked", [
    ("SELECT customer_id, full_name AS who FROM customers", "who"),
    ("WITH k AS (SELECT full_name AS n FROM customers) SELECT n FROM k", "n"),
    ("SELECT DISTINCT full_name FROM customers", "full_name"),
    ("SELECT region FROM customers UNION SELECT full_name FROM customers", "region"),
    ("SELECT (SELECT max(full_name) FROM customers) AS m", "m"),
])
def test_mask_role_wraps_outer_projection(env, sql, masked):
    result = env(sql, "auditor")
    assert result.ok, result.reasons
    low = result.sql.lower()
    assert low.count("select") >= sql.lower().count("select") + 1
    assert "'<hidden>'" in low
    columns, rows = env.run(result.sql)
    assert masked in columns
    i = columns.index(masked)
    assert rows and all(row[i] == "<hidden>" for row in rows)
    assert not any(v in {"Ann", "Bob", "Cy"} for row in rows for v in row)


def test_mask_keeps_distinct_meaning(env):
    result = env("SELECT DISTINCT full_name FROM customers", "auditor")
    assert "distinct" in result.sql.lower()
    _, rows = env.run(result.sql)
    assert len(rows) == 3  # Ann, Bob, Cy: distinct inside, masked outside


def test_granted_pii_and_counts_are_not_masked(env):
    result = env("SELECT email, region FROM customers ORDER BY email", "auditor")
    assert result.ok
    assert "<hidden>" not in result.sql
    _, rows = env.run(result.sql)
    assert rows[0][0] == "a@x.io"
    result = env("SELECT region, count(DISTINCT full_name) AS n FROM customers GROUP BY region ORDER BY region",
                 "auditor")
    assert "<hidden>" not in result.sql
    assert env.run(result.sql)[1] == [("EU", 2), ("US", 2)]


def test_mask_role_still_cannot_select_star(env):
    assert "STAR" in env("SELECT * FROM customers", "auditor").codes
