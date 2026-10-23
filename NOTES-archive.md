# NOTES archive

Sections rotated out of NOTES.md (PLAN.md §7.4), oldest first.

## Relocks
- 23 Oct 2026 14:50: G3: pin as_of in fixture/AS_OF (found at the G2b gate review) (changed: plan.yaml, plan/accept/accept_g3.py, plan/prompts/G3.md)

## G1 result
*Foundation from the Sprint 4 import (core package, green build, fct_invoices, metadata store), 22 Oct 2026 16:18.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G1`.

| check | ok | detail |
|---|---|---|
| governor.core.paths resolves the repo root | yes | {'ROOT': 'C:\\Users\\amir0\\portfolio\\governor', 'ARTIFACTS': 'C:\\Users\\amir0\\portfolio\\governor\\artifacts', 'GREE |
| no Sprint 4 / absolute paths in src, fixture, tests | yes |  |
| PROVENANCE.md exists | yes |  |
| every core module listed in PROVENANCE.md | yes | 10 listed |
| PROVENANCE.md has a 'New in G1' section | yes |  |
| fixture/build_green.py exits 0 | yes | sum raw.payments.amount_eur 7568711.00 | sum marts.mrr_monthly.mrr 5038784.00 | elapsed_s 37.4 |
| artifacts/green complete | yes | 6 files |
| green run: every node passes | yes | 0 not passing: [] |
| warehouse readable | yes |  |
| marts exist and are non-empty | yes | {'dim_accounts': 2000, 'fct_invoices': 30000, 'fct_revenue_daily': 24708, 'mrr_monthly': 11910} |
| fct_invoices has the required columns | yes | missing: [] |
| dim_accounts has the required columns | yes | missing: [] |
| warehouse.connect(): unqualified mart names, read-only | yes | {'n': 2000, 'write': 'InvalidInputException'} |
| fct_invoices.sql exists | yes |  |
| fct_invoices pins time to as_of (no now()/current_date) | yes | ok |
| harvest CLI exits 0 | yes | exposures 2 | results 87 | freshness 2 |
| meta.duckdb readable | yes |  |
| meta tables populated | yes | {'nodes': 19, 'columns': 109, 'edges': 20, 'tests': 82, 'exposures': 2} |
| meta has the four marts | yes | missing: [] |
| PII tags propagated to dim_accounts | yes | missing: [] |
| access.yaml allowlist matches the marts | yes | ['dim_accounts', 'fct_invoices', 'fct_revenue_daily', 'mrr_monthly'] |
| access.yaml grants point at PII-tagged columns | yes | bad: [] |
| access.yaml roles unchanged | yes |  |
| second build gives identical mart counts | yes | {'dim_accounts': 2000, 'fct_invoices': 30000, 'fct_revenue_daily': 24708, 'mrr_monthly': 11910} vs {'dim_accounts': 2000 |
| pytest tests/core | yes | 40 passed in 6.70s |

Review: G1 does what its prompt asks, and the acceptance pass comes from a real green build plus harvest, not from string checks alone. paths and warehouse.connect() resolve this repo and open the marts read-only. fct_invoices.days_outstanding uses the dbt var as_of, and the test checks every open invoice against as_of.txt. PROVENANCE lists each adapted import and the new files. access.yaml is absent from the diff. Mart PII tags are rows in meta.duckdb, copied from policy.yaml by column name (8 columns), not along lineage.

For Amir: No API keys or other credentials in src, fixture, or tests. The earlier secret_in_diff stop (string lengths 46, 87, and 97) lines up with PyPI URLs and sha256 hashes in uv.lock, which G1 had to add. config.py and schemas.py still say "Sprint 4" in docstrings; accept_g1 only rejects sprint-04, Turing College, and drive-letter paths, and those are absent. Unpaid void invoices keep a nonzero days_outstanding; NOTES already flags that choice.

## G3 result
*Evaluation harness, metrics, self-test systems, baseline, 23 Oct 2026 15:41.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G3`.

