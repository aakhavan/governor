# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
A1 is complete and accepted 14/14 on branch factory/A1 (uncommitted in the governor-airflow worktree). New: airflow/dags/governor_profile_raw.py (manual DAG, DockerOperator subclass rendering docker_url and mounts, all connection values from Airflow Variables at run time, no credentials), src/governor/api/profiles.py (auth-guarded list and get routes with regex and resolved-path checks), apps/streamlit/pages/4_Profiles.py, docs/airflow.md, and three test files. Existing files only gained lines: app.py +2, client.py +8. Full offline suite 513 passed / 21 skipped; the profile workload ran as a governor:local container against the test bed on 55432 and profiled 9 tables. The DAG itself has not yet been run under Airflow; that belongs to the airflow-platform side.

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

## E4 result
*Injection tests, error redaction and the threat model, 11 Nov 2026 14:24.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 1 fix loop(s); branch `factory/E4`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| src/governor/build/graph.py unchanged against main | yes | the file differs from main |
| src/governor/build/design.py unchanged against main | yes | the file differs from main |
| src/governor/build/prompts/repair.md unchanged against main | yes | the file differs from main |
| src/governor/build/prompts/propose.md unchanged against main | yes | the file differs from main |
| governor.build imports neither Slack nor ask | yes |  |
| redact_error runs | yes |  |
| no data value survives redaction | yes |  |
| known identifiers survive | yes |  |
| long numbers and DETAIL lines go | yes |  |
| threat model exists, at most 80 lines | yes | 57 lines |
| threat model has ASI01 | yes |  |
| threat model has ASI02 | yes |  |
| threat model has ASI03 | yes |  |
| threat model has ASI06 | yes |  |
| threat model has ASI09 | yes |  |
| threat model has Open findings | yes |  |
| threat model holds no marker or data value | yes |  |
| pytest tests/build | yes | 171 passed, 12 skipped in 51.82s |
| required tests present | yes | 9 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The acceptance lines 'the file differs from main' are the failure string stored even when the check passes. ok true means git diff --quiet against main returned 0, so graph.py, design.py, repair.md and propose.md match main. Unquoted values on a kept error line are left as written; section 25 and the threat model both say so, and Postgres quotes the values it reports.

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
