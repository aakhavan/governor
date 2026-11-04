# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D2 is in place. python -m governor.build profile reads schema raw as the build login and returns the section 5 profile from server-side aggregates: row counts, inferred types, candidate keys, and relationships. PII columns (policy names) contribute counts only; min and max are queried only for other integer, numeric, date, and timestamp columns, so a PII value is not fetched. On the synthetic sample there are 9 tables and 7 relationships; customer_id is a key and customer_unique_id is not; several extra keys exist only because the sample is small. D1 still stands: init does not overwrite dbt_project.yml, profiles.yml, or a model file, and profiles.yml takes the password only from env_var. The acceptance stack is a separate compose project on its own port.

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

## D1 result
*Test-bed isolation, build role reads raw, target dbt workspace, 04 Nov 2026 17:41.*

Implementer `claude-tc-sonnet`; reviewers `cursor-grok`: pass; 2 fix loop(s); branch `factory/D1`.

| check | ok | detail |
|---|---|---|
| compose maps the host port from GOVERNOR_PG_PORT | yes |  |
| dbt-postgres is a dependency | yes |  |
| src/governor/build/workspace.py exists | yes | missing |
| src/governor/build/dbt.py exists | yes | missing |
| src/governor/build/__main__.py exists | yes | missing |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| acceptance stack listens on its own port | yes | 0.0.0.0:55433 |
| build-role probe runs | yes |  |
| governor_build can read raw | yes | {'reads_raw': True, 'create_raw': 'InsufficientPrivilege', 'create_dev': 'ok', 'private': False} |
| governor_build cannot create in raw | yes | {'reads_raw': True, 'create_raw': 'InsufficientPrivilege', 'create_dev': 'ok', 'private': False} |
| governor_build can create in dev_governor | yes | {'reads_raw': True, 'create_raw': 'InsufficientPrivilege', 'create_dev': 'ok', 'private': False} |
| governor_build has no access to private | yes | {'reads_raw': True, 'create_raw': 'InsufficientPrivilege', 'create_dev': 'ok', 'private': False} |
| build init lists the 9 raw tables | yes |  |
| target has dbt_project.yml | yes | missing |
| target has profiles/profiles.yml | yes | missing |
| target has models/sources.yml | yes | missing |
| target has models/staging | yes | missing |
| target has models/intermediate | yes | missing |
| target has models/marts | yes | missing |
| target has tests | yes | missing |
| target has governor | yes | missing |
| profiles.yml reads credentials through env_var | yes |  |
| no password written into the target | yes | [] |
| sources.yml declares the raw tables with columns | yes |  |
| init is idempotent | yes | {"target": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_ojrghft0\\olist-dbt", "tables": ["olist_customers_da |
| dbt parse succeeds through run_dbt | yes | {'ok': True, 'tail': ' parse.\n16:34:07  [WARNING]: Configuration paths exist in your dbt_project.yml file which do not  |
| pytest tests/build | yes | 6 passed, 1 skipped in 0.51s |

Review: D1 matches the prompt and the passing acceptance. Profiles use env_var only and the password has no default in the file; the test-bed default stays in build_dsn(). governor_build gains USAGE and SELECT on raw, including later admin-created tables, and still cannot create in raw or use private. init_target does not overwrite dbt_project.yml or model files. dbt is the executable next to sys.executable, with no resolve(). dbt parse ran for real on dbt 1.12.6.

For Amir: dbt parse warns that models.shop.marts is an unused config path while marts is empty; that config is what the contract asks for. pytest skipped the live test (6 passed, 1 skipped); acceptance itself ran init and parse with the build password set. The prompt also asked for a NOTES line naming the adapter version: the lockfile has dbt-postgres 1.11.0 with dbt-core 1.12.6. Acceptance does not create a raw table after roles are applied, so the default-privilege grant is not live-probed; the SQL is in the raw-exists block.

## Additions for D2
Use governor.build. init_target(target, project_name) creates the layout and will not replace dbt_project.yml, profiles.yml, or an existing model file. The CLI init also calls write_sources, which rewrites models/sources.yml from information_schema: every raw base-table column, including _loaded_at, in ordinal order; table names sorted. build_dsn() reads GOVERNOR_PG_HOST, GOVERNOR_PG_PORT, GOVERNOR_PG_DB, GOVERNOR_BUILD_USER, and GOVERNOR_BUILD_PASSWORD, and falls back to localhost, 55432, shop, governor_build, and governor_build_local. profiles.yml does not default the password, so a dbt command that connects needs GOVERNOR_BUILD_PASSWORD in the environment. run_dbt(target, args) adds --project-dir, --profiles-dir <target>/profiles, and --no-use-colors, deletes a stale target/run_results.json first, and returns DbtResult. Marts materialization is models.<project_name>.marts +materialized table; dbt parse warns that path is unused until a model exists. Do not overwrite dbt_project.yml or the project name will drift from that config. The lockfile has dbt-postgres 1.11.0 beside dbt-core 1.12.6; dbt uses psycopg2 while the rest of governor uses psycopg 3. The raw grants are in the raw-exists guard in testbed/sql/roles.sql.

## D2 notes (implementer)
- `governor.build.profile.profile_schema(dsn, schema, policy)` returns the section 5 dict; `governor.build.models.Profile` validates it (`schema`/`from` are aliases: `schema_`/`from_`). `python -m governor.build profile [--schema raw] [--policy f] [--out f]`; `--out` prints a one-line JSON summary. The connection is read-only, `work_mem` 128MB for that session.
- Type rules: one set of anchored patterns (`PATTERNS`) used both server-side and by `infer_type()` offline. Values with leading zeros (`01000`) are `text`, so zip prefixes stay codes. A mix of dates and timestamps is `timestamp`. A value that matches a pattern but fails the cast (e.g. `2026-02-30`) demotes the column to `text`. Blank strings count as null.
- Speed: a 10k-row sample proposes the type, then the full scan checks only that type and its wider ones. Distinct counts use hash `select distinct` with `collate "C"` (`count(distinct)` under the DB collation was 4x slower). Pair keys skip pairs with a duplicate in the first 100k rows. Measured on the acceptance stack: 2 synthetic 1M-row tables (one with 4 true pair keys) in 24 s.
- The policy matches a bare column name or `table.column`. Without `--policy` nothing is PII, so pass the shop policy. For Amir: should the CLI default to `knowledge/shop/policy.yaml`?
- Sample: orders has 5 single-column candidate keys (5 rows, every timestamp unique); that's expected on tiny data, and D3's design should prefer `*_id` keys.

## D2 result
*Profile the raw schema, 04 Nov 2026 18:09.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D2`.

| check | ok | detail |
|---|---|---|
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| profile CLI writes the profile | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_qfhdv2gk\\profile.json", "schema": "raw", "tables": 9,  |
| all 9 raw tables profiled | yes | ['olist_customers_dataset', 'olist_geolocation_dataset', 'olist_order_items_dataset', 'olist_order_payments_dataset', 'o |
| row counts match the sample | yes |  |
| loader columns starting with _ are left out | yes |  |
| orders key is order_id | yes | [['order_id'], ['customer_id'], ['order_purchase_timestamp'], ['order_approved_at'], ['order_estimated_delivery_date']] |
| customer_id is a key and customer_unique_id is not | yes | [['customer_id']] |
| orders.customer_id relates to customers.customer_id | yes | [('olist_order_items_dataset.order_id', 'olist_orders_dataset.order_id'), ('olist_order_items_dataset.product_id', 'olis |
| purchase timestamp inferred as timestamp | yes | {'name': 'order_purchase_timestamp', 'inferred_type': 'timestamp', 'null_rate': 0.0, 'distinct': 5, 'pii': False, 'min': |
| price inferred as numeric | yes | {'name': 'price', 'inferred_type': 'numeric', 'null_rate': 0.0, 'distinct': 3, 'pii': False, 'min': 50.0, 'max': 100.0} |
| customer_unique_id is flagged PII with no min or max | yes | {'name': 'customer_unique_id', 'inferred_type': 'text', 'null_rate': 0.0, 'distinct': 5, 'pii': True, 'min': None, 'max' |
| no PII value appears in the profile | yes | [] |
| pytest tests/build | yes | 23 passed, 7 skipped in 0.61s |

Review: D2 profiles raw in SQL and matches section 5. Python receives counts plus min/max only for non-PII integer, numeric, date, and timestamp columns; policy columns, including numeric lat/lng, are counts only. Sample keys, the seven relationships, types, row counts, and the PII-string check all follow from that rule. Table and relationship order is sorted, and nothing reads the clock.

For Amir: On this five-row sample, section 5 treats every unique column as a key, so orders also keys its purchase, approved, and estimated-delivery timestamps, and products keys its measure columns. It will not hold on the full extract. The policy file does not name geolocation_zip_code_prefix, geolocation_city, geolocation_state, or seller_state. Those columns are text in the sample, so no value is written. Lat and lng are listed and their min/max are suppressed. Live pytest was skipped (no DB env in that process); the CLI check in accept_d2.py is what ran the profile.

## Additions for D3
profile_schema(dsn, schema, policy) and the profile CLI use build_dsn(). Shape: schema, profiled_at_rows (always true), tables (name order), relationships (from, to order). Columns are ordinal, skipping names that start with _. Fields: inferred_type (boolean|integer|numeric|date|timestamp|text), null_rate (6 d.p.), distinct, pii, min, max. pii means the column or table.column is a policy key (load_policy on knowledge/shop/policy.yaml). min/max only for non-PII integer (int), numeric (float), date (YYYY-MM-DD), timestamp (YYYY-MM-DD HH:MM:SS). Keys: non-null, distinct == rows; pairs only if no single-column key. Relationships: single-column keys only, from the other column to the key, coverage of non-null distinct values >= 0.95, 4 d.p. Sample has seven: items.order_id, items.product_id, items.seller_id, payments.order_id, reviews.order_id, orders.customer_id, products.product_category_name. customer_id is a key; customer_unique_id is not. Extra keys are tiny-sample artifacts (timestamps, review_score, product measures, seller zip/city/state); do not treat them as business primary keys. Models live in governor.build.models. build does not import governor.ask.
