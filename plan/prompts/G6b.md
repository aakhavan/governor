# G6b: Persistence, decision traces, CLI and the agent system

The graph from G6a, made durable and measurable.

Build:
1. `src/governor/ask/traces.py`: `TRACE_COLUMNS` = `trace_id, ts, role, question_hash, question_len, retrieved_ids, plan_json, sql_attempts, policy_decisions, executed_sql, row_count, result_hash, answer, outcome, models, tokens_in, tokens_out, cost_usd, latency_s, human_feedback`; `write_trace(row)`, `list_traces(role=None, outcome=None, limit=50)`, `get_trace(trace_id)` on table `traces` in `paths.TRACES` (DuckDB, opened read-write only here). The question text is stored only when env `GOVERNOR_TRACE_TEXT=1`; masked results never contain raw PII (store the mask, not the value).
2. `record_trace` writes the row; a trace write failure is logged and does not lose the answer.
3. Checkpointer: `SqliteSaver(sqlite3.connect(<state dir>/checkpoints.sqlite, check_same_thread=False))`. Add `paths.STATE` (env `GOVERNOR_STATE_DIR`, default `artifacts/`) and keep `TRACES` and checkpoints under it, so a deployment can mount one volume.
4. CLI `python -m governor.ask.run "QUESTION" --role analyst|finance_admin [--thread ID] [--llm fake:SCRIPT.json|openrouter]` and `python -m governor.ask.run --resume ID --answer "TEXT"` (works in a new process). Prints the answer card; last line JSON `{outcome, trace_id, thread_id}`.
5. Register system `agent` in `governor.eval.systems`: it runs the graph; a clarify interrupt is the behaviour `clarify` (never auto-answered). `python -m governor.eval.run --system agent --split tune --llm fake` must complete on the FakeLLM.
6. Offline tests in `tests/ask/`, exact names: `test_trace_row_complete`, `test_trace_never_stores_raw_pii`, `test_resume_in_new_process` (start the CLI in a subprocess, pause at clarify, resume from a second subprocess), `test_trace_write_failure_keeps_answer`.

Read: `src/governor/ask/{graph,schemas,llm_testing}.py`, `src/governor/eval/{systems,harness}.py`, `src/governor/core/{paths,trace}.py`.

Done when `plan/accept/accept_g6b.py` passes.
