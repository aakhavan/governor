# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D1 is in place. The compose host port is ${GOVERNOR_PG_PORT:-55432}; acceptance uses its own stack on 55433. governor_build has USAGE on schema raw and SELECT on its tables, plus default privileges so later admin-created raw tables stay readable; CREATE remains only on dev_governor, and private is unchanged. dbt-postgres 1.11.0 is locked beside dbt-core 1.12.6 so the postgres adapter imports. python -m governor.build init writes a target project whose profiles.yml takes host, port, dbname, user, and password only from env_var, with no password default in the file; the test-bed password default governor_build_local stays in build_dsn() only. init_target does not overwrite an existing dbt_project.yml, profiles.yml, or model file. run_dbt calls the dbt next to sys.executable and does not resolve symlinks. Shop policy and access files are still unwritten.

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
