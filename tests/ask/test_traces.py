"""Decision traces, the trace store, and the ask CLI resuming in a new process (offline)."""

from __future__ import annotations

import json
import logging
import os
import subprocess
import sys

import duckdb

from governor.ask import traces
from governor.ask.agent import to_output
from governor.ask.graph import build_graph
from governor.core import paths
from test_graph import (  # noqa: F401  (env is a fixture)
    ACCOUNTS,
    AS_OF,
    VALID_BY_REGION,
    Script,
    answer_json,
    env,
    plan_json,
    sql_json,
)

PII = [value for account in ACCOUNTS for value in account[2:]]


def ask(env, script, question, role="analyst", thread="t1", **options):
    graph = build_graph(llm=script.llm, **env, **options)
    return graph.invoke({"question": question, "role": role}, {"configurable": {"thread_id": thread}})


def store_dump(path) -> str:
    connection = duckdb.connect(str(path), read_only=True)
    try:
        return json.dumps(connection.execute("SELECT * FROM traces").fetchall(), default=str)
    finally:
        connection.close()


def test_trace_row_complete(env, monkeypatch):
    script = Script(
        plan=[plan_json()],
        sql=[sql_json(VALID_BY_REGION)],
        answer=[answer_json("{r0c0} billed {r0c1} euros.")],
    )
    question = "Billed amount by region?"
    out = ask(env, script, question)
    assert out["outcome"] == "answer" and out["trace_error"] is None

    row = traces.get_trace(out["trace"]["trace_id"])
    assert row is not None
    assert set(traces.TRACE_COLUMNS) <= set(row)
    unset = {"human_feedback"}
    assert [c for c in traces.TRACE_COLUMNS if c not in unset and row[c] is None] == []
    assert row["role"] == "analyst" and row["outcome"] == "answer"
    assert row["question_len"] == len(question) and len(row["question_hash"]) == 64
    assert row["answer"] == "North billed 215.75 euros."
    assert row["retrieved_ids"] and isinstance(row["sql_attempts"], list)
    assert row["models"] == ["FakeLLM"] and row["row_count"] == 2
    assert row["question_text"] is None  # text only on request

    # filters, newest first
    assert [t["trace_id"] for t in traces.list_traces(role="analyst", outcome="answer")] == [row["trace_id"]]
    assert traces.list_traces(role="finance_admin") == []
    assert traces.list_traces(outcome="refused_policy") == []

    monkeypatch.setenv("GOVERNOR_TRACE_TEXT", "1")
    script = Script(plan=[plan_json()], sql=[sql_json(VALID_BY_REGION)], answer=[answer_json("Done.")])
    second = ask(env, script, question, thread="t2")
    stored = traces.get_trace(second["trace"]["trace_id"])
    assert stored["question_text"] == question
    assert [t["trace_id"] for t in traces.list_traces(limit=1)] == [stored["trace_id"]]


def test_trace_never_stores_raw_pii(env, monkeypatch):
    monkeypatch.setenv("GOVERNOR_TRACE_TEXT", "1")
    # finance_admin: names are masked by the executor, the granted email is shown in the card
    script = Script(
        plan=[plan_json()],
        sql=[sql_json("SELECT account_id, contact_name, contact_email FROM accounts ORDER BY account_id")],
        answer=[answer_json("The first account is {r0c0}, contact {r0c1} at {r0c2}.")],
    )
    out = ask(env, script, "Who are the account contacts?", role="finance_admin")
    assert out["answer"]["text"] == "The first account is a1, contact ### at ann@x.io."
    stored = traces.get_trace(out["trace"]["trace_id"])
    assert stored["answer"] == "The first account is a1, contact ### at ###."

    # analyst: a literal email in the question and in the refused SQL
    script = Script(plan=[plan_json()], sql=[sql_json("SELECT region FROM accounts WHERE contact_email = 'bo@x.io'")])
    out = ask(env, script, "Which region is bo@x.io in?", thread="t2")
    assert out["outcome"] == "refused_policy"
    stored = traces.get_trace(out["trace"]["trace_id"])
    assert "###" in stored["question_text"] and "###" in json.dumps(stored["sql_attempts"])

    blob = store_dump(paths.TRACES)
    assert not [value for value in PII if value.lower() in blob.lower()]


