"""Serving schemas and adapter timeout on the Postgres test bed.

Skips unless both GOVERNOR_PG_DSN (the governor_ask login) and
GOVERNOR_PG_ADMIN_DSN are set. Uses its own policy and access fixtures; loads
the synthetic sample into raw and applies the roles first (both idempotent).
"""

from __future__ import annotations

import importlib.util
import os
import re
import secrets
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "testbed" / "sample"

DSN = os.environ.get("GOVERNOR_PG_DSN")
ADMIN_DSN = os.environ.get("GOVERNOR_PG_ADMIN_DSN")
pytestmark = pytest.mark.skipif(not (DSN and ADMIN_DSN), reason="GOVERNOR_PG_DSN or GOVERNOR_PG_ADMIN_DSN unset")

POLICY = "customer_unique_id: person_id\ncustomer_city: location\nreview_comment_message: free_text\n"
ACCESS = """version: 1
allowlist:
  models: []
limits:
  default_limit: 10
  row_cap: 50
  timeout_s: 5
mask_value: "[masked]"
roles:
  analyst:
    pii: aggregate_only
    grants: []
  finance_admin:
    pii: mask
    grants:
      - olist_customers_dataset.customer_city
"""


def _module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def served(tmp_path_factory):
    import psycopg

    from governor.core import serving

    _module("apply_roles", ROOT / "testbed" / "apply_roles.py").apply(ADMIN_DSN)
    _module("load_olist", ROOT / "testbed" / "load_olist.py").load(SAMPLE, ADMIN_DSN)
    d = tmp_path_factory.mktemp("serving")
    (d / "policy.yaml").write_text(POLICY, encoding="utf-8")
    (d / "access.yaml").write_text(ACCESS, encoding="utf-8")
    policy = serving.load_policy(d / "policy.yaml", d / "access.yaml")
    salt = "testsalt" + secrets.token_hex(8)
    summary = serving.apply("raw", policy, dsn=ADMIN_DSN, salt=salt)
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        raw_ids = [r[0] for r in admin.execute("SELECT customer_unique_id FROM raw.olist_customers_dataset")]
        raw_cities = {r[0] for r in admin.execute("SELECT customer_city FROM raw.olist_customers_dataset")}
    return {"salt": salt, "summary": summary, "policy": policy, "raw_ids": raw_ids, "raw_cities": raw_cities}


def as_role(role: str, query: str):
    import psycopg

    with psycopg.connect(DSN) as c:
        c.execute(f"SET ROLE {role}")
        return c.execute(query).fetchall()


def denied(role: str, query: str) -> bool:
    import psycopg

    try:
        as_role(role, query)
    except psycopg.errors.InsufficientPrivilege:
        return True
    return False


def test_serving_apply_idempotent_and_salt_private(served):
    import psycopg

    from governor.core import serving

    again = serving.apply("raw", served["policy"], dsn=ADMIN_DSN, salt=served["salt"])
    assert again == served["summary"]
    with psycopg.connect(ADMIN_DSN, autocommit=True) as admin:
        defs = [r[0] for r in admin.execute("SELECT definition FROM pg_views WHERE schemaname LIKE 'serve\\_%'")]
        salts = admin.execute("SELECT salt FROM private.pii_salt").fetchall()
    assert len(defs) == 2 * served["summary"]["tables"]
    assert not any(served["salt"] in d for d in defs)
    assert salts == [(served["salt"],)]


def test_hashing_keeps_equality_and_count_distinct(served):
    raw_ids = served["raw_ids"]
    ids = [r[0] for r in as_role("governor_analyst", "SELECT customer_unique_id FROM serve_analyst.olist_customers_dataset")]
    assert ids and all(re.fullmatch(r"[0-9a-f]{64}", i) for i in ids)
    assert not set(ids) & set(raw_ids)
    # The same raw value hashes to the same digest: the duplicate-count profile survives.
    assert sorted(ids.count(i) for i in set(ids)) == sorted(raw_ids.count(i) for i in set(raw_ids))
    n = as_role(
        "governor_analyst", "SELECT count(DISTINCT customer_unique_id) FROM serve_analyst.olist_customers_dataset"
    )[0][0]
    assert n == len(set(raw_ids))


def test_mask_applies_and_grant_honoured(served):
    rows = as_role(
        "governor_finance_admin",
        "SELECT customer_unique_id, customer_city, customer_state FROM serve_finance_admin.olist_customers_dataset",
    )
    assert rows and all(r[0] == "[masked]" for r in rows)
    assert {r[1] for r in rows} == served["raw_cities"]  # granted column passes through
    assert all(r[2] and r[2] != "[masked]" for r in rows)  # non-PII passes through
    reviews = as_role(
        "governor_finance_admin",
        "SELECT review_comment_message FROM serve_finance_admin.olist_order_reviews_dataset",
    )
    assert reviews and all(r[0] == "[masked]" for r in reviews)


def test_reader_roles_isolated(served):
    for role, other in (("governor_analyst", "serve_finance_admin"), ("governor_finance_admin", "serve_analyst")):
        assert denied(role, f"SELECT 1 FROM {other}.olist_customers_dataset LIMIT 1")
        assert denied(role, "SELECT salt FROM private.pii_salt")
        assert denied(role, "SELECT 1 FROM raw.olist_customers_dataset LIMIT 1")
    # Without SET ROLE the ask login itself has no grants on serving views.
    import psycopg

    with psycopg.connect(DSN) as c, pytest.raises(psycopg.errors.InsufficientPrivilege):
        c.execute("SELECT 1 FROM serve_analyst.olist_customers_dataset LIMIT 1")


def test_adapter_reads_serving_view_as_role(served):
    from governor.core.adapters import get_adapter

    adapter = get_adapter("postgres", allowed_roles=["governor_analyst"])
    columns, rows = adapter.run(
        "SELECT count(DISTINCT customer_unique_id) AS n FROM serve_analyst.olist_customers_dataset",
        timeout_s=5,
        row_cap=10,
        role="governor_analyst",
    )
    assert columns == ["n"] and rows[0][0] == len(set(served["raw_ids"]))


def test_postgres_timeout_clamped():
    from governor.core.adapters.postgres import MAX_TIMEOUT_S, PostgresAdapter, _timeout_ms

    assert _timeout_ms(3600) == MAX_TIMEOUT_S * 1000
    assert _timeout_ms(float("inf")) == MAX_TIMEOUT_S * 1000
    assert _timeout_ms(float("nan")) == MAX_TIMEOUT_S * 1000
    assert _timeout_ms(0) == 1 and _timeout_ms(-5) == 1
    assert _timeout_ms(2.5) == 2500
    adapter = PostgresAdapter()
    _, rows = adapter.run("SELECT current_setting('statement_timeout') AS t", timeout_s=3600, row_cap=1)
    assert rows == [["10s"]]
    _, rows = adapter.run("SELECT current_setting('statement_timeout') AS t", timeout_s=2, row_cap=1)
    assert rows == [["2s"]]
