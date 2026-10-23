# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G6b is in place on the G6a ask graph. record_trace writes one TRACE_COLUMNS row to paths.TRACES (DuckDB, read-write only in governor.ask.traces, connection closed). The question is sha256 and length unless GOVERNOR_TRACE_TEXT=1. Cells from PII-tagged columns and email-like strings are stored as the access.yaml mask in the answer, executed SQL, SQL attempts, plan JSON, and question text. The in-memory trace dict stays unredacted. A write failure is logged with the trace id and exception type, and the card is still returned. paths.STATE defaults to artifacts and follows GOVERNOR_STATE_DIR; traces.duckdb and checkpoints.sqlite sit under it. The CLI python -m governor.ask.run asks or resumes in a new process via SqliteSaver. The last stdout line is JSON with outcome, trace_id, and thread_id. System agent runs that graph in the harness: an interrupt is behaviour clarify and is not resumed. Relative dates still use as_of (2026-10-22). The golden set stays frozen.

## Open questions
- G2b gate review (claude.ai, 22 Oct): golden set fine; but `fixture/build_green.py` stamps as_of from the wall clock (Sprint 4 behaviour), so a rebuild on another day shifts days_outstanding/overdue answers and breaks the golden as_of check. Spec change for G3 (item 0 + locked check): pin as_of in `fixture/AS_OF` = 2026-10-22T14:11:26+00:00. Needs `factory relock` before `approve G2b`.
- `fct_invoices.days_outstanding` follows the spec literally: 0 only when fully paid. Void invoices (416 not paid) therefore show days outstanding. Should void count as 0 / be excluded? (Amir decides; one-line change in the SQL.)
- `as_of` is the build's wall-clock instant (S4 design: source freshness needs `_loaded_at` within 12 h). Data dates are fixed (seed 42) but `days_outstanding` shifts with each rebuild. Pin as_of if golden answers must be stable across rebuilds.
- `governor.core.config` replaces S4 `triage.config`, which was not imported. Values reconstructed: `ALLOWED_MODELS` from the S4 test, MAX_TOKENS 4096 from the llm docstring; `FAST_MODEL` (`openai/gpt-5-nano`) and `EMBED_MODEL` (`openai/text-embedding-3-small`) are guesses, overridable by env. Check before G4/G5 use them.
- `chromadb` is not a dependency (not in the G1 list). `retrieval.build_index/load_index` need it; add it in the step that uses dense retrieval.
- access.yaml: every model and grant name matches the real warehouse (allowlist = the four marts; `dim_accounts.contact_email` exists and is tagged `email`). No renames needed.
- Capstone brief not yet available; PLAN §1 holds the provisional stance (ask = spine, one triage path = stretch).
- G2b gold numbers are frozen against as_of 2026-10-22T14:11:26+00:00 and the current green build. m05, m06 and j04 depend on days_outstanding / paid amounts; a rebuild that moves as_of changes them and the gold must be rechecked (FROZEN hashes cover the files, not the results).
- G2b metric gold (m01-m03) mirrors metrics.yaml and returns (month_start, value). compare needs equal column counts, so a bare number fails these items. Amir: keep (forces the snapshot month to be stated), or drop month_start from the gold?
- Sol suggested comparing column names/types in the checker; kept name-agnostic on purpose (LLM aliases vary; Spider-style execution accuracy), with equal column counts and permutation matching.

- G3: dbt `source freshness` measures `_loaded_at` against the wall clock (DuckDB now()), and `_loaded_at` is now the pinned as_of, so green sources report warn after 12 h and error after 24 h. build_green.py accepts that (status pass/warn/error, 2 results) instead of failing. Side effect: green sources.json / meta.freshness are not "pass", so `lineage.failing_nodes` on the green build would flag the two sources. Clean fix (outside G3 paths): a project macro overriding `collect_freshness` to use `var('as_of')` as snapshotted_at, or `loaded_at_query` in _sources.yml. Amir decides.
- G3: the prompt gave AS_OF as `2026-10-22T14:11:26+00:00`, but the locked check compares against `str()` of the YAML datetime, so fixture/AS_OF and as_of.txt use `2026-10-22 14:11:26+00:00` (same instant; fromisoformat reads both).
- G3: `--llm` defaults to `fake` so nothing spends money by accident; G10 must pass `--llm openrouter`. The report records `llm`.

