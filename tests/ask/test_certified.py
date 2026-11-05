"""Certified answers (batch2b section 14): SQL builder, outcomes, validator allowlist, API, live registry."""

from __future__ import annotations

import datetime as dt
import json
import os
from decimal import Decimal

import pytest

from governor.ask import certified as c
from governor.ask.llm_testing import FakeLLM

AT = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)
CERTIFIED = [
    ("gmv", "kpi_gmv", "Gross merchandise value", "Item price plus freight.", "month", ["gmv"], "Amir (analytics)",
     "platform", "https://example.test/gmv", "amir", AT, "abc123"),
    ("cohort_retention", "kpi_cohort_retention", "Monthly cohort retention", "Share retained.", "cohort_month",
     ["retention"], "Amir (analytics)", "platform", "https://example.test/ret", "amir", AT, "abc123"),
    ("repeat_purchase_rate", "kpi_repeat_purchase_rate", "Repeat purchase rate", "Share repeating.", "total",
     ["customers", "repeat_purchase_rate"], "Amir (analytics)", "platform", "https://example.test/rpr", "amir", AT,
     "abc123"),
]
GAPS = [("conversion_rate", ["sessions"], ["web analytics"], "Load session data from the web analytics tool.")]
COLUMNS = {
    "kpi_gmv": [("month", "timestamp without time zone"), ("gmv", "numeric")],
    "kpi_cohort_retention": [("cohort_month", "timestamp without time zone"), ("months_since_first", "numeric"),
                             ("retention", "numeric"), ("incomplete_month", "boolean")],
    "kpi_repeat_purchase_rate": [("customers", "bigint"), ("repeat_purchase_rate", "numeric")],
    "governor_certified": [("kpi_id", "text")],
    "governor_gaps": [("kpi_id", "text")],
}


class FakeAdapter:
    """Answers the registry reads from the fixtures above and KPI queries from ``results``."""

    def __init__(self, results=None):
        self.results = list(results or [])
        self.calls: list[tuple[str, str | None]] = []

    def run(self, sql_text, *, timeout_s, row_cap, native=False, role=None):
        self.calls.append((sql_text, role))
        if "governor_certified" in sql_text and "information_schema" not in sql_text:
            return ["kpi_id"], [list(r) for r in CERTIFIED]
        if "governor_gaps" in sql_text:
            return ["kpi_id"], [list(r) for r in GAPS]
        if "information_schema.columns" in sql_text:
            return ["t", "c", "d"], [[t, col, typ] for t, cols in COLUMNS.items() for col, typ in cols]
        return ["grain_value", "kpi_value"], self.results.pop(0) if self.results else []

    def kpi_queries(self):
        return [s for s, _ in self.calls if "information_schema" not in s and "governor_" not in s]


def reply(kpi=None, col=None, kind="month", value="2026-01", pick="value", category="answer", msf=None):
    return json.dumps({"kpi_id": kpi, "value_column": col, "period": {"kind": kind, "value": value},
                       "months_since_first": msf, "pick": pick, "category": category})


@pytest.fixture
def registry():
    return c.read_registry(FakeAdapter(), "analyst")


def build(registry, kpi, **kw):
    sql, _ = c.build_sql(registry.kpis[kpi], registry.schema, c.CertifiedReply.model_validate(json.loads(reply(kpi, **kw))))
    checked = c.validate(sql, c.certified_policy(registry))
    assert checked.ok, (sql, checked.reasons)
    return checked.sql


# --------------------------------------------------------------------------- SQL builder


def test_builder_month(registry):
    sql = build(registry, "gmv", col="gmv")
    assert '"serve_analyst"."kpi_gmv"' in sql and "TO_CHAR(\"month\", 'YYYY-MM') = '2026-01'" in sql


def test_builder_year(registry):
    sql = build(registry, "gmv", col="gmv", kind="year", value="2026", pick="sum")
    assert 'SUM("gmv")' in sql and 'EXTRACT(YEAR FROM "month") = 2026' in sql


def test_builder_all_on_total_grain(registry):
    sql = build(registry, "repeat_purchase_rate", col="repeat_purchase_rate", kind="all", value=None)
    assert "WHERE" not in sql and '"kpi_repeat_purchase_rate"' in sql


