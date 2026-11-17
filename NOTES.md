# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
F1 and F2 are implemented and reviewed on branch factory/F2. src/governor/build/drift.py provides fingerprint, fingerprint_hash, diff and the Drift model; the build graph's record node writes governor/profile_fingerprint.json at approval and publish.GENERATED includes it. tests/build/test_drift.py holds the six required tests and the F2 acceptance passes (181 passed, 12 skipped on tests/build). The acceptance scripts for F1 to F6 were relocked to collect test folders by explicit path because pytest skips folders named build. One leftover, tests/core/test_build_drift.py, duplicates the drift tests and awaits deletion by Amir, after which the extra allowed_paths entry in plan-batch3.yaml can be reverted. F3 to F6 are pending.

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

## A1 result
*Airflow integration (manual profile DAG, profiles API route, Profiles page), 13 Nov 2026 20:56.*

Implementer `claude-tc-opus`; reviewers `claude-tc-fable`: pass, `cursor-grok`: pass; 2 fix loop(s); branch `factory/A1`.

| check | ok | detail |
|---|---|---|
| apps/streamlit/client.py only gains lines (<= 40) | yes | +8 -0 |
| src/governor/api/app.py only gains lines (<= 3) | yes | +2 -0 |
| diff inspected | yes | 30	0	plan/prompts/A1.md | 2	0	src/governor/api/app.py | warning: in the working copy of 'STATUS.md', CRLF will be replac |
| DAG file exists | yes | C:\Users\amir0\portfolio\governor-airflow\airflow\dags\governor_profile_raw.py |
| DAG imports allowed modules only | yes |  |
| dag_id governor_profile_raw | yes |  |
| manual only | yes |  |
| no literal password | yes |  |
| uses Variables for connection values | yes |  |
| full offline test suite green | yes | 513 passed, 21 skipped in 111.39s (0:01:51) |
| required tests present | yes | 6 found |
| governor:local builds from the worktree | yes | #16 unpacking to docker.io/library/governor:local | #16 unpacking to docker.io/library/governor:local 0.6s done | #16 DO |
| test bed up on 55432 | yes | start ../governor/testbed first |
| profile runs as a container against the test bed | yes | 9 tables |

Review: claude-tc-fable: pass | cursor-grok: pass

For Amir: Pass. Watch three things when airflow-platform triggers the DAG: (1) the _RenderedDockerOperator subclass turns the Mount into a plain dict at render time, which docker-py accepts but nothing here executes; (2) the volume default governor_governor-data was not confirmed with docker volume ls; (3) an unset governor_build_password Variable renders as the literal string None and fails at Postgres auth, as docs/airflow.md states. I could not re-run pytest in this session (approval unavailable), so the test result is the acceptance's own run.

## Additions for the next plan
Profiles API: GET /profiles (newest first by mtime, max 100) and GET /profiles/{run_id} (raw bytes, 404 if absent, 422 if run_id fails ^[A-Za-z0-9_.+-]{1,128}$) live in src/governor/api/profiles.py behind make_router(caller_role); they read $GOVERNOR_STATE_DIR/profiles/ at request time (relative to repo root, like paths.STATE). The DAG writes /data/profiles/<run_id with ':'->'_'>.json, so the API's state dir must be the same volume mounted at /data in the compose stack. DockerOperator does not template docker_url or mounts natively; the DAG uses a _RenderedDockerOperator subclass that adds them to template_fields, so Airflow renders the Mount into a plain dict. Variables: governor_data_volume (default governor_governor-data, unverified against docker volume ls), docker_url, governor_pg_host/port/db, governor_build_user, governor_build_password (no default; missing renders as the string 'None'). The airflow-platform step must actually trigger the DAG once to prove the subclass and the volume name. Tests: tests/test_api_profiles.py, tests/test_airflow_dag.py (static AST, Airflow not installed), tests/ui/test_profiles_page.py over the ASGI client. accept_a1 now drops GOVERNOR_PG_DSN/GOVERNOR_PG_ADMIN_DSN before pytest so the live test-bed test skips.

## Additions for F2
governor.core.pgconn.with_timeout(dsn) and connect_timeout_s() exist; any new psycopg.connect under build/ or core/ must wrap its DSN with with_timeout (eval/ stays raw by contract). workspace.build_address() returns host:port/db for messages; slack.config.workspace() returns (paths.KNOWLEDGE, address) and start_line(config) builds the start-up line; blocks.usage() takes an optional (knowledge_name, address) tuple for the footer. The dbt profile template only affects newly written profiles.yml files; existing targets keep theirs. Pytest's default norecursedirs skips tests/build/ when collecting from 'tests', so required tests must live in tests/core/ or tests/integrations/. The unreachable-database test has no hard timeout guard, so a regression of with_timeout in profile_schema would hang the suite instead of failing; consider adding a lower-bound elapsed check or OperationalError match if that test is touched again.

## F2 result
*Profile fingerprint and drift, 17 Nov 2026 17:23.*

Implementer `claude-tc-opus`; reviewers `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/F2`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| drift module exists | yes | missing in src/governor/build/drift.py |
| diff exists | yes | missing in src/governor/build/drift.py |
| fingerprint written at approval | yes | missing in src/governor/build/graph.py |
| fingerprint published | yes | missing in src/governor/build/publish.py |
| pytest tests/build | yes | 181 passed, 12 skipped in 58.46s |
| required tests present | yes | 6 found |

Review: F2 does what section 28 asks. The fingerprint holds only names, inferred types, PII flags, candidate keys, version and schema name; tables, columns and keys are sorted so the sha256 over canonical JSON is order-independent. diff reports names and type pairs only. The record node writes governor/profile_fingerprint.json with thread_id, approved_on, hash and fingerprint next to approved.yaml, and publish.GENERATED names it. The graph changes nowhere else. Tests inject distinctive values and sample cells and prove none leak.

For Amir: Delete tests/core/test_build_drift.py and remove it from F2's allowed_paths in plan-batch3.yaml; it re-runs the six drift tests under a second module name whenever pytest is invoked on tests, and the relocked acceptance scripts no longer need it. The extra 'governor/profile_fingerprint.json' entry in publish.GENERATED is redundant with 'governor' but harmless.

## Additions for F3
F3 can rely on: graph.target_fingerprint(target) gives <target>/governor/profile_fingerprint.json; its JSON has keys thread_id, approved_on (ISO date), hash, fingerprint. drift.fingerprint accepts a Profile or the section 5 dict (it validates with Profile, extra='forbid', so pass exactly the profiler's dict). drift.fingerprint_hash(fp) is sha256 of json.dumps(fp, sort_keys=True, separators=(',',':')). drift.diff(old_fp, new_fp) returns Drift with .empty and .summary_lines() (sorted plain lines, names and type pairs only). The compare node should read the file through target_fingerprint and compare doc['hash'] with fingerprint_hash(fingerprint(state['profile'])). Note pytest's default norecursedirs skips tests/build when invoked on 'tests'; acceptance scripts now collect tests/build explicitly, so no re-export shim is needed. tests/core/test_build_drift.py is a workaround slated for deletion; do not depend on it.
