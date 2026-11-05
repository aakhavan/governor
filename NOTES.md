# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
The build harness is governor.eval.build_eval. Each run starts from an empty dbt project and drops only dev_governor relations owned by the build login (governor_build by default), with no cascade. The agent runs the full build graph and is approved programmatically as eval-harness only inside this harness. The baseline is one plan-model call with the same profile, blueprint and KPI definitions and no template SQL; its files are written and built once with dbt build and are not repaired. Gold checks are read from the frozen gold file (table, expr, where, expected, tol) and scored on dev_governor; a missing table or column fails that check. The report has per-run status, design and dbt repairs, tests, high blueprint findings, KPI decisions (decline conversion_rate and gross_margin, build the other eight), gold passes, cost and seconds, plus means, pass rates, the gold sha256 and the models used. --max-cost-usd stops further runs. On the sample, two agent runs built and passed 6 of 6 checks; a one-KPI baseline scored 1 of 6 and was not repaired.

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

## D7 result
*Certified answers in ask, 05 Nov 2026 13:05.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D7`.

| check | ok | detail |
|---|---|---|
| certified.py exists | yes | missing |
| certified prompt lives outside the frozen prompts | yes |  |
| frozen ask prompts unchanged | yes |  |
| ask never imports build | yes |  |
| API exposes /v1/ask/certified | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| sample design and silver fixtures exist | yes |  |
| build init lists the 9 raw tables | yes |  |
| sample run pauses at the design gate | yes | {"thread_id": "114cbd9b-bff4-4eb0-8e37-c46e36ba415a", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| sample build completes | yes | {"thread_id": "114cbd9b-bff4-4eb0-8e37-c46e36ba415a", "status": "built", "report": "C:\\Users\\amir0\\AppData\\Local\\Te |
| publish creates a branch and commit | yes | {"status": "published", "branch": "governor/build-114cbd9b", "commit": "45ca28a35070e62e1f262fff34be90467db427c5", "pr_u |
| reviewer merges the pull request branch locally | yes |  create mode 100644 tests/int_order_lines__primary_key.sql |  create mode 100644 tests/stg_order_items__primary_key.sql  |
| certify deploys to analytics | yes | {"status": "certified", "kpis": ["gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purch |
| answers GMV from the certified table | yes | {"outcome": "answer", "text": "Gross merchandise value (gmv) in 2026-01 was 455. Source: certified KPI gmv (Gross mercha |
| answer cites the KPI and its certifier | yes | {"kpi_id": "gmv", "label": "Gross merchandise value", "model": "kpi_gmv", "owner": "Amir Akhavan (analytics)", "source_t |
| answer text shows the number filled by code | yes | Gross merchandise value (gmv) in 2026-01 was 455. Source: certified KPI gmv (Gross merchandise value), owner Amir Akhava |
| finance role gets the same certified answer | yes | {"outcome": "answer", "text": "Gross merchandise value (gmv) in 2026-01 was 455. Source: certified KPI gmv (Gross mercha |
| declined KPI is not_available and quotes its gap | yes | {"outcome": "not_available", "text": "conversion_rate is not available: this build is missing site sessions with a conve |
| person-level request refused | yes | {"outcome": "refused", "text": "Requests about individual people or records are refused; certified KPIs are aggregates o |
| out-of-scope question unanswerable | yes | {"outcome": "unanswerable", "text": "No certified KPI covers this question.", "value": null, "kpi_id": null, "sql": null |
| a reply naming an uncertified relation never runs | yes | {"outcome": "unanswerable", "text": "No certified KPI covers this question.", "value": null, "kpi_id": null, "sql": null |
| a reply naming a non-value column never runs | yes | {"outcome": "unanswerable", "text": "The certified KPI gmv cannot answer this: 'customer_id' is not a value column of gm |
| pytest tests/ask | yes | 147 passed, 2 skipped in 51.32s |

Review: D7 matches section 14. Code builds one SELECT on the chosen KPI's serving view from registry-checked names. The model supplies only those names. The validator allowlist is the certified models, so an unknown relation, a bad column, a bad period or a free-SQL reply never runs. Numbers come from the result row. The citation names the KPI, owner, source and certifier. Person-level replies are refused with sql null before that query. The prompt is outside the frozen ask prompts, and ask does not import governor.build. Live GMV was 455.

For Amir: Acceptance feeds a scripted reply, so this step shows the code path. A live model routing or refusing is D8. A reply that marks a person-level question as answer still runs only an aggregate SELECT of a certified value column. The two skipped pytest tests are the live GMV tests; they skip when GOVERNOR_PG_DSN is unset. The acceptance CLI already ran that path against Postgres. Existence checks report detail missing even when they pass; that is the shared helper, and the boolean is the result.

## Additions for D8a
D8 calls governor.ask.certified.answer. Do not edit src/governor/ask/prompts/ or import governor.build. Prompt: src/governor/ask/certified_prompts/certified.md. Fake key certified is a list of replies in order. Reply: kpi_id, value_column, period {kind month|year|all|cohort, value}, months_since_first, pick value|max|sum, category answer|not_available|out_of_scope|person_level. Code builds SQL from the KPI view and value column. person_level is refused with sql null before the KPI query; the registry is read first. Unknown names, bad columns, bad periods and out_of_scope are unanswerable and do not run. A catalogue or gap KPI that is not certified is not_available and quotes the gap. Cohort KPIs need months_since_first. value is the float from the result cell. citation: kpi_id, label, model, owner, source_tier, source_ref, certified_by, certified_at, git_commit. CLI: python -m governor.ask.certified QUESTION --role analyst|finance_admin --llm fake:SCRIPT|openrouter. POST /v1/ask/certified uses the /v1/ask token and body; thread_id is ignored. Dates use paths.as_of(). Sample gmv for 2026-01 is 455; gaps are conversion_rate and gross_margin.

## D8a notes (implementer)
- `governor.eval.build_eval` (CLI `python -m governor.eval.build_eval`). Each run gets a fresh target under `--work` (a new temp folder by default) with `models/sources.yml`. Before the run it drops the dev_governor relations owned by the build login (current_user). It drops views first, then tables, with no CASCADE, and retries until nothing more can be dropped. Checkpoints go per run under the work folder.
- Agent: `graph.start`, then `graph.approve(tid, "eval-harness")`. `valid_design_first_try` means the gate was reached with 0 design repairs. `validation_repairs` is the design-loop count and `dbt_repairs` is `sql_repairs`. `tests_failed` is 0 when the build succeeds; otherwise it comes from the last run_results.json.
- Baseline: one `structured("baseline", ...)` call on the plan role with the `BaselineReply {files:[{path, content}]}` schema. Paths must be under `models/` or `tests/`, with no `..`, no drive and no `sources.yml`; anything else is refused and listed. The run makes one `dbt build`. Status is built or failed, or invalid_output when the reply does not parse. For scoring only, the harness runs the blueprint check (`blueprint_high`); the baseline is never repaired. Its KPI decision counts as "build" when `kpi_<id>.sql` was written.
- Expected decisions are hard-coded (`EXPECTED_DECLINE = conversion_rate, gross_margin`; every other catalogue KPI should be built). The gold file does not carry them.
- `--max-cost-usd` is checked before each run, so the run that crosses the budget still finishes. A run with unknown cost (None) counts as 0 toward the budget and is counted in `summary.cost_unknown_runs`.

## D8a result
*Build evaluation harness (agent vs one-shot baseline), 05 Nov 2026 13:24.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D8a`.

