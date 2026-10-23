# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G7 serves governor-ask over HTTP. governor.api.app:app exposes GET /health with no auth, POST /v1/ask, POST /v1/threads/{thread_id}/resume, and GET /v1/traces plus GET /v1/traces/{trace_id}. GOVERNOR_API_TOKENS is role:token pairs. The role comes only from the bearer token, checked with hmac.compare_digest, and a role missing from access.yaml refuses startup. Bodies use extra=forbid. A thread belongs to the role stored in its checkpoint; a trace belongs to the role on its row; any other role gets 404, including ask with a taken thread id. Errors are {error, code} with no traceback and no question text. GOVERNOR_LLM selects openrouter, fake, or fake:SCRIPT.json. The graph is compiled once per process onto SqliteSaver under GOVERNOR_STATE_DIR (/data in the image, artifacts by default). The image builds the green warehouse and catalog, opens the warehouse read-only, and runs uvicorn as non-root. Compose has api on 8000 and a placeholder ui on 8501, with volume governor-data. This is a single-tenant portfolio deployment. as_of remains 2026-10-22.

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

## G7 result (implementer notes)
- `governor.ask.service`: `ask/resume/list_traces/get_trace/settings`, `AskResult`. One compiled graph per process on a SqliteSaver (`paths.CHECKPOINTS`, read when first compiled); `configure(llm, **graph_options)` / `reset()` drop it. Owner = `role` in the checkpointed state (threads) or the trace row; another role gets NotFound (404), same as a missing id. `ask` on an existing thread_id is 409 `thread_exists`; resuming a finished thread is 409 `not_waiting`.
- Status map: answer -> answered; interrupt -> clarify; refused_guard/policy -> refused; unanswerable and **clarify_failed -> unanswerable** (final, so the client must not offer a resume; differs from the agent map); refused_repair/error -> error. `sql` and rows only when answered.
- `governor.api.app`: `create_app(tokens=None, llm="env", **graph_options)`; module `app = create_app()` reads `GOVERNOR_API_TOKENS` and `GOVERNOR_LLM` (openrouter | fake | fake:SCRIPT.json) at import, so a bad role fails at uvicorn startup. Empty tokens = warning + every /v1 call 401. 422 bodies list field names only (pydantic's default echoes the input). `/docs` and `/redoc` disabled; `openapi.json` stays (acceptance reads it).
- New deps: `fastapi` (the API), `uvicorn` (ASGI server in the image), `httpx` (FastAPI TestClient). Plain uvicorn, not `[standard]`, to keep the image small.
- Dockerfile (python:3.12-slim + uv 0.8, `uv sync --frozen --no-dev`), `.dockerignore` (keeps .env, .venv, artifacts out of the context), compose with `api` and a placeholder `ui`, volume `governor-data` on `/data`. Not built here (no Docker run in this step). build_green's 60 s limit applies inside `docker build` too.
- `.gitignore`: `!.env.example` added (`.env.*` would have hidden it).
- **`.env.example` not written**: a permission deny rule covers `.env.*`, so the implementer could not create it. Amir: create it by hand (content in the G7 summary); the acceptance check fails until then.
Tests: `tests/api/test_api.py` (11 incl. parametrised 401 cases and a startup-error test). accept_g7 15/16 (only .env.example); full pytest 266 passed.

## Additions for G7
Resume with Command(resume=text) on the same thread_id. SqliteSaver is sqlite3.connect(paths.CHECKPOINTS, check_same_thread=False); run.sqlite_checkpointer wraps it. Interrupt value is {missing_slot: text}. A second clarify sets outcome clarify_failed and does not interrupt. The llm is not checkpointed. A pause returns outcome clarify and trace_id null; the row is written only in record_trace. Audits: traces.get_trace and list_traces (newest first) are redacted. The in-memory trace, the card, and checkpoints.sqlite still hold the question, clarification answer, and rows, including a granted email. human_feedback is always null. GOVERNOR_STATE_DIR (default artifacts, relative to ROOT) moves STATE, TRACES, and CHECKPOINTS. tests/ask conftest redirects them. CLI --llm openrouter uses llm=None (plan gpt-5-nano; SQL and answer gpt-5-mini). eval.run --llm openrouter passes one model to every node. Agent map: interrupt and clarify_failed -> clarify; refused_guard and refused_policy -> refuse; unanswerable -> unanswerable; refused_repair and refused_error -> answer with error set to that outcome. as_of remains 2026-10-22. CHROMA_DIR now lives under STATE (artifacts/), not .state/.

## G7 result
*API, authentication and deployment skeleton, 23 Oct 2026 19:30.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 1 fix loop(s); branch `factory/G7`.

| check | ok | detail |
|---|---|---|
| API app imports and answers with the fake LLM | yes |  |
| exactly the specified routes | yes | got [('GET', '/health'), ('GET', '/v1/traces'), ('GET', '/v1/traces/{trace_id}'), ('POST', '/v1/ask'), ('POST', '/v1/thr |
| /health needs no token | yes | 200 |
| missing and unknown tokens are 401 | yes | 401/401 |
| a role field in the body is rejected (422) | yes | 422 |
| /v1/ask works with a valid token and returns an AskResult | yes | 200 ['answer', 'clarify_question', 'cost_usd', 'freshness', 'lineage', 'models', 'result_columns', 'result_rows', 'sql', |
| errors are JSON without a traceback | yes | {"error":"trace not found","code":"not_found"} |
| Dockerfile builds the green warehouse and catalog at build time and runs uvicorn as non-root | yes |  |
| docker-compose.yml has api and ui services and a /data volume | yes |  |
| .env.example exists with placeholders only | yes |  |
| docs/deploy.md exists | yes |  |
| no real tokens in code, compose or docs | yes |  |
| tokens are never logged | yes |  |
| pytest tests/api | yes | 11 passed in 4.59s |
| required tests present | yes | 7 found |
| pytest tests/ask | yes | 107 passed in 44.07s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Acceptance does not run docker build. The Dockerfile does build the warehouse before switching to uid 10001, and only /data is writable by that user. Deploy checks are substrings, so the letters USER anywhere in the file would pass. GET /openapi.json is still mounted; docs and redoc are off. It is outside the schema, so the exact-routes check does not see it. app.openapi() does not need that route. If the same token string is listed for two roles, the later pair wins. checkpoints.sqlite on the volume still holds the raw question and result rows.

## Additions for G8
G8 Streamlit talks only to this API. Compose sets GOVERNOR_API_URL=http://api:8000 on ui, which is still a placeholder command on image governor:local. No role picker and no role field: send one bearer token; the API derives the role and returns 422 if the body contains role. Do not put GOVERNOR_API_TOKENS in the browser or in logs. No CORS is configured, so call the API from the Streamlit server. GET /health returns status, as_of, and version. POST /v1/ask takes {question, thread_id?} and returns AskResult. status clarify has a null trace_id; keep that thread and POST /v1/threads/{thread_id}/resume with {answer}. A rerun must not start a new ask. clarify_failed is returned as unanswerable and must not be resumed. Show result_columns and result_rows, not only answer. Another role's thread or trace is 404. 409 is thread_exists or not_waiting, and only for the owning role. Writable state is the api volume governor-data on /data, not the UI container. settings() is in-process only and is not a route.