def test_trace_write_failure_keeps_answer(env, tmp_path, caplog):
    script = Script(
        plan=[plan_json()],
        sql=[sql_json(VALID_BY_REGION)],
        answer=[answer_json("{r0c0} billed {r0c1} euros.")],
    )
    broken = tmp_path / "not-a-database"
    broken.mkdir()  # a directory: duckdb cannot open it as the trace store
    with caplog.at_level(logging.WARNING, logger="governor.ask.graph"):
        out = ask(env, script, "Billed amount by region?", trace_path=broken)
    assert out["outcome"] == "answer"
    assert out["answer"]["text"] == "North billed 215.75 euros."
    assert out["answer"]["rows"] == out["rows"]
    assert out["trace_error"] and out["trace"]["trace_id"]
    assert any("was not written" in r.getMessage() for r in caplog.records)
    assert "Billed" not in caplog.text  # the log does not carry the question


def _cli(args, state, *, parse=True):
    environment = {**os.environ, "GOVERNOR_STATE_DIR": str(state)}
    environment.pop("GOVERNOR_TRACE_TEXT", None)
    result = subprocess.run(
        [sys.executable, "-m", "governor.ask.run", *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=environment,
        timeout=240,
    )
    if not parse:
        return result
    assert result.returncode == 0, result.stderr[-2000:]
    return result, json.loads(result.stdout.strip().splitlines()[-1])


def test_resume_in_new_process(env, tmp_path):
    state = tmp_path / "state"
    cards = tmp_path / "cards.json"
    cards.write_text(json.dumps(env["cards"]), encoding="utf-8")
    fixture = ["--database", str(env["database"]), "--access", str(env["access_path"]),
               "--meta", str(env["meta_path"]), "--cards", str(cards), "--as-of", AS_OF.isoformat()]
    first = tmp_path / "first.json"
    first.write_text(json.dumps({"plan": [plan_json("clarify", missing_slot="By region or by account?")]}),
                     encoding="utf-8")
    second = tmp_path / "second.json"
    second.write_text(json.dumps({
        "plan": [plan_json()],
        "sql": [sql_json(VALID_BY_REGION)],
        "answer": [answer_json("The first region, {r0c0}, billed {r0c1} euros.")],
    }), encoding="utf-8")

    paused, summary = _cli(["Show billed totals please", "--role", "analyst", "--thread", "cli-1",
                            "--llm", f"fake:{first}", *fixture], state)
    assert summary == {"outcome": "clarify", "trace_id": None, "thread_id": "cli-1"}
    assert "By region or by account?" in paused.stdout
    assert (state / "checkpoints.sqlite").is_file()

    done, summary = _cli(["--resume", "cli-1", "--answer", "by region", "--llm", f"fake:{second}", *fixture], state)
    assert summary["outcome"] == "answer" and summary["thread_id"] == "cli-1"
    assert "The first region, North, billed 215.75 euros." in done.stdout
    stored = traces.get_trace(summary["trace_id"], path=state / "traces.duckdb")
    assert stored is not None and stored["outcome"] == "answer"

    # a finished thread is not resumed twice
    rerun = _cli(["--resume", "cli-1", "--answer", "x", "--llm", "fake", *fixture], state, parse=False)
    assert rerun.returncode == 1


def test_agent_output_mapping():
    paused = to_output({"__interrupt__": [object()], "usage": [{"tokens_in": 3, "tokens_out": 1, "cost_usd": 0.0}]})
    assert paused.behaviour == "clarify" and paused.tokens_in == 3 and paused.sql is None
    refused = to_output({"outcome": "refused_policy", "sql_attempts": [{"stage": "validate", "codes": ["PII_FORBIDDEN"]}]})
    assert refused.behaviour == "refuse"
    failed = to_output({"outcome": "refused_repair", "sql_attempts": [
        {"stage": "validate", "sql": "SELECT a", "codes": ["COLUMN_UNKNOWN"], "error": None},
        {"stage": "dry_run", "sql": "SELECT b", "codes": ["DRY_RUN_FAILED"], "error": "Binder Error"},
    ]})
    assert (failed.behaviour, failed.sql, failed.error) == ("answer", "SELECT b", "refused_repair")
    assert failed.sql_attempts == 2 and failed.first_sql_error == "COLUMN_UNKNOWN"
    answered = to_output({"outcome": "answer", "executed_sql": "SELECT 1 LIMIT 5", "columns": ["x"], "rows": [[1]],
                          "sql_attempts": [{"stage": "execute", "sql": "SELECT 1", "codes": [], "error": None}]})
    assert answered.rows == [(1,)] and answered.first_sql_error is None and answered.sql_attempts == 1
