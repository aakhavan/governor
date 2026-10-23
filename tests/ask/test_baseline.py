"""Baseline with FakeLLM: one prompt with the full schema, SQL or refusal, nothing else."""

from __future__ import annotations

import json

from governor.ask.baseline import PROMPT_FILE, BaselineSystem, mart_schema, parse_reply
from governor.ask.llm_testing import FakeLLM
from governor.core.llm import usage_from_message
from governor.eval.golden import Question
from governor.eval.systems import get_system, limits

QUESTION = "Fixture: how many widgets shipped to Atlantis?"


def ask(*replies: str):
    llm = FakeLLM(list(replies))
    return BaselineSystem(llm=llm).answer(QUESTION, "analyst"), llm


def test_fake_llm_default_is_select_1_and_costs_nothing():
    llm = FakeLLM()
    message = llm.invoke("hello")
    assert message.content == "SELECT 1"
    assert usage_from_message(message)["cost_usd"] == 0.0
    assert llm.calls == ["hello"]
    scripted = FakeLLM(["a", "b"], default="z")
    assert [scripted.invoke("p").content for _ in range(3)] == ["a", "b", "z"]
    assert FakeLLM(lambda p: p.upper()).invoke("abc").content == "ABC"


def test_schema_lists_every_mart_with_types_and_descriptions():
    schema = mart_schema()
    for mart in ("dim_accounts", "fct_invoices", "fct_revenue_daily", "mrr_monthly"):
        assert f"### {mart}" in schema
    assert "- contact_email (VARCHAR):" in schema
    assert "### stg_" not in schema and "### int_" not in schema


def test_one_prompt_with_schema_and_question():
    out, llm = ask()
    assert len(llm.calls) == 1
    prompt = llm.calls[0]
    assert QUESTION in prompt and mart_schema() in prompt
    assert "2026-10-22" in prompt
    assert "{schema}" in PROMPT_FILE.read_text(encoding="utf-8")
    assert out.behaviour == "answer" and out.sql == "SELECT 1" and out.rows == [(1,)]
    assert out.cost_usd == 0.0 and out.error is None


def test_json_sql_reply_runs_read_only_with_the_row_cap():
    out, _ = ask(json.dumps({"action": "sql", "sql": "SELECT account_id FROM fct_invoices"}))
    assert out.behaviour == "answer" and out.error is None
    assert len(out.rows) == limits()["row_cap"]


def test_refusal_and_bad_replies():
    out, _ = ask('```json\n{"action": "refuse", "reason": "not in the data"}\n```')
    assert out.behaviour == "refuse" and out.sql is None
    out, _ = ask("I am not sure.")
    assert out.behaviour == "answer" and out.error == "unparseable model reply"
    out, _ = ask("SELECT nope FROM nowhere")
    assert out.behaviour == "answer" and out.error and out.rows == []


def test_no_policy_the_baseline_runs_whatever_it_is_given():
    out, _ = ask("SELECT contact_email FROM dim_accounts LIMIT 2")
    assert out.behaviour == "answer" and len(out.rows) == 2


def test_parse_reply_accepts_fenced_sql_and_question_objects():
    assert parse_reply("```sql\nSELECT 2;\n```").sql == "SELECT 2"
    assert parse_reply('{"action": "sql"}') is None
    q = Question(id="f1", role="analyst", category="unanswerable", question=QUESTION, expect="unanswerable")
    system = get_system("baseline", llm=FakeLLM())
    assert system.name == "baseline" and system.answer(q, q.role).behaviour == "answer"
