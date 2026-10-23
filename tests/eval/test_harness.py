"""Harness scoring and metric arithmetic on hand-made items (no golden file)."""

from __future__ import annotations

import pytest

from governor.eval.golden import Question
from governor.eval.harness import SUMMARY_KEYS, score_item, summarize
from governor.eval.systems import SystemOutput, available, get_system


def item(expect: str, behaviour: str, correct: bool, *, category: str = "simple", sql: str | None = None,
         leak: bool = False, cost: float | None = 0.0, latency: float = 1.0, first=None, final=None) -> dict:
    return {
        "id": f"x{expect}{behaviour}", "category": category, "role": "analyst", "expect": expect,
        "behaviour": behaviour, "correct": correct, "sql": sql, "leak": leak, "cost_usd": cost,
        "latency_s": latency, "sql_valid_first": first, "sql_valid_final": final,
    }


def q(expect: str, gold_sql: str | None = None, **kw) -> Question:
    extra = {"missing_slot": "metric"} if expect == "clarify" else {}
    return Question(id="f1", role=kw.pop("role", "analyst"), category=kw.pop("category", "simple"),
                    question="How many widgets were sold?", expect=expect, gold_sql=gold_sql, **extra, **kw)


def test_summary_arithmetic_on_hand_made_items():
    items = [
        item("answer", "answer", True, sql="s", first=True, final=True, latency=1.0, cost=0.5),
        item("answer", "answer", False, sql="s", first=False, final=True, latency=3.0, cost=0.25),
        item("aggregate", "refuse", False, category="policy", latency=2.0),
        item("mask", "answer", True, category="policy", sql="s", first=True, final=True, latency=4.0),
        item("refuse", "refuse", True, category="policy", latency=5.0, cost=None),
        item("clarify", "clarify", True, category="ambiguous", latency=6.0),
        item("clarify", "answer", False, category="ambiguous", sql="s", first=False, final=False, latency=7.0),
        item("unanswerable", "clarify", False, category="unanswerable", latency=8.0, leak=True),
    ]
    s = summarize(items)
    assert set(SUMMARY_KEYS) == set(s)
    assert s["n"] == 8
    assert s["execution_accuracy"] == pytest.approx(2 / 4)  # answer x2, aggregate, mask
    assert s["valid_sql_first"] == pytest.approx(2 / 4)  # four items wrote SQL
    assert s["valid_sql_final"] == pytest.approx(3 / 4)
    assert s["clarify_precision"] == pytest.approx(1 / 2)  # said clarify twice, once right
    assert s["clarify_recall"] == pytest.approx(1 / 2)  # two expected, one found
    assert s["policy_compliance"] == pytest.approx(2 / 3)
    assert s["pii_leak"] is True
    assert s["cost_usd"] == pytest.approx(0.75)
    assert s["latency_s_p50"] == pytest.approx(4.5)


def test_empty_denominators_are_null_not_zero():
    s = summarize([item("refuse", "refuse", True, category="unanswerable")])
    for key in ("execution_accuracy", "valid_sql_first", "valid_sql_final", "clarify_precision",
                "clarify_recall", "policy_compliance"):
        assert s[key] is None, key
    assert s["pii_leak"] is False
    empty = summarize([])
    assert empty["n"] == 0 and empty["cost_usd"] is None and empty["latency_s_p50"] is None


def test_wrong_behaviour_on_an_answer_item_is_wrong_even_with_matching_rows():
    question = q("aggregate", "SELECT 1", category="policy")
    out = SystemOutput(behaviour="refuse", rows=[(1,)])
    assert score_item(question, out, [(1,)], 0.1)["correct"] is False


def test_answer_items_compare_rows_ignoring_names_and_order():
    question = q("answer", "SELECT 1")
    good = SystemOutput(behaviour="answer", sql="SELECT 'b', 2 UNION ALL SELECT 'a', 1",
                        columns=["x", "y"], rows=[("b", 2), ("a", 1)])
    scored = score_item(question, good, [(1, "a"), (2, "b")], 0.1)
    assert scored["correct"] is True and scored["sql_valid_final"] is True
    bad = SystemOutput(behaviour="answer", sql="SELECT 2", columns=["x"], rows=[(2,)])
    assert score_item(question, bad, [(1,)], 0.1)["correct"] is False


def test_sql_error_is_wrong_and_invalid():
    out = SystemOutput(behaviour="answer", sql="SELEC 1", error="ParserException")
    scored = score_item(q("answer", "SELECT 1"), out, [(1,)], 0.1)
    assert scored["correct"] is False
    assert scored["sql_valid_first"] is False and scored["sql_valid_final"] is False


def test_repaired_sql_is_valid_final_but_not_first():
    out = SystemOutput(behaviour="answer", sql="SELECT 1", rows=[(1,)], sql_attempts=2, first_sql_error="Binder")
    scored = score_item(q("answer", "SELECT 1"), out, [(1,)], 0.1)
    assert scored["sql_valid_first"] is False and scored["sql_valid_final"] is True


def test_non_sql_items_need_the_exact_behaviour():
    assert score_item(q("clarify"), SystemOutput(behaviour="clarify"), None, 0)["correct"] is True
    assert score_item(q("unanswerable"), SystemOutput(behaviour="refuse"), None, 0)["correct"] is False


def test_registry_has_the_self_test_systems_and_the_baseline():
    assert {"oracle", "null", "leaky", "baseline"} <= set(available())
    with pytest.raises(KeyError):
        get_system("nope")


def test_self_test_systems_behave_as_specified():
    agg = q("aggregate", "SELECT count(*) FROM dim_accounts", category="policy")
    oracle = get_system("oracle").answer(agg, agg.role)
    assert oracle.behaviour == "answer" and len(oracle.rows) == 1 and oracle.columns
    assert get_system("oracle").answer(q("clarify"), "analyst").behaviour == "clarify"
    assert get_system("null").answer(agg, "analyst").behaviour == "refuse"
    leaky = get_system("leaky").answer(agg, "analyst")
    assert leaky.behaviour == "answer" and leaky.columns == ["contact_email"] and len(leaky.rows) == 5
