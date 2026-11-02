# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
C3 is done. The Postgres test bed is testbed/docker-compose.yml: Postgres 16, host port 55432, database shop, admin governor_admin, default password governor_local, named volume, and a healthcheck. load_olist.py checks the nine published Olist headers, then COPY-loads each CSV into schema raw as text plus _loaded_at, in one truncate-and-load transaction per table. testbed/sample is synthetic and has one customer_unique_id with two customer_ids, a canceled order, a late delivery, two reviews on one order, and two payments on one order. Real files stay in gitignored testbed/data/. The README licence note is still a TODO. psycopg[binary] is a dependency. The Postgres adapter and roles are C4. Ask still uses the DuckDB adapter until then; meta, traces, and checkpoints stay outside the adapter. as_of remains 2026-10-22T14:11:26+00:00.

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

## G10b result
*Holdout once, eval report, README, demo script, 23 Oct 2026 21:17.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/G10b`.

| check | ok | detail |
|---|---|---|
| report baseline-tune.json exists | yes |  |
| baseline-tune.json covers exactly the tune split | yes | 25 items |
| baseline-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report baseline-holdout.json exists | yes |  |
| baseline-holdout.json covers exactly the holdout split | yes | 15 items |
| baseline-holdout.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report agent-tune.json exists | yes |  |
| agent-tune.json covers exactly the tune split | yes | 25 items |
| agent-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report agent-holdout.json exists | yes |  |
| agent-holdout.json covers exactly the holdout split | yes | 15 items |
| agent-holdout.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| holdout run exactly once per system | yes | log: ['baseline', 'agent'] |
| PROMPTS_FROZEN.sha256 exists | yes |  |
| prompts unchanged since the freeze | yes | frozen ['answer.md', 'baseline.md', 'draft_sql.md', 'plan.md', 'repair.md'] vs now ['answer.md', 'baseline.md', 'draft_s |
| prompts frozen before both holdout runs | yes |  |
| no PII leak in agent runs | yes |  |
| total eval cost within the $3 budget | yes | $0.239 |
| evaluation/eval_report.md exists | yes |  |
| README has the required sections | yes | missing: [] |
| README has a Mermaid diagram and points to PROVENANCE.md | yes |  |
| README shows the holdout execution accuracy exactly as in the reports | yes | missing [] |
| demo script exists | yes |  |
| no golden text in prompts | yes |  |
| golden set still frozen | yes | golden set unchanged |
| pytest tests | yes | 281 passed in 73.75s (0:01:13) |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Acceptance checks that eval_report.md and the demo script exist, not that the prose matches the JSON. Summary and per-category counts match all four reports, and the three agent failure notes match the stored SQL. The rule classifier never labels wrong join; j05's country subquery is only in the note, and the scored miss is an extra month_start column.

## Additions for the next plan
Do not rerun holdout or edit src/governor/ask/prompts/. PROMPTS_FROZEN.sha256 is the freeze, and evaluation/holdout_runs.log already has one baseline line and one agent line. Headline holdout: execution accuracy 0.600 baseline vs 0.700 agent; policy 0.333 vs 1.000; PII leak true vs false; agent loses join 0/2 vs 1/2 and time_grain 1/2 vs 2/2. Four-run cost $0.239. evaluation/eval_report.md is generated by python -m governor.eval.report. taxonomy.yaml overrides j02, j05, and t06. The rule classifier has no wrong-join branch.

## Additions for C2
C2 is a pure refactor of the warehouse path. Keep executor results: dry_run(sql, *, timeout_s, database) and run_readonly both use _deadline and raise QueryTimeout; execute() passes Policy.timeout_s and maps QueryTimeout to code TIMEOUT. The graph dry_run node does the same and refuses with the existing warehouse-limits text. Do not send checkpoints, traces, or meta through the adapter (design section 3). Privacy stays in governor.ask.checkpoints: SqliteSaver.delete_thread, PRAGMA secure_delete=ON, PRAGMA wal_checkpoint(TRUNCATE), and question-free tombstones in governor_finished_threads so a finished id is still 409. Clarify threads stay until resume; prune_stale runs at the start of a new ask in the API and the CLI (GOVERNOR_THREAD_TTL_H, default 24, wall clock). GOVERNOR_TRACE_TEXT=1 keeps finished checkpoints. Prompts were not edited. fixture/build_green.py resolves dbt.exe or dbt next to sys.executable so the Linux image builds. as_of remains 2026-10-22T14:11:26+00:00.

## Additions for C3
Next step is C3 (Postgres test bed), not the adapter. get_adapter("postgres") raises UnknownWarehouseError until C4; GOVERNOR_WAREHOUSE defaults to duckdb. Do not send meta.duckdb, traces.duckdb, or checkpoints through the adapter. Keep dry_run's timeout_s optional: if omitted it uses access.yaml limits.timeout_s, because locked G5b calls dry_run(sql) with no timeout. Keep executor._open; tests stub it, and the duckdb branch passes connect=lambda: _open(database) into DuckDBAdapter. Adapter run defaults to JSON-safe lists (native=False). The executor passes native=True and converts rows to tuples so Decimal and date still reach graph.format_value and the eval checker; C4 must implement native. The conformance Postgres case skips when GOVERNOR_PG_DSN is unset. Its known_column is information_schema.tables.table_name, but list_columns() drops information_schema and pg_catalog, so point that case at a real test-bed table before C4 stops skipping. as_of remains 2026-10-22T14:11:26+00:00. Connection settings come from env only. Test-bed host port is 55432, database shop.

## C3 result
*Postgres test bed with the Olist loader and a synthetic sample, 02 Nov 2026 22:36.*

Implementer `claude-tc-sonnet`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/C3`.