def test_builder_cohort(registry):
    sql = build(registry, "cohort_retention", col="retention", kind="cohort", value="2026-01", msf=1)
    assert "(TO_CHAR(\"cohort_month\", 'YYYY-MM'), \"months_since_first\") = ('2026-01', 1)" in sql


def test_builder_max(registry):
    sql = build(registry, "gmv", col="gmv", kind="all", value=None, pick="max")
    assert 'ORDER BY "gmv" DESC NULLS LAST LIMIT 1' in sql


def test_builder_sum(registry):
    sql = build(registry, "gmv", col="gmv", kind="all", value=None, pick="sum")
    assert 'SUM("gmv")' in sql and "WHERE" not in sql


@pytest.mark.parametrize("kw", [
    dict(col="customer_id"),                                   # not a value column
    dict(col="month"),                                         # the grain column is not a value
    dict(col="gmv", kind="cohort"),                            # month grain cannot express a cohort
    dict(col="gmv", value="2026-13"),                          # not a month
    dict(col="gmv", value="2026-01'; DROP TABLE x; --"),       # never reaches SQL
    dict(col="gmv", kind="year", value="2026"),                # many rows, pick value
    dict(col="gmv", msf=2),                                    # no months_since_first column
])
def test_builder_refuses_what_the_kpi_cannot_express(registry, kw):
    with pytest.raises(c.Unanswerable):
        c.build_sql(registry.kpis["gmv"], registry.schema, c.CertifiedReply.model_validate(json.loads(reply("gmv", **kw))))


def test_builder_cohort_needs_months_since_first(registry):
    with pytest.raises(c.Unanswerable):
        c.build_sql(registry.kpis["cohort_retention"], registry.schema,
                    c.CertifiedReply.model_validate(json.loads(reply("cohort_retention", "retention", kind="cohort"))))


# --------------------------------------------------------------------------- validator


@pytest.mark.parametrize("sql", [
    "SELECT kpi_id FROM serve_analyst.governor_certified",           # registry is not a certified model
    "SELECT customer_unique_id FROM serve_analyst.stg_customers",     # silver is not certified
    "SELECT gmv FROM analytics.kpi_gmv",                              # not the serving schema
    "SELECT gmv FROM serve_finance_admin.kpi_gmv",                    # another role's schema
    "SELECT gmv FROM kpi_gmv",                                        # unqualified
    "SELECT * FROM serve_analyst.kpi_gmv",
    "SELECT set_config('role', 'governor_finance_admin', true) FROM serve_analyst.kpi_gmv",
])
def test_validator_refuses_outside_the_certified_allowlist(registry, sql):
    assert not c.validate(sql, c.certified_policy(registry)).ok


def test_allowlist_is_the_certified_models(registry):
    assert set(c.certified_policy(registry).models) == {"kpi_gmv", "kpi_cohort_retention", "kpi_repeat_purchase_rate"}


# --------------------------------------------------------------------------- outcomes


def ask(question, *replies, results=None, role="analyst"):
    adapter = FakeAdapter(results)
    out = c.answer(question, role, FakeLLM(list(replies)), adapter)
    return out, adapter


def test_answer_fills_numbers_and_cites():
    out, adapter = ask("GMV in January 2026?", reply("gmv", "gmv"), results=[[[dt.datetime(2026, 1, 1), Decimal("455.0")]]])
    assert out.outcome == "answer" and out.value == 455.0 and "455" in out.text
    assert out.citation["kpi_id"] == "gmv" and out.citation["certified_by"] == "amir"
    assert out.citation["owner"] and out.citation["source_tier"] == "platform" and out.citation["source_ref"]
    assert out.sql and len(adapter.kpi_queries()) == 1
    assert all(role == "governor_analyst" for _, role in adapter.calls)


def test_model_never_sees_data_values():
    llm = FakeLLM([reply("gmv", "gmv")])
    c.answer("GMV?", "analyst", llm, FakeAdapter([[[dt.datetime(2026, 1, 1), Decimal("455.0")]]]))
    assert "455" not in llm.calls[0] and "gmv" in llm.calls[0] and "sessions" in llm.calls[0]


