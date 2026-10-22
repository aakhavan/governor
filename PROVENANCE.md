# PROVENANCE: files imported from Sprint 4

Imported 2026-10-22 14:32 by `scripts/import_foundation.ps1` from the Sprint 4 project (commit ed6bde6).
G1 updates the last column ("changed: ...") for every file it adapts.

| file here | source (Sprint 4) | sha256 (12) | changes |
|---|---|---|---|
| `src/governor/core/llm.py` | `src/triage/llm.py` | 49d8b6bbef5b | changed: import `triage.config` → `governor.core.config` |
| `src/governor/core/security.py` | `src/triage/security.py` | c45099ac6c62 | unchanged |
| `src/governor/core/trace.py` | `src/triage/trace.py` | a6ace97b48fc | changed: `LOG_PATH` from `paths.LOGS` instead of `triage.config.PROJECT_DIR`; docstring path |
| `src/governor/core/harvest.py` | `src/triage/harvest.py` | 78d0c8f522da | changed: knowledge paths from `paths.KNOWLEDGE`; `--out <path>` CLI option (`harvest(..., out=)`); usage/docstring module name |
| `src/governor/core/lineage.py` | `src/triage/lineage.py` | 0da7f91a0b66 | unchanged |
| `src/governor/core/retrieval.py` | `src/triage/retrieval.py` | 75bb6703632d | changed: imports → `governor.core.{paths,config,schemas,llm}`; `GREEN_META` = `paths.META`; build command name |
| `knowledge/owners.yaml` | `knowledge/owners.yaml` | 4050ea06c5df | changed: added `model.billing_mart.fct_invoices: finance-data` |
| `knowledge/policy.yaml` | `knowledge/policy.yaml` | 048ec1540942 | unchanged (tags match by column name, so mart columns are already tagged) |
| `tests/core/test_llm.py` | `tests/test_llm.py` | bb34a8188ebe | changed: imports → `governor.core.*` |
| `tests/core/test_security.py` | `tests/test_security.py` | 3d09183dc48e | changed: imports → `governor.core.*` |
| `tests/core/test_trace.py` | `tests/test_trace.py` | 6e4c2feb63fc | changed: imports → `governor.core.*` |
| `tests/core/test_harvest.py` | `tests/test_harvest.py` | 9e869eb06cb3 | changed: imports/paths → `governor.core.*`; counts and edges updated for `fct_invoices` (19 nodes, 109 columns, 20 edges, 75 tests, 87 results); exposures have no result rows (was `no-op`) |
| `tests/core/test_lineage.py` | `tests/test_lineage.py` | 1db9a7c0d903 | changed: imports/paths → `governor.core.*`; `fct_invoices` added to the payments descendants |
| `tests/core/test_retrieval.py` | `tests/test_retrieval.py` | 078ceea22070 | changed: imports → `governor.core.*`; catalog card count 18 → 19; dropped `test_grade_loop_stops_after_two_rewrites` (`triage.grading` not imported) and `test_authored_corpus_does_not_name_planted_faults` (runbooks/post-mortems not imported) |
| `fixture/` (32 files) | `fixture/` | - | changed: `build_green.py` (paths via `governor.core.paths`, `--vars as_of` to every dbt call, `dbt build --exclude-resource-type exposure` so every run result is pass/success, `fct_invoices` in the summary, dbt output to `logs/build_green_dbt.log`); `load_raw.py`, `generate_raw.py` (`FIXTURE_DIR = paths.FIXTURE`); `int_invoices_with_payments` (+`last_paid_at`, sql + yml); `marts/_models.yml` (+`fct_invoices`). Rest unchanged; target/, logs/, *.duckdb excluded |

## New in G1

| file | purpose |
|---|---|
| `src/governor/core/__init__.py` | package marker |
| `src/governor/core/paths.py` | `ROOT` (env `GOVERNOR_ROOT`), `ARTIFACTS`, `GREEN`, `WAREHOUSE`, `META`, `KNOWLEDGE`, `TRACES`, `as_of()` |
| `src/governor/core/warehouse.py` | `connect()`: read-only warehouse, `search_path = marts` |
| `src/governor/core/config.py` | stands in for S4 `triage.config` (not imported): model ids, OpenRouter URL, `get_api_key`, Chroma/chunk paths |
| `src/governor/core/schemas.py` | stands in for the part of S4 `triage.schemas` retrieval uses: `Hit`, `SearchKnowledgeResult`, `as_untrusted` |
| `fixture/billing_mart/models/marts/fct_invoices.sql` | new mart, one row per invoice; `days_outstanding` against dbt var `as_of` |
| `tests/core/test_paths.py` | root, env override, `as_of()` |
| `tests/core/test_warehouse.py` | unqualified mart names, writes refused |
| `tests/core/test_fct_invoices.py` | `days_outstanding` uses as_of, no clock functions in the SQL |
