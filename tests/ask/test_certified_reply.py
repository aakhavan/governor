"""certified.answer_reply is the path of certified.answer after the model's choice (batch2d section 23)."""

from __future__ import annotations

import datetime as dt
import json
from decimal import Decimal

import pytest

from governor.ask import certified as c
from governor.ask.llm_testing import FakeLLM

AT = dt.datetime(2026, 11, 5, 12, 0, tzinfo=dt.timezone.utc)
CERTIFIED = [
    ("cohort_retention", "kpi_cohort_retention", "Monthly cohort retention", "Share retained.", "cohort_month",
     ["retention"], "Owner A", "platform", "https://example.test/ret", "certifier", AT, "c0ffee"),
    ("gmv", "kpi_gmv", "Gross merchandise value", "Item price plus freight.", "month", ["gmv"], "Owner A",
     "platform", "https://example.test/gmv", "certifier", AT, "c0ffee"),
]
GAPS = [("conversion_rate", ["sessions"], ["web analytics"], "Load session data from the web analytics tool.")]
COLUMNS = {
    "kpi_gmv": [("month", "timestamp without time zone"), ("gmv", "numeric")],
    "kpi_cohort_retention": [("cohort_month", "timestamp without time zone"), ("months_since_first", "numeric"),
                             ("retention", "numeric")],
}
ROWS = [[dt.datetime(2026, 1, 1), Decimal("455.0")]]


class FakeAdapter:
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


@pytest.mark.parametrize("data, results", [
    ({"kpi_id": "gmv", "value_column": "gmv", "period": {"kind": "month", "value": "2026-01"}}, [ROWS]),
    ({"kpi_id": "gmv", "period": {"kind": "all"}, "pick": "max"}, [ROWS]),
    ({"kpi_id": "gmv", "period": {"kind": "month", "value": "2026-01"}, "months_since_first": 2}, [ROWS]),
    ({"kpi_id": "cohort_retention", "period": {"kind": "year", "value": "2026"}, "months_since_first": 1},
     [[[dt.datetime(2026, 1, 1), Decimal("0.25")], [dt.datetime(2026, 2, 1), Decimal("0.3")]]]),
    ({"kpi_id": "conversion_rate", "category": "not_available"}, []),
    ({"kpi_id": "gmv", "value_column": "customer_id"}, []),
    ({"kpi_id": "nope"}, []),
    ({"category": "person_level"}, []),
    ({"category": "out_of_scope"}, []),
])
def test_answer_reply_matches_answer(data, results):
    data = {"category": "answer", **data}
    via_answer = FakeAdapter(results)
    a = c.answer("question", "analyst", FakeLLM([json.dumps(data)]), via_answer)
    via_reply = FakeAdapter(results)
    b = c.answer_reply(c.CertifiedReply.model_validate(data), "analyst", via_reply)
    assert a == b
    assert via_answer.kpi_queries() == via_reply.kpi_queries()
    assert all(role == "governor_analyst" for _, role in via_reply.calls)