| check | ok | detail |
|---|---|---|
| capstone ground truth frozen and unchanged | yes | capstone ground truth unchanged |
| baseline prompt exists | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| agent report written | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_vvlbbin3\\agent_report.json", "system": "agent", "runs" |
| two agent runs recorded | yes | 2 |
| every agent run built and passed 6/6 gold checks | yes | [{"run": 1, "system": "agent", "target": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_build_eval_bd1rbrnm\\agent-01 |
| agent approvals recorded as eval-harness | yes |  |
| report has a summary and the gold file hash | yes |  |
| partial baseline scores exactly the one KPI it built | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_vvlbbin3\\baseline_report.json", "system": "baseline",  |
| baseline was never repaired | yes | [{"run": 1, "system": "baseline", "target": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_build_eval_0v48x7sr\\basel |
| pytest tests/eval | yes | 120 passed in 5.63s |

Review: The harness reads the frozen gold file and never writes it. Agent approval as eval-harness happens only in run_agent, and only when the build graph is waiting at the design gate. The baseline receives the same profile, blueprint and KPI definitions with template SQL removed, is built once, and is not repaired. Cleanup drops only dev_governor relations owned by the build login. The budget flag stops further runs once recorded cost reaches the cap. Acceptance scored the agent 6/6 and a one-KPI baseline 1/6.

For Amir: Acceptance scored sample_gold.yaml (6 checks), not olist_gold.yaml (11). The olist file was not executed and its hash is unchanged. A budget cap stops the next run after recorded spend reaches it, so the run that crosses the cap still finishes. Baseline blueprint_high is a static file check after the reply and does not start a repair.

## Additions for D8b
Capstone report reads this JSON and does not recompute it. Root: system, gold_file, gold_sha256, gold_dataset, llm, models, approval, max_cost_usd, stopped_by_budget, runs_requested, runs, summary, total_cost_usd, work. approval is eval-harness for the agent and null for the baseline. A run has status, approved_by, valid_design_first_try, validation_repairs, dbt_repairs, escalated, tests_passed, tests_failed, blueprint_high, kpi_decisions_correct, kpi_decisions_total, gold_passed, gold_total, gold (id, table, passed, value, expected, tol, reason), cost_usd, seconds. Baseline design fields are null. Unparseable baseline output is status invalid_output. A crashed run is status error with gold reason run_failed. summary rates: built, valid_design_first_try, escalated, gold_all_passed, kpi_decisions_all_correct; mean covers the numeric run fields; cost_unknown_runs counts missing costs. Decision key is fixed: decline conversion_rate and gross_margin, build the other eight catalogue KPIs. sample_gold.yaml has 6 checks; olist_gold.yaml has 11. Do not write those files or FROZEN_CAPSTONE.sha256. --max-cost-usd stops starting another run once spend has reached the cap; the run that crosses it is kept. Baseline fake script key is baseline; each item is a JSON string {"files":[{"path","content"}]}. Written paths must sit under models/ or tests/ and must not replace sources.yml.
