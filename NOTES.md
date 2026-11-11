# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
E4 redacts dbt errors when the repair prompt is rendered and leaves the stored failure and the escalation record raw. redact_error drops DETAIL, HINT, CONTEXT, Failing row and Key ( lines, blanks single-quoted text and unknown double-quoted spans, and replaces runs of 7 or more digits with #. Known identifiers stay when double-quoted: model and column names, raw tables and columns, and the schemas dev_governor and raw. All five hijack shapes in tests/build/test_threats.py get findings from design.validate, which was not changed, and the threat model lists no xfail. docs/capstone/threat-model.md is 57 lines and covers ASI01, ASI02, ASI03, ASI06 and ASI09. graph.py, design.py, repair.md and propose.md match main. A well-typed wrong mapping still passes the code checks, including L8, and is left to the design-gate reviewer and evaluation/build_gold.

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

## E3 result
*Perturbed test bed for one holdout run, 11 Nov 2026 13:32.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/E3`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| testbed/load_olist.py unchanged against main | yes | the file differs from main |
| README has the perturbed holdout section | yes |  |
| README states the Olist licence | yes |  |
| no real data tracked | yes |  |
| build_eval has --policy | yes |  |
| perturb.py runs on the sample (a) | yes | {"cust": 6, "geo_zip": 5, "ord_line": 6, "ord_pay": 6, "ord_rvw": 4, "ord_hdr": 5, "ord_dlv": 5, "prod": 3, "slr": 2, "c |
| perturb.py runs on the sample (b) | yes | {"cust": 6, "geo_zip": 5, "ord_line": 6, "ord_pay": 6, "ord_rvw": 4, "ord_hdr": 5, "ord_dlv": 5, "prod": 3, "slr": 2, "c |
| mapping.json, policy.yaml and the junk table are written | yes | cat_xlat.csv, cust.csv, etl_audit_log.csv, geo_zip.csv, mapping.json, ord_dlv.csv, ord_hdr.csv, ord_line.csv, ord_pay.cs |
| two runs give identical files | yes |  |
| every sample table is renamed | yes |  |
| pytest tests/testbed | yes | 15 passed, 7 skipped in 0.77s |
| required tests present | yes | 8 found |
| pytest tests/eval | yes | 153 passed in 8.15s |
| required tests present | yes | 1 found |

Review: E3 preserves every sample cell and row count, gives every table and column a new name (orders split into ord_hdr and ord_dlv), and writes a policy whose keys are exactly the renamed PII columns. load_csv_dir --replace drops only schema raw and refuses a non-empty raw. build_eval --policy only forwards the path; without it the shop policy stays. Acceptance tests cover those claims, and no real Olist data is tracked.

For Amir: mapping.json records olist_orders_dataset.order_id only as ord_hdr.ord_ref; the same ids are also on ord_dlv. Tag values are still customer_id, location, and free_text, so the model sees the PII class on the new column names. The load_olist acceptance detail is the failure string stored on a passing check; the file matches main. Gold numbers are still the full dataset (99,441 orders). The holdout run is still yours.

## Additions for E4
E4 must leave src/governor/build/graph.py, src/governor/build/design.py, and evaluation/ unchanged. E3 added testbed/perturb.py, testbed/load_csv_dir.py, build_eval --policy, and the Perturbed holdout section in testbed/README.md. knowledge/shop/policy.yaml is still the original column names. A perturbed policy is an output of perturb.py: same tags (customer_id, location, free_text), keys renamed (cust_ref, cust_uid, cust_zip5, cust_town, cust_uf, geo_y, geo_x, slr_zip5, slr_town, rvw_ttl, rvw_txt). The profiler marks PII when the column name is a policy key, on every table that has that name. Orders are split into ord_hdr and ord_dlv; mapping.json points order_id only at ord_hdr.ord_ref, and ord_dlv also carries it. etl_audit_log (20 fixed rows) is not in the mapping. load_csv_dir touches only schema raw; --replace is required when raw is not empty. build_eval without --policy leaves hooks unset, and Hooks.policy stays the shop policy. The holdout run has not been executed.

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

## Additions for the next plan
Batch 2d has no further code step; section 26 is the human planner sweep and must not change graph.py, design.py, or the frozen gold files. Redaction happens only inside silver.repair_prompt. Do not redact st['failures'] or the escalation error. Single-quoted spans, including ref('model'), always become '…'. A double-quoted span is kept only on an exact case-insensitive match to error_identifiers (design model and column names, staging raw tables and columns, schemas dev_governor and raw). Unquoted text on a kept line is unchanged. The five hijack shapes already fail validation (UNKNOWN_SOURCE_TABLE, UNKNOWN_SOURCE_COLUMN, KPI_UNKNOWN, PII_UNTAGGED, MAPPING_UNKNOWN_COLUMN); there is no strict xfail to keep. A mapping that is well typed but wrong is not a code finding.