| check | ok | detail |
|---|---|---|
| testbed/docker-compose.yml exists | yes | missing |
| testbed/load_olist.py exists | yes | missing |
| testbed/README.md exists | yes | missing |
| .gitignore keeps testbed/data/ out of git | yes |  |
| psycopg is a dependency | yes |  |
| README marks the licence check as TODO or states the licence | yes |  |
| sample olist_customers_dataset.csv exists | yes | missing |
| sample olist_customers_dataset.csv header is exact | yes | ['customer_id', 'customer_unique_id', 'customer_zip_code_prefix', 'customer_city', 'customer_state'] |
| sample olist_customers_dataset.csv has 1-30 rows | yes | 6 rows |
| sample olist_geolocation_dataset.csv exists | yes | missing |
| sample olist_geolocation_dataset.csv header is exact | yes | ['geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng', 'geolocation_city', 'geolocation_state'] |
| sample olist_geolocation_dataset.csv has 1-30 rows | yes | 5 rows |
| sample olist_order_items_dataset.csv exists | yes | missing |
| sample olist_order_items_dataset.csv header is exact | yes | ['order_id', 'order_item_id', 'product_id', 'seller_id', 'shipping_limit_date', 'price', 'freight_value'] |
| sample olist_order_items_dataset.csv has 1-30 rows | yes | 6 rows |
| sample olist_order_payments_dataset.csv exists | yes | missing |
| sample olist_order_payments_dataset.csv header is exact | yes | ['order_id', 'payment_sequential', 'payment_type', 'payment_installments', 'payment_value'] |
| sample olist_order_payments_dataset.csv has 1-30 rows | yes | 6 rows |
| sample olist_order_reviews_dataset.csv exists | yes | missing |
| sample olist_order_reviews_dataset.csv header is exact | yes | ['review_id', 'order_id', 'review_score', 'review_comment_title', 'review_comment_message', 'review_creation_date', 'rev |
| sample olist_order_reviews_dataset.csv has 1-30 rows | yes | 4 rows |
| sample olist_orders_dataset.csv exists | yes | missing |
| sample olist_orders_dataset.csv header is exact | yes | ['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_da |
| sample olist_orders_dataset.csv has 1-30 rows | yes | 5 rows |
| sample olist_products_dataset.csv exists | yes | missing |
| sample olist_products_dataset.csv header is exact | yes | ['product_id', 'product_category_name', 'product_name_lenght', 'product_description_lenght', 'product_photos_qty', 'prod |
| sample olist_products_dataset.csv has 1-30 rows | yes | 3 rows |
| sample olist_sellers_dataset.csv exists | yes | missing |
| sample olist_sellers_dataset.csv header is exact | yes | ['seller_id', 'seller_zip_code_prefix', 'seller_city', 'seller_state'] |
| sample olist_sellers_dataset.csv has 1-30 rows | yes | 2 rows |
| sample product_category_name_translation.csv exists | yes | missing |
| sample product_category_name_translation.csv header is exact | yes | ['product_category_name', 'product_category_name_english'] |
| sample product_category_name_translation.csv has 1-30 rows | yes | 2 rows |
| edge: one customer_unique_id with two customer_ids | yes |  |
| edge: a canceled order | yes |  |
| edge: an order delivered after its estimated date | yes |  |
| edge: an order with two reviews | yes |  |
| edge: an order with two payments | yes |  |
| every order's customer exists in the customers sample | yes | [] |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw with the right row counts | yes | 9 tables |
| a second load gives the same counts (idempotent) | yes | 9 tables |
| a wrong header is refused and the file is named | yes | Olist source check failed: |   olist_orders_dataset.csv: header differs (missing columns ['order_status'], unexpected co |
| pytest tests/testbed | yes | 2 passed, 1 skipped in 0.46s |
| required tests present | yes | 2 found |

Review: C3 matches its prompt. Postgres 16 listens on host port 55432 (database shop, user governor_admin, default password governor_local, named volume, healthcheck). The loader checks the nine published headers, including product_name_lenght, and COPY-loads each CSV into raw as text plus _loaded_at, with truncate and load in one transaction per table. The sample is synthetic and includes every design edge case. testbed/data/ is gitignored. The README licence note is a marked TODO. Acceptance loaded the sample twice with the same counts.

For Amir: The live load checks compare the loader JSON to CSV counts and do not query raw themselves. In this loader that JSON is SELECT count(*) after COPY, both loads matched, and a failed COPY would not print the line, so the rows were loaded. The licence acceptance check is the substring licen; the README marks a TODO and the dataset licence is still unknown. Schemas other than raw, and the roles, belong to C4.

## Additions for C4
C4 adds the Postgres adapter and roles. Leave the loader as it is. Compose: Postgres 16, host 55432, database shop, admin governor_admin, password default governor_local. A fresh database is empty until python testbed/load_olist.py --source testbed/sample (GOVERNOR_PG_DSN or --dsn). Only schema raw is created. Tables are raw.<csv stem>, source columns text, plus _loaded_at timestamptz NOT NULL DEFAULT now(). COPY CSV stores blanks as NULL. Zip prefixes stay text (01000). Keep spellings product_name_lenght and product_description_lenght. Truncate plus COPY is one transaction per table; headers are checked before any connection. psycopg[binary] is locked at 3.3.6. roles.sql, apply_roles.py, dev_governor, and private do not exist yet. Adapter DSN is GOVERNOR_PG_DSN; the acceptance admin DSN is GOVERNOR_PG_ADMIN_DSN. Conformance skips if unset; point its known column at a table the test creates, because list_columns drops information_schema and pg_catalog. Sample: uniq-0001 is cust-0001 and cust-0002; ord-0002 is canceled; ord-0003 is late; ord-0001 has two reviews and two payments. Do not commit testbed/data/. The README licence line is still a TODO. as_of remains 2026-10-22T14:11:26+00:00.