## G6b result (implementer notes)
- `governor.ask.traces`: `TRACE_COLUMNS` (re-exported from schemas), `write_trace(row, *, question, secrets, mask, path)`, `list_traces(role, outcome, limit)` (newest first), `get_trace(id)` on table `traces` in `paths.TRACES`; the only read-write opener, every connection closed. List fields are JSON text, decoded on read. Extra column `question_text`, filled only with `GOVERNOR_TRACE_TEXT=1`.
- No raw PII in the store: before writing, result cells of output columns that trace to a PII-tagged column (`governor.eval.pii.output_lineage`, granted or not) and any email-like string are replaced by the access.yaml mask in answer, executed_sql, sql_attempts, plan_json and question_text. So a finance_admin card shows the granted email, the stored trace shows the mask. `state['trace']` itself is unredacted (as in G6a).
- `record_trace` writes the row (`build_graph(..., trace_path=None, store_traces=True)`); any write error is logged (trace id + error type only) and lands in `state['trace_error']`; the card is returned.
- `paths.STATE` = ROOT / `GOVERNOR_STATE_DIR` (default `artifacts`); `TRACES` and new `CHECKPOINTS` (checkpoints.sqlite) live under it. Side effect: `config.CHROMA_DIR` / `CHUNKS_PATH` moved from `.state/` to `artifacts/` (unused so far).
- CLI `python -m governor.ask.run` with SqliteSaver (`langgraph-checkpoint-sqlite`, new dependency; pyproject + uv.lock). `--llm` defaults to `openrouter` (llm=None, per-node models); `fake:SCRIPT.json` takes a list or `{plan, sql, answer}` queues (`llm_testing.load_script`). The llm is not saved with the thread: pass it again on `--resume`. Hidden `--database/--access/--meta/--cards/--as-of` for fixtures. A finished thread exits 1 on `--resume`.
- System `agent` (`governor.ask.agent`, lazy in systems): one thread per item, interrupt = `clarify`; refused_guard/policy = refuse; refused_repair/error = failed answer with the last SQL attempt. With `eval.run --llm openrouter` it gets gpt-5-mini for every node (eval.run's make_llm), not nano for plan; G10 may want llm=None for agent.
- `tests/ask/conftest.py` points STATE/TRACES/CHECKPOINTS at a temp dir for every ask test.
Tests: `tests/ask/test_traces.py` (5). accept_g6b 12/12; full pytest 255 passed.

## G6b result
*Persistence, decision traces, CLI and the agent system, 23 Oct 2026 18:22.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G6b`.

| check | ok | detail |
|---|---|---|
| governor.ask.traces exposes TRACE_COLUMNS, write_trace, list_traces, get_trace | yes |  |
| trace row has every specified column | yes | missing: [] |
| GOVERNOR_STATE_DIR moves state (traces, checkpoints) to one folder | yes | {'state': 'C:\\Users\\amir0\\portfolio\\governor\\zz_state', 'traces': 'C:\\Users\\amir0\\portfolio\\governor\\zz_state\ |
| agent system runs through the harness on the FakeLLM | yes | wrote C:\Users\amir0\AppData\Local\Temp\g6-accept-ith7kh5_\agent-tune.json | {"n": 25, "execution_accuracy": 0.0, "valid |
| agent report covers the 25 tune items | yes | 25 |
| graph prompts exist as files | yes | missing: [] |
| no golden questions or gold SQL in prompts, code or tests | yes |  |
| no wall-clock dates in ask logic (as_of only) | yes |  |
| golden set still frozen | yes | golden set unchanged |
| pytest tests/ask | yes | 107 passed in 44.08s |
| required tests present | yes | 4 found |
| pytest tests/eval | yes | 103 passed in 2.37s |

Review: Decision traces are complete rows in traces.duckdb. Every TRACE_COLUMNS field is written. Question text is stored only when GOVERNOR_TRACE_TEXT=1. Result PII, including a granted email, is stored as the policy mask. A failed write is logged and the answer is kept. Checkpoints and traces share GOVERNOR_STATE_DIR. The CLI resumes a clarify pause from a second process. The agent system returns behaviour clarify on an interrupt and does not resume it. Acceptance passed 12/12.

For Amir: DuckDB trace rows are masked, but SqliteSaver checkpoints and the in-memory trace still contain the question, clarification text, result rows, and the card, so a granted email is in checkpoints.sqlite. G7 should show the role-scoped card and get_trace, not the checkpoint. eval.run --llm openrouter uses one chat model for every node; the CLI openrouter path uses llm=None so plan stays gpt-5-nano. STATE's default moved from .state to artifacts, so CHROMA_DIR and CHUNKS_PATH moved with it. The tune FakeLLM run answers SELECT 1 (execution_accuracy 0) and does not emit clarify.

## Additions for G7
Resume with Command(resume=text) on the same thread_id. SqliteSaver is sqlite3.connect(paths.CHECKPOINTS, check_same_thread=False); run.sqlite_checkpointer wraps it. Interrupt value is {missing_slot: text}. A second clarify sets outcome clarify_failed and does not interrupt. The llm is not checkpointed. A pause returns outcome clarify and trace_id null; the row is written only in record_trace. Audits: traces.get_trace and list_traces (newest first) are redacted. The in-memory trace, the card, and checkpoints.sqlite still hold the question, clarification answer, and rows, including a granted email. human_feedback is always null. GOVERNOR_STATE_DIR (default artifacts, relative to ROOT) moves STATE, TRACES, and CHECKPOINTS. tests/ask conftest redirects them. CLI --llm openrouter uses llm=None (plan gpt-5-nano; SQL and answer gpt-5-mini). eval.run --llm openrouter passes one model to every node. Agent map: interrupt and clarify_failed -> clarify; refused_guard and refused_policy -> refuse; unanswerable -> unanswerable; refused_repair and refused_error -> answer with error set to that outcome. as_of remains 2026-10-22. CHROMA_DIR now lives under STATE (artifacts/), not .state/.
