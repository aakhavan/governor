# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D14 is in place. design.validate raises KEY_NOT_UNIQUE when a staging model's primary key does not contain a candidate key of its profiled source table. Key columns map through a null expr, a bare column, or a cast of one; any other expression is flagged as computed. The finding names the candidate keys, or says the table has none, with column names and the row count only. Intermediate models are not checked. The existing design repair loop sends the finding back before the gate. propose.md tells the planner the rule. The offline sample profile now includes pair candidate keys the way the profiler does, and the sample design's staging keys pass that check.

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

## D14 result
*Keys checked against the profile, 07 Nov 2026 14:26.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D14`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| KEY_NOT_UNIQUE is a validation code | yes | missing |
| propose prompt mentions candidate keys | yes | missing |
| pytest tests/build | yes | 152 passed, 12 skipped in 39.34s |
| required tests present | yes | 5 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: STATUS.md shows a later lock_mismatch because plan files changed after the lock. That is outside this review; the acceptance result given for D14 passed. If a primary_key names a column the model does not declare, _key_findings returns nothing and MISSING_KEY blocks the gate, so a computed column earlier in that same key is not also reported until a later repair.

## Additions for D9b
KEY_NOT_UNIQUE is raised by design.validate for a staging model whose source_table is in the profile. It is not a new graph branch: any finding, including this one, goes through the existing propose repair loop (at most two design repairs) before the gate. A staging primary_key is valid when some candidate key of the source table is a subset of the raw columns its key columns read. A null expr means the raw column of the same name; a bare column or a cast of one maps to that column; any other expr is computed and is KEY_NOT_UNIQUE on subject <model>.<column>. A table with no candidate key gets one finding: leave it unstaged unless a KPI needs it, or dedupe it in an intermediate model. Intermediate models are not checked. Findings contain column names and the table row count, never data values. propose.md already states the rule. tests/build/conftest.py sample_profile now records unique null-free column pairs when a table has no single-column key, matching profile.py. sample_design.json keys stg_reviews on [review_id, order_id], which that sample profile accepts.
