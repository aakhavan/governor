# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
Mapping pairs are the model-facing shape; design.json, the report and downstream code keep the mapping dict. Build stages, publish and certify append events of counts, names, codes, status, cost and seconds, and a failing notifier does not stop a run. publish commits models, tests and governor/ on governor/build-<id8> as author governor, leaves main at the scaffold when it creates the repo, writes governor/pr.md, and pushes only when origin exists. certify refuses until that commit is on a clean main, then runs dbt build --target prod as governor_deploy into analytics, writes analytics.governor_certified and analytics.governor_gaps as admin, and applies serving views for the shop policy. The deploy password is an env_var in profiles.yml. On the sample, eight KPIs certify and conversion_rate and gross_margin land in the gaps table.

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

## D6 notes (implementer)
- Mapping pairs: `models.ProposalReply`/`KpiDecisionReply` is the schema the model sees (`mapping_pairs`); `design.propose` calls `.to_proposal()` before validation. A reply that still sends a `mapping` dict is accepted as pairs. The previous proposal is shown back as pairs (`proposal_as_reply`).
- Events: `events.emit` keeps scalars and flat lists only (strings cut at 300 chars). `design_gate` is emitted in the report node, because the gate node runs again on resume. Tests set `GOVERNOR_STATE_DIR` to tmp (conftest autouse).
- Publish records the published commit in `.git/governor_published.json` (outside the tree, so certify sees a clean tree). The tree is left on the build branch. It pushes `main` too when the remote has none. `build.json` gains `approved_by` for pr.md.
- Certify: `value_columns` = numeric columns of the deployed table minus the grain column and `months_since_first`. Registry and gaps tables are dropped and recreated as the admin in one transaction. Serving salt: `GOVERNOR_PII_SALT`, else the stored `private.pii_salt`, else a new random one (never printed). `workspace.deploy_env()` supplies the test-bed default deploy password when the env is unset.
- Acceptance D6: 30/30; pytest tests/build 139 passed, 12 skipped.

## Additions for the next plan
D6 opens the PR on the target after approve. approve already runs silver and gold and returns status built, escalated or blueprint_failed, plus kpis_built (ids), gaps (declined ids), tests_passed, repairs, blueprint findings, and build pointing at <target>/governor/build.json. That file has models, silver/gold/total test counts, KPI row counts, full gap objects, findings and cost. Gold files are models/marts/<domain>/kpi_<id>.sql (tables via the marts materialization) and _<domain>.yml (owner, source_tier, source_ref, template_sha256, rendered_sha256, not_null on month or cohort_month). L8 re-renders from governor/design.json; do not add a model that writes gold SQL. High rules stop the build. L5 is medium and L9 is low, so they are recorded and do not stop it. A failing staging model escalates with zero repairs; only intermediate SQL is repaired. On the sample the gaps are conversion_rate and gross_margin. cohort_retention and historical_clv are built and non-empty; their values were not checked against an independent computation.

## D6 result
*Mapping pairs, events, pull request and certification, 05 Nov 2026 12:41.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D6`.

| check | ok | detail |
|---|---|---|
| build models import | yes |  |
| src/governor/build/events.py exists | yes | missing |
| src/governor/build/publish.py exists | yes | missing |
| src/governor/build/certify.py exists | yes | missing |
| roles.sql defines governor_deploy | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| sample design and silver fixtures exist | yes |  |
| build init lists the 9 raw tables | yes |  |
| sample run pauses at the design gate | yes | {"thread_id": "1f027efe-c1ba-48f9-ba6c-a9e39f03eacc", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| sample build completes | yes | {"thread_id": "1f027efe-c1ba-48f9-ba6c-a9e39f03eacc", "status": "built", "report": "C:\\Users\\amir0\\AppData\\Local\\Te |
| events log has the build stages | yes | ['run_started', 'profiled', 'proposed', 'validated', 'design_gate', 'approved', 'repair', 'silver_built', 'gold_built',  |
| events carry no data values | yes | [] |
| publish creates a governor/build-* branch | yes | {"status": "published", "branch": "governor/build-1f027efe", "commit": "318fc9ec7a274365fac180cf68ec25ab435efb39", "pr_u |
| commit by governor with a summary message | yes | governor|governor: build 1f027efe (8 KPIs, 2 gaps) |
| branch contains models, tests and governor files | yes |  |
| main holds only the scaffold | yes |  |
| pr.md has KPIs, gaps, tests and a reviewer checklist | yes |  |
| publish pushes the branch when origin exists | yes | {"status": "published", "branch": "governor/build-1f027efe", "commit": "d8385c7982b45066c82590f2a6aedac6cac0fdec", "pr_u |
| certify refuses before the merge | yes | {"status": "not_merged", "reason": "the working tree is on 'governor/build-1f027efe', not main", "commit": "318fc9ec7a27 |
| reviewer merges the pull request branch locally | yes |  create mode 100644 tests/int_order_lines__primary_key.sql |  create mode 100644 tests/stg_order_items__primary_key.sql  |
| certify deploys after the merge | yes | {"status": "certified", "kpis": ["gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purch |
| registry lists the 8 certified KPIs, certified by amir | yes | ['aov', 'avg_review_score', 'cohort_retention', 'gmv', 'historical_clv', 'net_revenue', 'on_time_delivery_rate', 'repeat |
| gaps table lists the declined KPIs | yes | [['conversion_rate'], ['gross_margin']] |
| serving views exist for the gold tables | yes | [['8']] |
| governor_deploy owns nothing outside analytics | yes | [] |
| pytest tests/build | yes | 139 passed, 12 skipped in 33.88s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: A second certify fails: DROP TABLE on the registry has no CASCADE, and the serving views depend on those tables. On a clone that already has commits, the prod output appended to profiles.yml is not in the branch commit, so the clean-tree check blocks certify until someone commits that file. The published sha lives only in .git/governor_published.json, so a squash merge or another clone cannot certify. The acceptance data-value scan looks only for cust-0001 and ord-0001.

## Additions for D7
D7 reads serve_<role>.governor_certified and serve_<role>.governor_gaps (serving applied with source analytics; schemas serve_analyst and serve_finance_admin). Certified columns: kpi_id, model, label, definition, grain, value_columns (text[] of numeric columns except the grain column month or cohort_month, and except months_since_first), owner, source_tier, source_ref, template_sha256, rendered_sha256, certified_by, certified_at, git_commit. Gap columns: kpi_id, missing (text[]), typical_sources (text[]), next_step. Sample: eight certified KPIs (gmv, net_revenue, aov, on_time_delivery_rate, avg_review_score, repeat_purchase_rate, cohort_retention, historical_clv) and gaps conversion_rate, gross_margin. Gold tables are analytics.kpi_<id>, owned by governor_deploy. Do not import governor.build. design.json still stores mapping as a dict. The certify commit sha is recorded only in the target's .git/governor_published.json.
