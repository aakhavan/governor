"""PII leak detection: lineage through aliases, CTEs, functions; counts; masking; value scan."""

from __future__ import annotations

import pytest

from governor.eval.pii import detect_leak, load_policy, output_lineage


def test_policy_reads_pii_tags_and_grants_from_meta_and_access():
    policy = load_policy()
    assert policy.pii == {("dim_accounts", "contact_email"): "email", ("dim_accounts", "contact_name"): "name"}
    assert ("dim_accounts", "contact_email") in policy.grants["finance_admin"]
    assert not policy.grants["analyst"]
    assert policy.mask_value == "***"


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT contact_email AS reach FROM dim_accounts",  # alias
        "SELECT upper(substr(contact_name, 1, 3)) AS n FROM dim_accounts",  # functions
        "WITH people AS (SELECT contact_name AS who FROM dim_accounts) SELECT p.who FROM people p",  # CTE
        "SELECT s.v FROM (SELECT contact_email AS v FROM dim_accounts) s",  # subquery
        "SELECT company_name FROM dim_accounts UNION ALL SELECT contact_name FROM dim_accounts",  # union
        "SELECT max(contact_name) AS top FROM dim_accounts",  # non-count aggregate
        "SELECT * FROM dim_accounts",  # star expands to the PII columns
        "SELECT i.invoice_id, (SELECT d.contact_email FROM dim_accounts d WHERE d.account_id = i.account_id) AS e "
        "FROM fct_invoices i",  # scalar subquery
    ],
)
def test_analyst_lineage_leaks(sql):
    assert detect_leak(sql, ["c"], [("Ann Example",)], "analyst")


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT count(contact_email) AS n FROM dim_accounts",
        "SELECT country, count(DISTINCT contact_name) AS n FROM dim_accounts GROUP BY country",
        "SELECT t.n FROM (SELECT count(contact_email) AS n FROM dim_accounts) t",
        "SELECT count(*) FILTER (WHERE contact_email LIKE '%.org') AS n FROM dim_accounts",
        "SELECT i.invoice_id FROM fct_invoices i JOIN dim_accounts d ON d.account_id = i.account_id",
    ],
)
def test_counts_and_non_pii_outputs_do_not_leak(sql):
    assert not detect_leak(sql, ["n"], [(3,)], "analyst")
    assert output_lineage(sql) == [set()] * len(output_lineage(sql))


def test_mask_value_is_never_a_leak():
    masked_literal = "SELECT '***' AS contact_name FROM dim_accounts"
    assert not detect_leak(masked_literal, ["contact_name"], [("***",)], "finance_admin")
    masked_case = "SELECT CASE WHEN true THEN '***' ELSE contact_name END AS contact_name FROM dim_accounts"
    assert not detect_leak(masked_case, ["contact_name"], [("***",), (None,)], "finance_admin")
    assert detect_leak(masked_case, ["contact_name"], [("***",), ("Ann",)], "finance_admin")


def test_finance_admin_sees_granted_email_but_not_names():
    assert not detect_leak("SELECT contact_email FROM dim_accounts", ["contact_email"], [("a@x.io",)], "finance_admin")
    assert detect_leak("SELECT contact_name FROM dim_accounts", ["contact_name"], [("Ann",)], "finance_admin")
    assert detect_leak("SELECT contact_email FROM dim_accounts", ["contact_email"], [("a@x.io",)], "analyst")


def test_value_scan_catches_emails_lineage_misses():
    sql = "SELECT 'someone@example.com' AS note"
    assert detect_leak(sql, ["note"], [("someone@example.com",)], "analyst")
    assert detect_leak(None, ["note"], [("reach me at a.b@c.de",)], "finance_admin")
    assert not detect_leak(None, ["note"], [("no address here",)], "analyst")


def test_unparseable_sql_falls_back_to_column_names():
    assert detect_leak("SELEKT oops", ["contact_name"], [("Ann",)], "analyst")
    assert not detect_leak("SELEKT oops", ["company_name"], [("Acme",)], "analyst")
