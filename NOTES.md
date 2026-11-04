# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
C6 is in place. governor.core.catalogue loads the KPI catalogue, the layer blueprint and approved decisions. knowledge/kpis.yaml and knowledge/approved.yaml are version 1 and empty; definitions are added only after Amir approves them. knowledge/blueprint.md maps bronze to sources, silver to staging and intermediate, and gold to marts, with rules L1-L9 at the agreed severities and no exceptions. A proposed KPI may omit owner and source; an approved KPI needs both, and a vendor source needs a note. render fills template placeholders from a name mapping and refuses a missing name, an unknown name, or a value that introduces a placeholder. Shop policy and access files under knowledge/ are still unwritten. Blueprint wording is waiting on Amir's gate.

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

## C6 result
*KPI catalogue, layer blueprint and approved-decisions formats, 04 Nov 2026 17:26.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 2 fix loop(s); branch `factory/C6`.

| check | ok | detail |
|---|---|---|
| src/governor/core/catalogue.py exists | yes | missing |
| knowledge/blueprint.md exists | yes | missing |
| knowledge/kpis.yaml exists | yes | missing |
| knowledge/approved.yaml exists | yes | missing |
| catalogue module runs | yes |  |
| a valid catalogue loads | yes |  |
| validation catches duplicate_id and names the KPI | yes | True |
| validation catches bad_status and names the KPI | yes | True |
| validation catches undeclared_placeholder and names the KPI | yes | True |
| validation catches unknown_relation and names the KPI | yes | True |
| render fills every placeholder | yes |  |
| render refuses a missing mapping | yes | refused |
| render refuses an unknown name | yes | refused |
| blueprint maps bronze/silver/gold to sources, staging+intermediate, marts | yes | {'bronze': ['sources'], 'silver': ['staging', 'intermediate'], 'gold': ['marts']} |
| blueprint rules L1-L9 with the agreed severities | yes | {'L1': 'high', 'L2': 'high', 'L3': 'high', 'L4': 'high', 'L5': 'medium', 'L6': 'high', 'L7': 'high', 'L8': 'high', 'L9': |
| blueprint starts with no exceptions | yes | [] |
| no KPI definitions invented (catalogue empty) | yes | [] |
| approved decisions start empty | yes | [] |
| pytest tests/core/test_catalogue.py | yes | 35 passed in 0.95s |
| required tests present | yes | 1 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The blueprint prose is plain and follows L1-L9; your gate is still the wording approval. Design section 6's AOV sample leaves "item price, freight excluded" unquoted inside a flow mapping, so YAML splits it at the comma. The loader rejects that form; quote those descriptions in real entries. Catalogue status approved means you approved the definition, separate from a certified metric.

## Additions for the next plan
Use governor.core.catalogue. load_kpis, load_blueprint and load_approved raise CatalogueError (a ValueError) and name the file; KPI errors also name the id. model_dump() mirrors the YAML: catalogue.kpis, blueprint.layers['silver'].dbt, and decisions. SOURCE_PRECEDENCE is company, then accounting, then platform, then vendor. A proposed KPI may omit owner and source; an approved KPI needs both; a vendor source needs a note. There is no conflict resolver yet; the order is only recorded on SOURCE_PRECEDENCE and in the kpis.yaml header. render(kpi, mapping) substitutes relation and input names and refuses unknown names, blanks, and any {placeholder} in a value or in the result. knowledge/kpis.yaml and knowledge/approved.yaml are empty and human-owned; do not invent KPIs or decisions. knowledge/blueprint.md is the standard: bronze=sources, silver=staging and intermediate, gold=marts, rules L1-L9, exceptions []. Quote flow-mapping values that contain commas. Catalogue status approved means the definition was approved; it is not a certified metric.