| check | ok | detail |
|---|---|---|
| fixture/AS_OF pins the golden set's as_of | yes | '2026-10-22 14:11:26+00:00' vs '2026-10-22 14:11:26+00:00' |
| build scripts never read the wall clock | yes |  |
| a rebuild reproduces as_of and the marts | yes | as_of '2026-10-22 14:11:26+00:00'; fct_invoices ['30000', '369808', '8596901.00'] -> ['30000', '369808', '8596901.00'] |
| oracle run writes a report | yes | wrote C:\Users\amir0\AppData\Local\Temp\g3-accept-hu8q9v22\oracle-tune.json | {"n": 25, "execution_accuracy": 1.0, "vali |
| report summary has all metric keys | yes | missing: [] |
| report items have all keys | yes |  |
| report records golden_sha and as_of | yes |  |
| stdout last line is the summary JSON | yes |  |
| oracle: n = 25 on tune | yes | 25 |
| oracle: every metric is 1.0 and no leak | yes | {"n": 25, "execution_accuracy": 1.0, "valid_sql_first": 1.0, "valid_sql_final": 1.0, "clarify_precision": 1.0, "clarify_ |
| null run writes a report | yes | wrote C:\Users\amir0\AppData\Local\Temp\g3-accept-hu8q9v22\null-tune.json | {"n": 25, "execution_accuracy": 0.0, "valid_ |
| null: accuracy 0, clarify recall 0, precision null, no leak, policy < 1 | yes | {"n": 25, "execution_accuracy": 0.0, "valid_sql_first": null, "valid_sql_final": null, "clarify_precision": null, "clari |
| leaky run writes a report | yes | wrote C:\Users\amir0\AppData\Local\Temp\g3-accept-hu8q9v22\leaky-tune.json | {"n": 25, "execution_accuracy": 0.0, "valid |
| leaky: run flagged, every analyst item leaks, granted email is not a leak for finance_admin | yes | analyst 15/15, finance_admin 0/10 |
| detect_leak runs | yes | [true, true, true, false, false, false, true, false] |
| detect_leak decides the 8 locked cases | yes | wrong cases: [] |
| holdout: first run ok, second refused (exit 2), forced run ok | yes | rc 0/2/0 |
| holdout log has one line per completed run, tab-separated | yes | 2 lines |
| baseline (fake LLM) runs on tune | yes | wrote C:\Users\amir0\AppData\Local\Temp\g3-accept-hu8q9v22\baseline-tune.json | {"n": 25, "execution_accuracy": 0.0, "va |
| baseline report: 25 items, cost 0 with fake LLM | yes |  |
| baseline prompt file exists | yes |  |
| baseline uses no retrieval, validator or executor | yes |  |
| no golden questions or gold SQL copied into src/ or tests/ | yes |  |
| golden set still frozen | yes | golden set unchanged |
| pytest tests/eval | yes | 103 passed in 2.75s |
| pytest tests/ask | yes | 7 passed in 3.31s |

Review: G3 pins as_of in fixture/AS_OF and a rebuild reproduced that instant and fct_invoices. Oracle scores 1.0 with no PII leak; null scores accuracy 0, clarify recall 0, and null precision; leaky flags every analyst row and not finance_admin's granted email. Leak detection is sqlglot lineage plus an email scan; the mask value never leaks. A second holdout run exits 2. The baseline prompt is schema, as_of, and the question: no gold SQL, retrieval, validator, or policy. FakeLLM's SELECT 1 scores accuracy 0.

For Amir: dbt source freshness still compares _loaded_at to DuckDB now(). With as_of pinned, the two green sources go warn after 12 hours and error after 24 hours. build_green accepts that, and the mart totals still reproduced. A project macro that uses var('as_of') as snapshotted_at would stop lineage.failing_nodes from flagging those sources. That change was outside the G3 paths.

