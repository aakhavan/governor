# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D9 is in src/governor/integrations/slack: a Socket Mode app with /governor, an approver allowlist, a design-gate card and a build notifier. slack-bolt 1.30.0. Tokens and settings come from the environment. Message state is GOVERNOR_STATE_DIR/slack_messages.json. Builds report to Slack when GOVERNOR_BUILD_NOTIFIERS includes governor.integrations.slack.notifier:notify. governor.build does not import Slack. tests/integrations has the seven offline Slack tests. Certify stays a terminal command.

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

## D10 result
*Column descriptions from lineage, 06 Nov 2026 15:12.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D10`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| docs.py exists | yes | missing |
| describe prompt exists | yes | missing |
| pytest tests/build | yes | 146 passed, 12 skipped in 40.17s |
| required tests present | yes | 5 found |

Review: Column descriptions are deterministic first: gold from the catalogue definition and role, staging from lineage and profile bands (no data values), intermediate by inheriting the same-named ref (approved text kept). One write-model call per model fills only the columns still empty; the prompt has lineage, counts and assumptions, and replies trim at 200 characters. Texts land in the staging, intermediate and marts yml; build.json and pr.md record docs_coverage. SQL is unchanged (catalogue.render and staging_sql). The five tests, including a graph run, check this.

For Amir: The sample design never calls the write model for descriptions; rule 4 is tested by an added int_customer_orders model. The live sample-build mismatch (full Olist months versus the 2026-01 sample) is the data already on the dev test bed, and acceptance skips it by pinning the port. Marts yml now lists every KPI output column, not only the grain.

## Additions for D9
docs.describe runs in graph write_silver before any SQL is written and stores state docs (model to column to description). silver.write_silver(docs=) and gold.write_gold(docs=) put those strings on column descriptions in _staging.yml, _intermediate.yml and models/marts/<domain>/_<domain>.yml. not_null stays on the grain only. governor/build.json docs_coverage is {columns, described, share}; render_pr adds one Column descriptions line pointing at the yml. Fake script key describe maps each model to a list of JSON objects of column to description, on the write role; a non-JSON reply leaves those columns empty. On the sample design rules 1-3 fill every column, so no describe call is made. Profile min and max must not be copied into any new payload. Do not change staging_sql or gold_sql.

## D9 result
*Slack app, 06 Nov 2026 16:47.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 2 fix loop(s); branch `factory/D9`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| slack-bolt is a dependency | yes |  |
| src/governor/integrations/slack/app.py exists | yes | missing |
| src/governor/integrations/slack/blocks.py exists | yes | missing |
| src/governor/integrations/slack/notifier.py exists | yes | missing |
| docs/slack.md exists | yes | missing |
| governor.build never imports Slack | yes |  |
| Slack modules import without tokens | yes |  |
| pytest tests/integrations | yes | 7 passed in 5.33s |
| required tests present | yes | 7 found |
| pytest tests/build | yes | 146 passed, 12 skipped in 40.96s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Slack-started publish posts the PR URL from publish()'s return. A terminal publish only says a PR was opened, because the published event has pr: true and no pr_url. An approver missing from GOVERNOR_SLACK_NAMES is stored as their Slack user id. An escalation with no model name can omit the error, because silver_done emits before that checkpoint is written. design.md is uploaded whole, so mapping SQL is in the file; the card omits mappings. Tests use a fake Web API client and do not open Socket Mode.

## Additions for the next plan
D10 fills column descriptions. Keep them free of data values: the Slack card prints decline reasons and validation problems (after safe_text), and the notifier uploads governor/design.md, so new text in the proposal, findings or that report becomes a Slack payload. Do not import governor.integrations from governor.build. Progress events stay counts, names, codes, status and cost. The checklist keys are the existing event kinds. docs_coverage is not shown in Slack. Descriptions belong in the yml files and build.json, as section 16 says.
