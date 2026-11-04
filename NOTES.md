# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
C4 is done. PostgresAdapter, registered as get_adapter("postgres"), takes the DSN from GOVERNOR_PG_DSN and optional allowed_roles. Each call opens its own connection, sets the transaction read-only, sets statement_timeout from timeout_s, and may SET LOCAL ROLE after checking allowed_roles. dry_run (EXPLAIN) and run (DECLARE plus FETCH, capped at row_cap) send the user SQL as one prepared statement, so a second command cannot change the role or the timeout. QueryCanceled becomes QueryTimeout; other database errors become QueryError. testbed/sql/roles.sql, applied by testbed/apply_roles.py, creates governor_ask, governor_analyst, governor_finance_admin, and governor_build. governor_ask is read-only with statement_timeout 10s and belongs to the reader roles WITH INHERIT FALSE, SET TRUE. governor_build has USAGE and CREATE on dev_governor only. Schema private is admin-only. Conformance tests need GOVERNOR_PG_DSN and GOVERNOR_PG_ADMIN_DSN. as_of remains 2026-10-22T14:11:26+00:00.

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

## C4 result
*Postgres adapter and database roles, 04 Nov 2026 11:02.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 2 fix loop(s); branch `factory/C4`.

| check | ok | detail |
|---|---|---|
| src/governor/core/adapters/postgres.py exists | yes | missing |
| testbed/sql/roles.sql exists | yes | missing |
| testbed/apply_roles.py exists | yes | missing |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| roles applied a second time (idempotent) | yes | roles applied |
| conformance schema set up as admin | yes |  |
| governor_ask defaults to read-only transactions | yes | default_transaction_read_only=on statement_timeout=10s |
| governor_ask has a 10s statement timeout | yes | default_transaction_read_only=on statement_timeout=10s |
| Postgres adapter runs as governor_ask | yes |  |
| adapter named postgres with dialect postgres | yes | {'name': 'postgres', 'dialect': 'postgres', 'dry_good': True, 'dry_bad': False, 'row_cap': 1000, 'json_safe': True, 'tim |
| dry_run passes a good query and fails a bad column | yes | {'name': 'postgres', 'dialect': 'postgres', 'dry_good': True, 'dry_bad': False, 'row_cap': 1000, 'json_safe': True, 'tim |
| run honours row_cap | yes | 1000 |
| run returns JSON-safe values (numeric included) | yes |  |
| statement timeout raises QueryTimeout | yes | QueryTimeout |
| a write is refused by the database with QueryError | yes | QueryError |
| governor_ask cannot read raw tables | yes | QueryError |
| a role outside allowed_roles is refused with QueryError | yes | QueryError |
| an allowed role can be set | yes | ok |
| list_columns returns real columns | yes |  |
| governor_build can log in | yes |  |
| governor_build can create tables in dev_governor | yes | ok |
| governor_build cannot create tables in raw | yes | InsufficientPrivilege |
| pytest tests | yes | 304 passed, 13 skipped in 75.38s (0:01:15) |

Review: C4 matches its prompt and the review focus. governor_ask is read-only with a 10s statement_timeout in the database, and every adapter call also sets a read-only transaction and a transaction-local timeout. Roles are checked against allowed_roles before connect and applied with SET LOCAL ROLE as a quoted identifier. dry_run and run send the user SQL as one prepared statement, so a second command cannot SET ROLE or clear the timeout. Only the documented test-bed passwords appear. governor_build has CREATE on dev_governor only.

For Amir: accept_c4 does not send a two-statement query, and it stops Docker before pytest, so the smuggle tests did not run in the green pytest (they skip without a DSN). The guard is connection.execute(..., prepare=True): psycopg sends a Parse, and Postgres rejects a second command before it runs. Writes through run() fail at DECLARE because a cursor query must be a SELECT; the transaction is still read-only, and governor_ask has default_transaction_read_only=on.

## Additions for C5
C5 grants belong on governor_analyst and governor_finance_admin, not on governor_ask. governor_ask is a member of both WITH INHERIT FALSE, SET TRUE, so those grants apply only after SET ROLE. Pass role= to PostgresAdapter.run and dry_run; get_adapter("postgres", allowed_roles=[...]) raises QueryError before connecting if the role is not listed. list_columns takes no role and runs as the login, so a governor_ask connection will not see serve_* columns. Schema private already exists and is revoked from all four roles and PUBLIC; store the salt in private.pii_salt and do not put it in a view definition. dev_governor is the only schema where governor_build has CREATE. raw is not granted to ask, build, or the readers. Adapter DSN is GOVERNOR_PG_DSN (the acceptance ask login); admin DDL uses GOVERNOR_PG_ADMIN_DSN. Password env vars are GOVERNOR_ASK_PASSWORD and GOVERNOR_BUILD_PASSWORD, with defaults governor_ask_local and governor_build_local. run() is JSON-safe unless native=True, which the executor already passes. Conformance tests skip unless both DSNs are set, and accept_c4 stops Docker before pytest. as_of remains 2026-10-22T14:11:26+00:00.
