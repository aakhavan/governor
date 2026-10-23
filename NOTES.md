# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G8 is the Streamlit thin client on the G7 API. apps/streamlit/client.py (httpx) is the only UI import of governor.api, used when GOVERNOR_API_URL=asgi. Pages contain no SQL, DuckDB, policy checks, or governor.ask imports and no role picker: the sidebar stores a bearer token in session state. Ask shows answer text, the result table, SQL, models, lineage, freshness, and cost. A pending clarification keeps thread_id, so a rerun does not ask again, and the reply calls resume. Refusals display as refusals; unanswerable and error do not resume. Trace explorer filters the caller's traces and shows plan, SQL attempts with validator codes, and policy decisions. Developer shows /health, model ids from those traces, and knowledge/access.yaml as read-only text. Compose runs ui on port 8501 with GOVERNOR_API_URL=http://api:8000, no secrets, after api is healthy. as_of remains 2026-10-22.

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

## G8 result (implementer notes)
- `apps/streamlit/`: `client.py` (`ApiClient` over httpx; `GOVERNOR_API_URL=asgi` runs the API in-process via `httpx.ASGITransport` + `asyncio.run`, looking up `governor.api.app.app` per request), `ui_common.py` (sidebar token box: password field copied into `session_state["api_token"]` so it survives page switches; login hint), `app.py` (landing: what it is, `/health` status/as_of/version), pages Ask, Trace explorer, Developer.
- Ask: API called only on form submit, so reruns never re-ask. `thread_id` + `clarify_question` in session state while a clarify is pending; reply box calls `resume`; 404/409 on resume clears the pending thread and shows the error. Answer card: text, `result_columns`/`result_rows` table, SQL expander, models, upstream sources, freshness expander, cost badge; refusals as an error box; unanswerable/error as warnings (no resume offered).
- Trace explorer: outcome filter (fixed list of graph outcomes), list table, detail (plan JSON, SQL attempts with validator codes, executed SQL, policy decisions).
- Developer: API URL, `/health` JSON. No settings route exists (and `src/governor/api` is outside G8 paths), so "models" = LLM model ids from the caller's recent traces. access.yaml read from the repo copy and shown as text.
- Compose `ui`: `streamlit run apps/streamlit/app.py` on 8501, own healthcheck (`/_stcore/health`; the image's HEALTHCHECK targets 8000), waits for api healthy, **no `env_file`** (the UI needs no secrets; GOVERNOR_API_TOKENS stays out of the UI container). Not built or run here.
- New dep: `streamlit` (UI; 1.66.1). Added by editing pyproject; `uv run` re-locked.
- Open: `docs/deploy.md` still calls the ui a placeholder (outside G8 paths). Streamlit runs as uid 10001 with HOME=/nonexistent in the image; untested in Docker.
Tests: `tests/ui/test_pages.py` (5, AppTest, asgi, scripted FakeLLM); accept_g8 11/11; full pytest 271 passed.

## G8 result
*Streamlit as a thin client over the API, 23 Oct 2026 19:47.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G8`.

| check | ok | detail |
|---|---|---|
| app and the three pages exist | yes | missing: [] |
| UI has no DB, SQL, policy or governor.ask imports | yes |  |
| only client.py touches governor.api (asgi mode) | yes |  |
| no role picker in the UI (role comes from the token) | yes |  |
| no golden questions in the UI or its tests | yes |  |
| apps/streamlit/client.py importable | yes |  |
| ApiClient exposes ask/resume/list_traces/get_trace/health | yes | missing: [] |
| compose ui service points at the api service | yes |  |
| pytest tests/ui | yes | 5 passed in 8.90s |
| required tests present | yes | 5 found |
| pytest tests/api | yes | 11 passed in 4.05s |

Review: Pages talk only to ApiClient. governor.api is imported only for GOVERNOR_API_URL=asgi. No role picker: the token is sent as a bearer header. Ask stores thread_id while a clarification is pending, so a rerun does not ask again, and the reply box calls resume. Answered results render result_rows as a dataframe plus SQL, models, lineage, freshness, and cost. Refusals are shown as refusals. Trace outcomes match the graph literal. AppTests run these paths on the real API. Compose points ui at http://api:8000 and does not pass tokens.

For Amir: Acceptance does not start the ui container. Streamlit 1.66 with --server.headless and --browser.gatherUsageStats=false does not create ~/.streamlit on boot, so HOME=/nonexistent should not stop startup; a later streamlit_write would still need a writable home. docs/deploy.md still calls ui a placeholder and is outside G8 paths. The role-picker grep is case-sensitive and would miss a widget labeled Role; this UI has no role widget. Refusal rendering is implemented and untested.

## Additions for G9
G9 is MCP on stdio, separate from the Streamlit client. Do not import apps/streamlit. Shared read-only logic stays in governor.ask.service; the UI already uses that service only through HTTP. Role is never a tool or body field: HTTP derives it from the bearer token and returns 422 if the body contains role. MCP must take the role from GOVERNOR_MCP_ROLE (default analyst, must exist in access.yaml) and must not let the client raise it. settings() is in-process only and is not a route. AskResult clarify carries thread_id and a null trace_id; resume is POST /v1/threads/{id}/resume with {answer}. clarify_failed is returned as unanswerable and must not be resumed. sql and rows are present only when status is answered. Traces are scoped to the role. No write path. Tool text must not restate access.yaml. as_of remains 2026-10-22. Do not read evaluation/golden.
