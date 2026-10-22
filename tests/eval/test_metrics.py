"""knowledge/metrics.yaml: shape, allowlisted marts, as_of-pinned dates, runs on green."""

from __future__ import annotations

import re

import pytest
import sqlglot
import yaml
from sqlglot import exp

from governor.core import paths
from governor.eval.checker import run_gold

FIELDS = {"id", "label", "definition", "sql", "grain", "time_column", "synonyms", "owner"}
REQUIRED = {
    "mrr",
    "arr",
    "active_subscriptions",
    "churned_subscriptions",
    "invoiced_revenue",
    "collected_revenue",
    "outstanding_receivables",
    "overdue_invoices",
}
METRICS = yaml.safe_load((paths.KNOWLEDGE / "metrics.yaml").read_text(encoding="utf-8"))["metrics"]
ALLOWED = set(yaml.safe_load((paths.KNOWLEDGE / "access.yaml").read_text(encoding="utf-8"))["allowlist"]["models"])
PII = set(yaml.safe_load((paths.KNOWLEDGE / "policy.yaml").read_text(encoding="utf-8")))


def test_shape():
    ids = [m["id"] for m in METRICS]
    assert len(ids) >= 8 and len(set(ids)) == len(ids)
    assert REQUIRED <= set(ids)
    for m in METRICS:
        assert set(m) == FIELDS, m["id"]
        assert isinstance(m["synonyms"], list) and m["synonyms"], m["id"]


@pytest.mark.parametrize("metric", METRICS, ids=lambda m: m["id"])
def test_sql_is_a_select_on_allowlisted_marts(metric):
    tree = sqlglot.parse_one(metric["sql"], read="duckdb")
    assert isinstance(tree, exp.Select)
    ctes = {c.alias_or_name for c in tree.find_all(exp.CTE)}
    assert {t.name for t in tree.find_all(exp.Table)} - ctes <= ALLOWED
    assert not list(tree.find_all(exp.Star))
    columns = {c.name for c in tree.find_all(exp.Column)}
    assert not columns & PII
    lowered = metric["sql"].lower()
    assert not any(w in lowered for w in ("now()", "current_date", "current_timestamp"))


@pytest.mark.parametrize("metric", METRICS, ids=lambda m: m["id"])
def test_date_literals_are_the_build_as_of(metric):
    as_of = paths.as_of().date().isoformat()
    for literal in re.findall(r"DATE '([0-9-]+)'", metric["sql"]):
        assert literal == as_of, f"{metric['id']}: re-pin DATE '{literal}' to as_of {as_of}"


@pytest.mark.parametrize("metric", METRICS, ids=lambda m: m["id"])
def test_sql_runs_and_returns_rows(metric):
    assert run_gold(metric["sql"])