def test_max_names_the_period():
    out, _ = ask("Best GMV month?", reply("gmv", "gmv", kind="all", value=None, pick="max"),
                 results=[[[dt.datetime(2026, 3, 1), Decimal("900.5")]]])
    assert out.outcome == "answer" and out.value == 900.5 and "2026-03" in out.text and "900.50" in out.text


def test_uncertified_kpi_is_unanswerable_and_never_runs():
    out, adapter = ask("GMV please", reply("stg_customers", "customer_unique_id"))
    assert out.outcome == "unanswerable" and not out.sql and not adapter.kpi_queries()


def test_non_value_column_is_unanswerable_and_never_runs():
    out, adapter = ask("GMV please", reply("gmv", "customer_id"))
    assert out.outcome == "unanswerable" and not out.sql and not adapter.kpi_queries()


def test_declined_kpi_quotes_its_gap():
    out, adapter = ask("Conversion rate?", reply("conversion_rate", None, category="not_available"))
    assert out.outcome == "not_available" and out.kpi_id == "conversion_rate"
    assert "sessions" in out.text and "Load session data" in out.text and not adapter.kpi_queries()


def test_catalogue_kpi_without_gap_is_not_available():
    out, _ = ask("Gross margin?", reply("gross_margin", "gross_margin"))  # in the catalogue, not certified, no gap row
    assert out.outcome == "not_available" and "not certified" in out.text


def test_person_level_is_refused():
    out, adapter = ask("List customer ids", reply(None, None, category="person_level"))
    assert out.outcome == "refused" and not out.sql and not adapter.kpi_queries()


def test_out_of_scope_is_unanswerable():
    out, _ = ask("Forecast GMV", reply(None, None, category="out_of_scope"))
    assert out.outcome == "unanswerable" and not out.sql


def test_unparseable_reply_is_unanswerable():
    out, adapter = ask("GMV?", "SELECT * FROM serve_analyst.stg_customers")
    assert out.outcome == "unanswerable" and not out.sql and not adapter.kpi_queries()


def test_fake_script_loader(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(json.dumps({"certified": [reply("gmv", "gmv")]}), encoding="utf-8")
    llm = c.make_llm(f"fake:{p}")
    assert c.choose(llm, "x").kpi_id == "gmv"


# --------------------------------------------------------------------------- API


def test_api_certified_route(monkeypatch):
    from fastapi.testclient import TestClient

    from governor.api.app import create_app
    from governor.ask import service

    adapter = FakeAdapter([[[dt.datetime(2026, 1, 1), Decimal("455.0")]]])
    monkeypatch.setattr(c, "default_adapter", lambda: adapter)
    app = create_app(tokens="analyst:tok-a", llm=FakeLLM([reply("gmv", "gmv")]))
    try:
        client = TestClient(app, raise_server_exceptions=False)
        assert client.post("/v1/ask/certified", json={"question": "GMV?"}).status_code == 401
        assert client.post("/v1/ask/certified", json={"question": "GMV?", "role": "finance_admin"},
                           headers={"Authorization": "Bearer tok-a"}).status_code == 422
        r = client.post("/v1/ask/certified", json={"question": "GMV?"}, headers={"Authorization": "Bearer tok-a"})
        assert r.status_code == 200 and r.json()["outcome"] == "answer" and r.json()["value"] == 455.0
        assert all(role == "governor_analyst" for _, role in adapter.calls)
    finally:
        service.reset()


# --------------------------------------------------------------------------- live (test bed)


def _live_registry():
    if not os.environ.get("GOVERNOR_PG_DSN"):
        return None
    try:
        reg = c.read_registry(c.default_adapter(), "analyst")
    except Exception:  # noqa: BLE001 - no database or no certified build: skip
        return None
    return reg if "gmv" in reg.kpis else None


@pytest.mark.skipif(_live_registry() is None, reason="needs the test bed with a certified sample build")
@pytest.mark.parametrize("role", ["analyst", "finance_admin"])
def test_live_gmv_for_the_sample_month(role):
    out = c.answer("What was GMV in January 2026?", role, FakeLLM([reply("gmv", "gmv")]))
    assert out.outcome == "answer" and abs(out.value - 455.0) < 1e-6
    assert out.citation["kpi_id"] == "gmv" and out.citation["certified_by"]
