# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
The build graph runs from the profile and the design gate through silver to gold. Gold models are the catalogue template with each relation replaced by a ref, under models/marts/<domain>/. Declined KPIs go to governor/gaps.md and are not models. check_project applies blueprint L1-L9; a high finding ends approve as blueprint_failed without building marts. A failing staging model escalates and is not repaired. governor/build.json records models, tests, KPI row counts, gaps, findings and cost. On the sample the eight buildable KPIs build, and gmv, net revenue, AOV, on-time delivery, average review score and repeat purchase rate match a computation from the sample CSVs.

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

## D4 result
*Silver writer, dbt build in the dev schema, repair and escalation, 04 Nov 2026 21:54.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D4`.

| check | ok | detail |
|---|---|---|
| sample design and silver fixtures exist | yes | tests/fixtures/build/ |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| build init lists the 9 raw tables | yes |  |
| run pauses at the design gate | yes | {"thread_id": "7c556dce-bf99-4cbc-b038-a14c66ada5ff", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| approve builds silver | yes | {"thread_id": "7c556dce-bf99-4cbc-b038-a14c66ada5ff", "status": "silver_built", "report": "C:\\Users\\amir0\\AppData\\Lo |
| tests ran and passed | yes | 11 |
| the scripted bad draft was repaired | yes | 1 |
| every silver model exists in dev_governor | yes | [] |
| nothing written outside dev_governor | yes | [] |
| silver yml tags PII columns | yes |  |
| silver yml has unique and not_null key tests | yes |  |
| composite keys have singular tests | yes |  |
| a model that cannot be repaired ends escalated | yes | {"thread_id": "9fd8b17c-fc24-4565-8de1-9e03ca00db18", "status": "escalated", "report": "C:\\Users\\amir0\\AppData\\Local |
| pytest tests/build | yes | 88 passed, 10 skipped in 14.46s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The live run is the evidence: tests_passed 11 equals 4 single-column keys times unique and not_null, plus 3 composite singular tests, and int_order_lines exists only after the repair replaced i.price with i.item_price. The yml checks in accept_d4.py are substring searches. Section 8 still says status built; the step and the script use silver_built until D5. When several models run out of repairs together, only the first is named. A dbt failure tied to no model escalates with model null. Reused targets keep stale SQL files. approved_on is still date.today.

## D5 notes (implementer)
- `governor.build.gold`: `write_gold` (file = `catalogue.render` with relations as `{{ ref() }}`, written as LF bytes; `_<domain>.yml` with definition, meta kpi_id/owner/source_tier/source_ref/template_sha256/rendered_sha256, `not_null` on month/cohort_month), `check_project(target, catalogue, policy, blueprint=)` -> `BlueprintFinding{rule, severity, target, problem}` (severity from blueprint.md, its exceptions honoured), `write_gaps`, `dbt_build_gold`, `kpi_rows`, `summarise` (`governor/build.json`). Hashes are SHA-256 of LF-normalised text.
- L7 checks the final SELECT's output columns, followed through renaming CTE columns, against policy PII plus silver columns tagged pii; PII used inside CTEs and aggregated away is allowed (repeat_purchase_rate reads customer_unique_id). `SELECT *` in gold is an L7 finding. L9 is a regex over gold SQL without comments and string literals.
- Graph: `silver_done -> write_gold (models, gaps.md, check) -> dbt_build_gold -> summarise -> END`; a high finding skips dbt (`blueprint_failed`, build.json still written). A failing gold model escalates (no model repair). `approve` returns status, `kpis_built` (ids), `gaps` (ids), `tests_passed` (silver + gold), `repairs` (SQL repairs), `models`, `blueprint`, plus `escalated` when it applies. `build_graph(row_counter=)` for offline tests.
- Design-gate guard: a failing (or check_sql-refused) staging model escalates at once with `{model, folder, error, fix}`; `repair_silver` only touches intermediate models. `silver.prune_stale` runs at the start of `write_silver` (and `write_gold`): removes .sql/.yml under staging, intermediate and marts, and `tests/*__primary_key.sql`, that the design does not produce; empty mart folders go too. Stale tables in `dev_governor` are not dropped.
- Mart folder = `mart_folder(domain)` (lower case, `[a-z0-9_]`).

## Additions for D5
On silver_built, continue to write_gold; leave escalated at END. Section 8's approve status built is the post-gold name; D4 returns silver_built plus models, tests_passed, and repairs. State.repairs is the design-loop count. SQL repairs are state.sql_repairs and silver.repairs, with per-model counts in silver.attempts (2 write, then 1 plan). calls uses operator.add; return only new usage dicts. Files: models/staging/_staging.yml, models/intermediate/_intermediate.yml, models/<folder>/<name>.sql, and tests/<model>__primary_key.sql for a composite key. PII is columns[].config.meta.pii (dbt 1.12). Single-column keys use data_tests [unique, not_null]. Composite keys do not get per-column unique tests; the singular test returns rows for a duplicate or a null key part. Model config.meta.primary_key lists the key. Silver models stay views; marts are tables via dbt_project.yml. The profile already targets dev_governor as governor_build. That schema is shared and not dropped, and a reused target keeps stale stg_/int_ files. The column check compares names only. design.json is the proposal at <target>/governor/design.json. The sample declines conversion_rate and gross_margin. Do not import governor.ask. Do not write knowledge/.

## D5 result
*Gold from catalogue templates, blueprint checks, gap report, 04 Nov 2026 23:03.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D5`.

| check | ok | detail |
|---|---|---|
| sample design and silver fixtures exist | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| build init lists the 9 raw tables | yes |  |
| run pauses at the design gate | yes | {"thread_id": "fbe9ed5e-9b10-4ba6-bb95-7aad45d73a6e", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| approve builds silver and gold | yes | {"thread_id": "fbe9ed5e-9b10-4ba6-bb95-7aad45d73a6e", "status": "built", "report": "C:\\Users\\amir0\\AppData\\Local\\Te |
| all eight buildable KPIs built | yes | ['gmv', 'net_revenue', 'aov', 'on_time_delivery_rate', 'avg_review_score', 'repeat_purchase_rate', 'cohort_retention', ' |
| gaps list conversion_rate and gross_margin | yes |  |
| target has governor/gaps.md | yes |  |
| target has governor/build.json | yes |  |
| gold yml carries owner, source tier and template hash | yes |  |
| gmv equals the independent computation | yes | got {'2026-01': 455.0} want {'2026-01': 455.0} |
| net_revenue equals the independent computation | yes | got {'2026-01': 325.5} want {'2026-01': 325.5} |
| aov equals the independent computation | yes | got {'2026-01': 100.25} want {'2026-01': 100.25} |
| on_time_delivery_rate equals the independent computation | yes | got {'2026-01': 0.6666666666666666} want {'2026-01': 0.6666666666666666} |
| avg_review_score equals the independent computation | yes | got {'2026-01': 3.3333333333333335} want {'2026-01': 3.3333333333333335} |
| repeat_purchase_rate equals the independent computation | yes | got [['0.3333333333333333']] want 0.3333333333333333 |
| blueprint check is clean on the built project | yes | [] |
| blueprint check catches a cast in gold (L9) and a changed template (L8) | yes | [{"rule": "L8", "severity": "high", "target": "kpi_gmv", "problem": "rendered_sha256 does not match the model file"}, {" |
| pytest tests/build | yes | 122 passed, 11 skipped in 22.12s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The acceptance line "blueprint check is clean" fails only when a high finding is present, so a lone L9 would still pass that line. The unit test requires an empty finding list, and the generated project is empty. cohort_retention and historical_clv are built with rows; the step asked for an independent value check only for the five order-level KPIs and the repeat purchase rate.

## Additions for the next plan
D6 opens the PR on the target after approve. approve already runs silver and gold and returns status built, escalated or blueprint_failed, plus kpis_built (ids), gaps (declined ids), tests_passed, repairs, blueprint findings, and build pointing at <target>/governor/build.json. That file has models, silver/gold/total test counts, KPI row counts, full gap objects, findings and cost. Gold files are models/marts/<domain>/kpi_<id>.sql (tables via the marts materialization) and _<domain>.yml (owner, source_tier, source_ref, template_sha256, rendered_sha256, not_null on month or cohort_month). L8 re-renders from governor/design.json; do not add a model that writes gold SQL. High rules stop the build. L5 is medium and L9 is low, so they are recorded and do not stop it. A failing staging model escalates with zero repairs; only intermediate SQL is repaired. On the sample the gaps are conversion_rate and gross_margin. cohort_retention and historical_clv are built and non-empty; their values were not checked against an independent computation.
