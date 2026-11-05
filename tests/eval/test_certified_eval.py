"""Certified-answer evaluation (batch2b section 15), offline: a stub answerer and the fake LLM."""
import json

from langchain_core.messages import AIMessage

from governor.ask.llm_testing import FakeLLM
from governor.eval import certified_eval as ce

SET = """version: 1
questions:
  - {id: t1, question: 'GMV in January?', outcome: answer, kpi: gmv, expected: 455.0, tol: 0.01}
  - {id: t2, question: 'Best GMV month?', outcome: answer, kpi: gmv, expected: 500, tol: 0, expected_period: '2026-02'}
  - {id: t3, question: 'Conversion rate?', outcome: not_available, kpi: conversion_rate}
  - {id: t4, question: 'Next month GMV?', outcome: unanswerable}
  - {id: t5, question: 'Customer ids?', outcome: refused}
"""


def _ans(outcome, value=None, kpi=None, text=""):
    return {"outcome": outcome, "value": value, "kpi_id": kpi, "text": text, "sql": None, "citation": None}


def test_score_answer_within_tolerance():
    q = {"outcome": "answer", "expected": 455.0, "tol": 0.01}
    assert ce.score(q, _ans("answer", 455.004))["pass"]
    s = ce.score(q, _ans("answer", 456.0))
    assert not s["pass"] and s["outcome_ok"] and s["value_ok"] is False


def test_score_answer_wrong_outcome_fails_value_too():
    s = ce.score({"outcome": "answer", "expected": 1, "tol": 0}, _ans("unanswerable"))
    assert not s["pass"] and not s["outcome_ok"] and s["value_ok"] is False


def test_score_expected_period_must_be_named():
    q = {"outcome": "answer", "expected": 500, "tol": 0, "expected_period": "2026-02"}
    assert ce.score(q, _ans("answer", 500, text="highest in 2026-02"))["pass"]
    assert not ce.score(q, _ans("answer", 500, text="highest in 2026-01"))["pass"]


def test_score_not_available_needs_the_kpi():
    q = {"outcome": "not_available", "kpi": "gross_margin"}
    assert ce.score(q, _ans("not_available", kpi="gross_margin"))["pass"]
    assert not ce.score(q, _ans("not_available", kpi="conversion_rate"))["pass"]


def test_score_unanswerable_and_refused():
    assert ce.score({"outcome": "unanswerable"}, _ans("unanswerable"))["pass"]
    assert ce.score({"outcome": "refused"}, _ans("refused"))["pass"]
    assert not ce.score({"outcome": "refused"}, _ans("answer", 3))["pass"]
    assert not ce.score({"outcome": "unanswerable"}, _ans("error"))["pass"]


def test_evaluate_report(tmp_path):
    path = tmp_path / "q.yaml"
    path.write_text(SET, encoding="utf-8")
    replies = {
        "GMV in January?": _ans("answer", 455.0, "gmv"),
        "Best GMV month?": _ans("answer", 499.0, "gmv", "in 2026-02"),
        "Conversion rate?": _ans("not_available", kpi="conversion_rate"),
        "Next month GMV?": _ans("unanswerable"),
        "Customer ids?": _ans("answer", 1.0),
    }
    report = ce.evaluate(path, "analyst", replies.__getitem__)
    s = report["summary"]
    assert report["kind"] == "certified_eval" and len(report["set_sha256"]) == 64
    assert [i["pass"] for i in report["items"]] == [True, False, True, True, False]
    assert s["questions"] == 5 and s["passed"] == 3
    assert s["outcome_correct"] == 4 and s["outcome_accuracy"] == 0.8
    assert s["answerable"] == 2 and s["value_correct"] == 1 and s["value_accuracy"] == 0.5
    assert s["confusion"]["refused"] == {"answer": 1}
    assert json.dumps(report).count('"pass": true') == 3


def test_metered_llm_records_cost():
    meter = ce.MeteredLLM(FakeLLM(["{}", "{}"]))
    meter.invoke("a")
    meter.invoke("b")
    assert ce.cost_of(meter.usage) == (0.0, 0)
    assert not hasattr(meter, "with_structured_output")  # FakeLLM has none: certified.choose uses invoke


def test_metered_llm_structured_raw_cost():
    class Structured:
        def invoke(self, prompt):
            raw = AIMessage(content="{}", response_metadata={"token_usage": {"cost": 0.25}})
            return {"raw": raw, "parsed": None}

    class Chat:
        model_name = "x/model"

        def invoke(self, prompt):
            return AIMessage(content="{}")

        def with_structured_output(self, schema, include_raw=False):
            return Structured()

    meter = ce.MeteredLLM(Chat())
    meter.with_structured_output(dict, include_raw=True).invoke("q")
    meter.invoke("q")
    assert ce.cost_of(meter.usage) == (0.25, 1)
    assert meter.model_name() == "x/model"


def test_ask_one_turns_errors_into_outcome(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("database down\nmore")

    monkeypatch.setattr(ce.certified, "answer", boom)
    out = ce.ask_one("q", "analyst", None, None)
    assert out["outcome"] == "error" and "database down" in out["text"] and "more" not in out["text"]
