# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
Certified answers are a separate ask path. answer() reads serve_<role>.governor_certified and governor_gaps as governor_ask with the reader role set, then makes one structured call using certified_prompts/certified.md. Code builds a single read-only SELECT from that KPI's serving view and value column, and the validator allowlist is the certified models. Python fills every number from the result row and cites the KPI id, owner, source tier and reference, certifier and date. Outcomes are answer, not_available for a catalogue KPI that is declined or not certified (quoting the gap), unanswerable, and refused for person-level requests before the KPI query. POST /v1/ask/certified uses the same body and bearer auth as /v1/ask. The frozen prompts in src/governor/ask/prompts/ are unchanged, and ask does not import governor.build. On the sample, GMV for 2026-01 is 455, and conversion_rate and gross_margin are gaps.

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

## D7 notes (implementer)
- `governor.ask.certified`: the registry, gaps and column types (information_schema, as the reader role) are read through `PostgresAdapter(allowed_roles=READER_ROLES)`. The validator policy is built in code: allowlist = the certified models, schema = their serving-view columns, limits from `knowledge/shop/access.yaml`. It calls `validator._validate` directly because `validate()` takes its allowlist from access.yaml and meta.duckdb.
- **Validator bug (outside D7 paths, for Amir):** in sqlglot 30.24, `exp.And`/`exp.Or` subclass `exp.Func`, so `_check_functions` rejects every Postgres query that has `AND` or `OR` ("function AND is not on the allowlist"). That affects the main ask path on Postgres too. The fix is one line: skip `exp.Connector` in `_check_functions`, or add `AND`/`OR` to `POSTGRES_FUNCTIONS`. Meanwhile the certified builder uses no AND: month and cohort filter as `TO_CHAR(grain, 'YYYY-MM') = 'YYYY-MM'`, year as `EXTRACT(YEAR FROM grain) = YYYY`, and several filters combine as one row comparison `(a, b) = (x, y)`.
- Reply rules: grain month takes month, year or all; cohort_month takes cohort, year or all; total takes all only. pick value needs a single row (a month, a cohort or a total). A KPI with `months_since_first` must be given it. max returns the period with its value. sum uses SUM/COUNT of the column. If the reply's value_column is null and the KPI has only one value column, that column is used.
- not_available covers a gap row, or a catalogue KPI (knowledge/kpis.yaml) that is neither certified nor in the gaps. Any other id is unanswerable. The API returns 503 `registry_unavailable` when the registry cannot be read. The certified path takes its FakeLLM from the `certified` key of the same `GOVERNOR_LLM` script.
- Acceptance D7: 27/27; pytest tests/ask 147 passed, 2 skipped (the live tests skip because the acceptance run tears the test bed down before pytest).

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
