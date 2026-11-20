# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
Batch 4 V2 is done: ask registry and labelled topology, all eleven nodes traced with §35 summaries, checkpoints.invoke owns run_started/resumed/paused/finished, and fold marks never-started ask nodes skipped after a finished run. Marker and lifecycle tests pass offline. V3 (console read API and demo fixtures) is next.

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

## V1 result
*Run-event contract, reducer and build-graph tracing, 20 Nov 2026 18:38.*

Implementer `cursor-grok`; reviewers `cursor-composer`: pass; 0 fix loop(s); branch `factory/V1`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| runtrace package | yes | missing |
| fold cases: at least 8 | yes | 8 cases |
| fold cases cover section 34 | yes | ok |
| build graph wraps nodes | yes | no traced( in build/graph.py |
| build does not import ask/integrations | yes | bad import |
| topology has every build node | yes | 14 nodes |
| every conditional edge labelled | yes | [] |
| pytest tests/core | yes | 131 passed, 12 skipped in 10.94s |
| required tests present | yes | 7 found |
| pytest tests/build | yes | 207 passed, 12 skipped in 91.56s (0:01:31) |
| required tests present | yes | 5 found |
| pytest tests | yes | 767 passed, 33 skipped in 209.26s (0:03:29) |

Review: V1 matches batch4 §34–35: additive JSONL tracing, fold reducer with 8 shared cases, build registry/topology, and traced build nodes plus entry-point lifecycle events. Tracing re-raises exceptions, treats GraphInterrupt as pause, respects GOVERNOR_RUNTRACE=0, and marker tests show no warehouse/approver leakage. Acceptance tests and review_focus items are covered.

For Amir: Accept script prints detail strings like "missing" and "no traced(" even on success — they are failure messages, not status.

## V2 result
*Ask-graph tracing, 20 Nov 2026 19:06.*

Implementer `cursor-grok`; reviewers `cursor-composer`: pass; 0 fix loop(s); branch `factory/V2`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| src/governor/ask/graph.py does not import build/integrations | yes | bad import |
| src/governor/ask/checkpoints.py does not import build/integrations | yes | bad import |
| ask graph wraps nodes | yes | no traced( |
| topology has every ask node | yes | 11 nodes |
| every conditional edge labelled | yes | [] |
| pytest tests/ask | yes | 164 passed, 2 skipped in 49.52s |
| required tests present | yes | 6 found |
| pytest tests | yes | 773 passed, 33 skipped in 217.39s (0:03:37) |
| pytest tests/build | yes | 207 passed, 12 skipped in 93.43s (0:01:33) |

Review: V2 wires ask tracing end-to-end: ASK_NODES and labelled edges, every node wrapped with traced summaries, checkpoints.invoke emits run lifecycle events, fold skips unstarted nodes after run_finished. Offline tests cover repair, guard block, clarify pause, and the marker privacy check. Acceptance and full pytest are green; API/trace store behaviour unchanged.

For Amir: Optional follow-up: eval AgentSystem uses graph.invoke without run lifecycle wrappers; only affects golden eval threads, not the ask API.

## Additions for V3
V3 can use topology('ask') and fold() on GOVERNOR_STATE_DIR/runs/ask/<thread_id>.jsonl. run_status mapping is in checkpoints.run_status. Guard-blocked runs finish with status blocked and many skipped nodes. Clarify leaves the log without run_finished until resume. Summaries never carry question/SQL/values; only counts and codes. Eval agent still bypasses checkpoints.invoke — console live runs come from API/CLI unless that is changed later.

## Additions for the next plan
Multi-tenant Slack: GovernorSlack takes tenant_threads= (callable returning tenant -> thread ids) for tests; config.tenants non-empty switches every path. Notifier gets tenant_of= and records rec['tenant'] from the run_started project name, then from the tenants' checkpoints; every Notifier.reply appends a 'tenant <name>' context block via blocks.with_tenant, so any new reply type gets it for free, but a chat_update that rebuilds blocks must re-apply with_tenant (see _on_published). dbt_project_name(name) in app.py maps '-' to '_' and prefixes a leading digit with 't_'; the build CLI --tenant still hands init_target the raw tenant name, so a hyphenated tenant created from the CLI gets an invalid dbt project name unless Slack created the target first (init_target never overwrites). ask remains single-tenant and is refused before parse_command. The reviewer's pytest invocation was blocked by the permission policy; acceptance reported tests/integrations 46 passed and the full suite 549 passed, 21 skipped.
