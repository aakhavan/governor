"""The Streamlit pages over the API (asgi, FakeLLM): answer card, clarify flow, traces, developer, login hint."""

from __future__ import annotations

import json

from governor.ask.llm_testing import scripted

QUESTION = "how many accounts are there"
SQL = "SELECT count(*) AS accounts FROM dim_accounts"


def plan_json(intent: str = "answer", **extra) -> str:
    return json.dumps({"intent": intent, "models": ["dim_accounts"], **extra})


def answering_llm(*plans: str):
    return scripted({
        "plan": list(plans) or [plan_json()],
        "sql": [json.dumps({"sql": SQL})],
        "answer": [json.dumps({"text_with_placeholders": "There are {r0c0} accounts."})],
    })


def ask(at, question: str = QUESTION):
    at.run()
    at.text_area[0].input(question)
    at.button[0].click()
    at.run()
    return at


def markdown(at) -> str:
    return "\n".join(m.value for m in at.markdown)


def test_ask_page_answers_with_fake_llm(page, use_api):
    use_api(llm=answering_llm())
    at = ask(page("pages/1_Ask.py"))
    assert not at.exception
    result = at.session_state["ask_result"]
    assert result["status"] == "answered"
    assert "There are" in markdown(at) and "accounts." in markdown(at)
    table = at.dataframe[0].value
    assert list(table.columns) == ["accounts"] and len(table) == 1
    assert result["sql"] and any(c.value == result["sql"] for c in at.code)  # SQL in the expander
    assert "dim_accounts" in markdown(at)
    assert "thread_id" not in at.session_state


def test_ask_page_clarify_flow(page, use_api):
    use_api(llm=answering_llm(plan_json("clarify", missing_slot="Active accounts only, or all of them?"), plan_json()))
    at = ask(page("pages/1_Ask.py"))
    assert not at.exception
    thread_id = at.session_state["thread_id"]
    assert any("Active accounts only" in i.value for i in at.info)
    assert not at.dataframe

    at.run()  # a rerun keeps the pending clarification and does not ask again
    assert at.session_state["thread_id"] == thread_id
    assert any("Active accounts only" in i.value for i in at.info)
    assert len(at.text_area) == 0

    reply = [t for t in at.text_input if t.label == "Your reply"][0]
    reply.input("all of them")
    [b for b in at.button if b.label == "Send reply"][0].click()
    at.run()
    assert not at.exception
    result = at.session_state["ask_result"]
    assert result["status"] == "answered" and result["thread_id"] == thread_id
    assert "thread_id" not in at.session_state
    assert list(at.dataframe[0].value.columns) == ["accounts"]


def test_trace_explorer_lists_rows(page, use_api):
    use_api(llm=answering_llm())
    ask(page("pages/1_Ask.py"))
    ask(page("pages/1_Ask.py"))
    at = page("pages/2_Trace_explorer.py")
    at.run()
    assert not at.exception
    assert len(at.dataframe[0].value) == 2
    assert at.selectbox[0].label == "Outcome"
    assert [m.value for m in at.metric][0] == "answer"
    assert any(c.value == SQL for c in at.code)  # SQL attempt in the detail view

    at.selectbox[0].select("refused_policy")
    at.run()
    assert not at.dataframe
    assert any("No traces" in i.value for i in at.info)


def test_developer_page_renders(page):
    at = page("pages/3_Developer.py")
    at.run()
    assert not at.exception
    assert "in-process (asgi)" in markdown(at)
    assert at.json[0].value and json.loads(at.json[0].value)["as_of"].startswith("2026-10-22")
    assert any("mask_value" in c.value for c in at.code)  # access.yaml shown read-only
    assert "test-analyst-token" not in markdown(at)


def test_no_token_shows_login_hint(page):
    for name in (None, "pages/1_Ask.py", "pages/2_Trace_explorer.py"):
        at = page(name, token=None)
        at.run()
        assert not at.exception
        assert any("API token" in i.value for i in at.info), name
    ask_page = page("pages/1_Ask.py", token=None)
    ask_page.run()
    assert len(ask_page.text_area) == 0  # no question box without a token
