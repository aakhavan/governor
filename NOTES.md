# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
E2 is in place: python -m governor.ask.mcp_certified (server governor-certified) serves list_certified_kpis, describe_kpi, query_kpi and gap_report read-only under GOVERNOR_MCP_ROLE (analyst or finance_admin). No model call; no tool takes SQL or a role. query_kpi calls certified.answer_reply, which builds the SQL, validates it and runs it as that role's reader. describe_kpi returns unknown when the id is neither certified nor in governor_gaps, including a catalogue-only id such as gross_margin; query_kpi returns not_available for that same id because answer_reply still consults the catalogue. Failures are an object with outcome error and one line of text, connection string scrubbed. answer_reply takes an optional registry so answer does not read the registry twice. E1 remains: /governor ask posts CertifiedAnswer.text from GovernorSlack._default_asker, role only from GOVERNOR_SLACK_ASK_ROLE, refusals and errors ephemeral, channel shows text only. The existing mcp_server is unchanged.

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

## E2 result (implementer notes)
accept_e2: 17/17 checks pass (tests/mcp 15 passed; tests/ask 158 passed, 2 skipped); tests/integrations 36 passed. Notes for review: `answer_reply` has an extra keyword-only `registry=` so `answer` keeps one registry read. `query_kpi` types `period_kind` and `pick` as plain strings so a bad value comes back as `{"outcome": "error"}` from our CertifiedReply validation instead of an SDK ToolError; the allowed values are in the tool description. `describe_kpi` reads `template_sha256` with a separate optional query (read_registry's column list is unchanged so the existing fakes keep working); a catalogue KPI with no gap row is `not_available`. describe/list use the private `certified._gap_text` and `_catalogue_ids`.

## Additions for E2
E2 splits certified.answer and adds answer_reply. Slack must keep calling certified.answer(question, role, certified.make_llm(config.ask_llm)) with no adapter, from GovernorSlack._default_asker only. That import has to stay inside the function: a top-level governor.ask import fails the E1 check. The omitted adapter is the ask login (GOVERNOR_PG_DSN), same as the API. make_llm("openrouter") returns None, and answer() then builds the chat model. READER_ROLES is the dict in governor.core.serving (keys analyst and finance_admin). SlackConfig rejects any other ask role at construction, including the Postgres role names. Channel outcomes are answer, not_available, and unanswerable. refused and any exception are ephemeral and must not include the question. The channel shows text only; sql, value, and citation stay off the message and out of the log. Ask logs are outcome, kpi id, and Slack user id. GOVERNOR_SLACK_ASKERS unset means the runners, and unset runners means the approvers. * means every user.

## E2 result
*Certified KPIs over MCP (second read-only server), 11 Nov 2026 13:14.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 1 fix loop(s); branch `factory/E2`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.ask never imports build or integrations | yes |  |
| tests/ask/test_certified.py unchanged against main | yes | the file differs from main |
| src/governor/ask/mcp_server.py unchanged against main | yes | the file differs from main |
| tests/mcp/test_mcp_server.py unchanged against main | yes | the file differs from main |
| mcp_certified imports without a database | yes |  |
| certified.answer_reply exists | yes |  |
| build_server takes an adapter | yes |  |
| docs/mcp.md mentions governor.ask.mcp_certified | yes |  |
| docs/mcp.md mentions list_certified_kpis | yes |  |
| docs/mcp.md mentions describe_kpi | yes |  |
| docs/mcp.md mentions query_kpi | yes |  |
| docs/mcp.md mentions gap_report | yes |  |
| pytest tests/mcp | yes | 15 passed in 30.66s |
| required tests present | yes | 9 found |
| pytest tests/ask | yes | 158 passed, 2 skipped in 50.50s |
| required tests present | yes | 1 found |

Review: E2 matches section 23. certified.answer calls answer_reply after the model choice, and tests/ask/test_certified.py is unchanged and green. query_kpi uses that path: build_sql, the validator, and the role's reader. The four tools take no role and no SQL. Arguments that fail validation return outcome error and run no SQL. Errors are one line with the connection string scrubbed. describe_kpi returns unknown for an id that is neither certified nor a registry gap, including catalogue-only gross_margin. mcp_server.py is unchanged. Acceptance passed.

For Amir: Acceptance details that say the file differs from main, for test_certified.py, mcp_server.py and test_mcp_server.py, are that check's failure text. git diff --quiet main returned 0, so those files match main. The E2 implementer note in NOTES.md still says a catalogue KPI with no gap is not_available and that describe uses _catalogue_ids. describe_kpi returns unknown and does not call _catalogue_ids. query_kpi still returns not_available for that id, because it calls answer_reply.

## Additions for E3
E2 adds python -m governor.ask.mcp_certified, server name governor-certified. GOVERNOR_MCP_ROLE defaults to analyst and must be a key of certified.READER_ROLES (analyst, finance_admin), not the Postgres role name. build_server(role, adapter=None) raises ValueError otherwise; main exits 2. Tools: list_certified_kpis, describe_kpi, query_kpi, gap_report. None takes a role or SQL. query_kpi builds a CertifiedReply with category answer and calls answer_reply. A registry gap is not_available. A catalogue id with no gap row is also not_available on query_kpi, because answer_reply still uses _catalogue_ids. describe_kpi stops after a certified row and a governor_gaps row, then returns outcome unknown plus kpi_id. It does not call _catalogue_ids. template_sha256 is a separate optional query, omitted when the column is absent; read_registry's SELECT list is unchanged. answer_reply(reply, role, adapter=None, *, access_path, kpis_path, registry=None) is the path after the model choice; answer passes the registry it already read so it does not read twice. Slack must keep calling certified.answer from GovernorSlack._default_asker only, import inside the function. mcp_server.py, tests/ask/test_certified.py and tests/mcp/test_mcp_server.py are unchanged. Failures are outcome error with one line of text; safe_text redacts URLs and password, user, host, hostaddr, dbname, port, dsn, sslmode. E3 (perturbed test bed) does not use this server.
