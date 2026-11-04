# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
C5 is in place. governor.core.serving apply rebuilds serve_analyst and serve_finance_admin in one transaction: a salted SHA-256 view and a masked view per source table, the salt stored only in private.pii_salt, and each reader role granted only its own schema. The Postgres validator requires serve_<role>.<model> and an allowlist of read-only functions, so set_config and query_to_xml are refused. The Postgres adapter clamps statement_timeout to 10 seconds. Shop policy and access files under knowledge/ are still unwritten. Acceptance passed, including the live serving checks. The testbed pytest module skips unless both DSNs are set, and the acceptance script stops Docker before pytest, so those tests did not run in the green pytest.

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

## C5 implementer notes
`governor.core.serving apply` runs in one admin transaction: salt into private.pii_salt (one row), drop every view in serve_analyst / serve_finance_admin, recreate one per source table, revoke from PUBLIC and the other governor roles, grant USAGE + SELECT to the owning reader role only. Analyst views read the salt with a scalar subquery (view owner's rights), so the value is never in a definition. `--access` defaults to knowledge/access.yaml (mask_value, finance_admin grants). Validator, postgres dialect only: relations must be `serve_<role>.<model>` (unqualified refused), every function must be on `POSTGRES_FUNCTIONS` and unqualified (`FUNCTION_NOT_ALLOWED`), `FOR UPDATE/SHARE` refused. Postgres adapter caps statement_timeout at 10 s (`MAX_TIMEOUT_S`). Open: tests/testbed/test_testbed.py::test_load_sample_idempotent loads with GOVERNOR_PG_DSN, which since C4 is the ask login, so it fails when both DSNs are set; tests/testbed/test_serving.py did not run against a live database here (accept_c5 stops Docker before pytest).

## C5 result
*Serving schemas and the validator in the Postgres dialect, 04 Nov 2026 12:43.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 2 fix loop(s); branch `factory/C5`.

| check | ok | detail |
|---|---|---|
| src/governor/core/serving.py exists | yes | missing |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| serving apply succeeds | yes | {"finance_grants": ["olist_customers_dataset.customer_city"], "pii_columns": ["olist_customers_dataset.customer_city", " |
| serving apply is idempotent | yes | {"finance_grants": ["olist_customers_dataset.customer_city"], "pii_columns": ["olist_customers_dataset.customer_city", " |
| serving checks run | yes |  |
| one view per table per role (18 views) | yes | 18 |
| the salt never appears in a view definition | yes |  |
| analyst sees PII as 64-hex digests | yes |  |
| analyst view contains no raw PII values | yes |  |
| COUNT(DISTINCT) on hashed PII equals the raw distinct count | yes |  |
| non-PII columns pass through unchanged | yes |  |
| analyst is denied the finance schema | yes |  |
| analyst is denied private (salt) | yes |  |
| analyst is denied raw | yes |  |
| finance sees ungranted PII masked | yes |  |
| finance sees the granted column unmasked | yes |  |
| finance is denied the analyst schema | yes |  |
| pytest tests | yes | 309 passed, 19 skipped in 94.28s (0:01:34) |
| required tests present | yes | 5 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The green pytest skipped all six tests in tests/testbed/test_serving.py, including test_postgres_timeout_clamped, because accept_c5 stops Docker and that module skips without the DSNs. Serving itself was checked live by accept_c5. The 10s cap is in PostgresAdapter._session and was not executed during that pytest. QueryTimeout still names the caller's timeout_s, so a 3600s request cancelled at 10s is reported as 3600s.

## Additions for C6
Serving is `python -m governor.core.serving apply --source <schema> --policy <file> [--access <file>]` using GOVERNOR_PG_ADMIN_DSN and GOVERNOR_PII_SALT. It writes one view per source table in serve_analyst and serve_finance_admin. Analyst PII is encode(sha256(convert_to((SELECT salt FROM private.pii_salt) || cast(value as text), 'UTF8')), 'hex'). Finance PII is the access mask unless finance_admin grants table.column. The salt row is replaced on each apply and is not in the view definition. Database roles are governor_analyst and governor_finance_admin (USAGE and SELECT on their own schema only). governor_ask does not inherit those grants; it still needs SET ROLE. In the postgres dialect the validator allows only unqualified functions in POSTGRES_FUNCTIONS and rejects anything else as FUNCTION_NOT_ALLOWED. That code is not in the graph POLICY_RULES, so a bad function is repaired rather than refused immediately. PostgresAdapter clamps statement_timeout to 10s (MAX_TIMEOUT_S). knowledge/ was not changed; shop policy and access are still unwritten. tests/testbed/test_testbed.py::test_load_sample_idempotent loads through GOVERNOR_PG_DSN, the ask login, so a full pytest with both DSNs set can fail that older test.
