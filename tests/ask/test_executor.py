"""Read-only executor on a small fixture warehouse (own models, own PII tags, own limits)."""

from __future__ import annotations

import threading
import time

import duckdb
import pytest

from governor.ask import executor
from governor.ask.executor import QueryError, QueryTimeout, dry_run, execute, run_readonly

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
    ("model.shop.orders", "order_id", "INTEGER", None),
    ("model.shop.orders", "customer_id", "VARCHAR", None),
    ("model.shop.orders", "amount", "DECIMAL(18,2)", None),
]

CUSTOMERS = [
    ("c1", "a@x.io", "Ann", "EU"),
    ("c2", "b@x.io", "Bob", "EU"),
    ("c3", "c@x.io", "Cy", "US"),
    ("c4", "d@x.io", "Ann", "US"),
    ("c5", "e@x.io", "Dee", "US"),
]
ORDERS = 3000


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
    con.execute("CREATE SCHEMA marts")
    con.execute("CREATE TABLE marts.customers (customer_id VARCHAR, email VARCHAR, full_name VARCHAR, region VARCHAR)")
    con.executemany("INSERT INTO marts.customers VALUES (?, ?, ?, ?)", CUSTOMERS)
    con.execute(
        "CREATE TABLE marts.orders AS SELECT i::INTEGER AS order_id, 'c' || (i % 5 + 1) AS customer_id, "
        f"(i % 97)::DECIMAL(18,2) AS amount FROM range({ORDERS}) t(i)"
    )
    con.close()

    def run(sql, role):
        return execute(sql, role, access_path=access, meta_path=meta, database=warehouse)

    run.warehouse = warehouse
    return run


# --- execute: both roles --------------------------------------------------------

def test_viewer_aggregate_runs(env):
    result = env("SELECT region, count(DISTINCT email) AS n FROM customers GROUP BY region ORDER BY region", "viewer")
    assert result.ok, result.reasons
    assert result.columns == ["region", "n"]
    assert result.rows == [("EU", 2), ("US", 3)]
    assert result.row_count == 2


def test_viewer_pii_is_refused_without_rows(env):
    result = env("SELECT email FROM customers", "viewer")
    assert result.ok is False
    assert "PII_FORBIDDEN" in result.codes
    assert result.sql is None and result.rows == [] and result.row_count == 0


def test_unknown_role_is_refused(env):
    result = env("SELECT region FROM customers", "nobody")
    assert result.ok is False and result.codes == ["UNKNOWN_ROLE"] and not result.rows


def test_validator_rejects_writes_before_execution(env):
    result = env("DROP TABLE customers", "auditor")
    assert result.ok is False and "NOT_SELECT" in result.codes and result.sql is None


def test_executes_rewritten_sql_not_the_user_sql(env):
    result = env("SELECT 1 AS one -- ; DROP TABLE customers", "viewer")
    assert result.ok, result.reasons
    assert "--" not in result.sql and "drop" not in result.sql.lower()
    assert result.rows == [(1,)]


# --- masking ------------------------------------------------------------------------

def test_mask_role_sees_mask_for_hidden_pii(env):
    result = env("SELECT customer_id, full_name FROM customers ORDER BY customer_id", "auditor")
    assert result.ok, result.reasons
    assert [r[1] for r in result.rows] == ["<hidden>"] * len(CUSTOMERS)
    assert [r[0] for r in result.rows] == [c[0] for c in CUSTOMERS]


def test_mask_follows_lineage_through_functions_and_ctes(env):
    for sql, col in [
        ("SELECT upper(full_name) AS n FROM customers", "n"),
        ("WITH x AS (SELECT full_name AS k FROM customers) SELECT k FROM x", "k"),
    ]:
        result = env(sql, "auditor")
        assert result.ok, result.reasons
        i = result.columns.index(col)
        assert result.rows and all(r[i] == "<hidden>" for r in result.rows)


def test_granted_pii_is_not_masked(env):
    result = env("SELECT email FROM customers", "auditor")
    assert result.ok, result.reasons
    assert all("@" in r[0] for r in result.rows)


def test_distinct_row_count_unchanged_by_masking(env):
    result = env("SELECT DISTINCT full_name FROM customers", "auditor")
    assert result.ok, result.reasons
    assert result.row_count == len({c[2] for c in CUSTOMERS})
    assert all(r[0] == "<hidden>" for r in result.rows)


def test_count_distinct_pii_stays_a_number(env):
    result = env("SELECT region, count(DISTINCT full_name) AS n FROM customers GROUP BY region ORDER BY region",
                 "auditor")
    assert result.ok, result.reasons
    assert result.rows == [("EU", 2), ("US", 3)]


# --- LIMIT and row cap ------------------------------------------------------------

def test_default_limit_applies(env):
    result = env("SELECT order_id FROM orders", "viewer")
    assert result.ok and result.row_count == 7


def test_small_limit_is_kept(env):
    result = env("SELECT order_id FROM orders LIMIT 3", "viewer")
    assert result.ok and result.row_count == 3


def test_large_limit_is_lowered_to_row_cap(env):
    result = env("SELECT order_id FROM orders LIMIT 5000", "viewer")
    assert result.ok and result.row_count == 20


def test_run_readonly_fetches_at_most_row_cap(env):
    columns, rows = run_readonly("SELECT order_id FROM orders", timeout_s=5, row_cap=11, database=env.warehouse)
    assert columns == ["order_id"] and len(rows) == 11


# --- guards with the validator bypassed ------------------------------------------

def test_timeout_interrupts(env):
    sql = "SELECT count(*) FROM orders a, orders b, orders c WHERE a.amount + b.amount + c.amount > -1"
    with pytest.raises(QueryTimeout):
        run_readonly(sql, timeout_s=0.5, row_cap=10, database=env.warehouse)


@pytest.mark.parametrize("sql", [
    "CREATE TABLE zz AS SELECT 1 AS a",
    "INSERT INTO customers VALUES ('c9', 'z@x.io', 'Zed', 'EU')",
    "DROP TABLE orders",
])
def test_writes_refused_by_connection(env, sql):
    with pytest.raises(QueryError):
        run_readonly(sql, timeout_s=5, row_cap=10, database=env.warehouse)
    _, rows = run_readonly("SELECT count(*) FROM customers", timeout_s=5, row_cap=1, database=env.warehouse)
    assert rows == [(len(CUSTOMERS),)]


def test_external_access_disabled(env, tmp_path):
    secret = tmp_path / "secret.csv"
    secret.write_text("a\n1\n", encoding="utf-8")
    with pytest.raises(QueryError):
        run_readonly(f"SELECT a FROM read_csv('{secret.as_posix()}')", timeout_s=5, row_cap=10,
                     database=env.warehouse)


def test_configuration_is_locked(env):
    with pytest.raises(QueryError):
        run_readonly("SET enable_external_access = true", timeout_s=5, row_cap=10, database=env.warehouse)


def test_timeout_is_not_reported_for_ordinary_errors(env):
    with pytest.raises(QueryError) as info:
        run_readonly("SELECT nope FROM customers", timeout_s=5, row_cap=10, database=env.warehouse)
    assert not isinstance(info.value, QueryTimeout)


# --- dry run ---------------------------------------------------------------------------

def test_dry_run_bad_column(env):
    plan = dry_run("SELECT nope FROM customers", timeout_s=5, database=env.warehouse)
    assert plan.ok is False and plan.error


def test_dry_run_good_query_executes_nothing(env):
    assert dry_run("SELECT region FROM customers", timeout_s=5, database=env.warehouse).ok
    assert dry_run("CREATE TABLE zz AS SELECT 1 AS a", timeout_s=5, database=env.warehouse).ok is False


class _StuckConnection:
    """EXPLAIN that only returns when the connection is interrupted (a slow planner)."""

    def __init__(self) -> None:
        self.interrupted = threading.Event()
        self.closed = False

    def execute(self, sql):
        if not self.interrupted.wait(10):
            raise AssertionError("dry_run was never interrupted")
        raise duckdb.InterruptException("INTERRUPT Error: Interrupted!")

    def interrupt(self):
        self.interrupted.set()

    def close(self):
        self.closed = True


def test_dry_run_respects_timeout(env, monkeypatch):
    stuck = _StuckConnection()
    monkeypatch.setattr(executor, "_open", lambda database=None: stuck)
    started = time.monotonic()
    with pytest.raises(QueryTimeout):
        dry_run("SELECT region FROM customers", timeout_s=0.3, database=env.warehouse)
    assert time.monotonic() - started < 5 and stuck.closed

    # execute() passes the access.yaml timeout (5 s) to the dry run and reports TIMEOUT
    seen = {}

    def slow_plan(sql, *, timeout_s, database=None):
        seen["timeout_s"] = timeout_s
        raise QueryTimeout(f"query interrupted after {timeout_s}s")

    monkeypatch.setattr(executor, "dry_run", slow_plan)
    result = env("SELECT region FROM customers", "viewer")
    assert seen == {"timeout_s": 5.0}
    assert result.ok is False and result.codes == ["TIMEOUT"] and not result.rows


def test_hardening_settings_are_applied(env):
    con = executor._open(env.warehouse)
    try:
        settings = dict(con.execute(
            "SELECT name, value FROM duckdb_settings() WHERE name IN ('enable_external_access', "
            "'autoinstall_known_extensions', 'autoload_known_extensions', 'lock_configuration')"
        ).fetchall())
    finally:
        con.close()
    assert settings == {
        "enable_external_access": "false",
        "autoinstall_known_extensions": "false",
        "autoload_known_extensions": "false",
        "lock_configuration": "true",
    }
