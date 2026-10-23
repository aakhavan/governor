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

## G2a result
*Metric definitions, golden-set loader, result checker, 22 Oct 2026 16:36.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G2a`.

| check | ok | detail |
|---|---|---|
| metrics.yaml: >= 8 metrics with all fields | yes | 10 metrics; incomplete: [] |
| metrics.yaml covers the required metrics | yes | missing: [] |
| gold and metric SQL can be checked | yes | {"metric:mrr": {"rows": 1, "bad_tables": []}, "metric:arr": {"rows": 1, "bad_tables": []}, "metric:active_subscriptions" |
| every gold/metric SQL executes on the green warehouse | yes | 10 ok |
| every gold/metric SQL returns rows | yes | empty: [] |
| gold/metric SQL uses allowlisted marts only | yes | {} |
| checker.compare runs | yes | [true, false, true, true, false, false, true, false, false, true] |
| checker.compare decides the 10 locked cases | yes | wrong cases: [] |
| governor.eval.golden exposes load_golden/load_split/verify_frozen | yes |  |
| verify_frozen() is False before the golden files exist | yes |  |
| no golden questions written yet (that is G2b) | yes |  |
| no agent prompts exist yet (golden set frozen first) | yes | found: [] |
| pytest tests/eval | yes | 73 passed in 1.50s |

Review: Metric SQL matches the written definitions. Snapshots use the latest mrr_monthly month on or before as_of (2026-09-01; mart window ends there, as_of is 2026-10-22). Active means started before the month ended and not cancelled before it started. Churn sums per-account drops in active_subscriptions vs the previous month (17 rows, May 2025-Sep 2026); a cancellation still counts as active that month. Overdue is non-void, not fully paid, and days_outstanding > 30. compare rejects crossed rows, lost duplicates, and None vs 0, and the 10 locked cases follow those rules.

For Amir: compare treats a swap of two numeric columns as equal, because column names and column order are ignored on purpose. Above 300 rows the tolerance rematch is skipped, so only an exact sorted match counts. Unpaid void invoices still have nonzero days_outstanding in the mart; overdue and receivables stay on non-void invoices. Pin as_of before G2b: build_green.py rewrites as_of.txt from the clock, which moves days_outstanding even though seed 42 fixes the raw rows.

## Additions for G1
- Start from `PROVENANCE.md`: it lists every imported file and its original path. Rename imports `triage.` → `governor.core.`; replace any path built from the S4 folder with `governor.core.paths`.
- Keep changes to imported code minimal and list each one in `PROVENANCE.md` ("changed: …").

## Additions for G2a
G2a should resolve every relative date with governor.core.paths.as_of() (artifacts/green/as_of.txt). build_green.py stamps that file from UTC now, so days_outstanding changes on each rebuild even though seed 42 fixes raw rows; pin as_of before gold numbers are frozen. Marts: dim_accounts 2000, fct_invoices 30000 (one row per invoice), fct_revenue_daily 24708, mrr_monthly 11910. days_outstanding is 0 only when paid_amount_eur >= amount_eur; unpaid void invoices stay nonzero. PII is not lineage: policy.yaml maps contact_name to name, contact_email to email, card_last4 to payment_card, and harvest tags every column of that name (8 rows). card_last4 is staging/source only. Do not edit access.yaml; allowlist is those four marts; the only grant is dim_accounts.contact_email. dbt build excludes exposures, so meta.results has no exposure rows; meta.exposures still has 2. warehouse.connect() is read-only with search_path=marts. config.FAST_MODEL and EMBED_MODEL are guesses; chromadb is not installed; the Chroma collection is still named triage_knowledge.

## Additions for G2b
G2b writes evaluation/golden/questions.yaml, split.json, and FROZEN.sha256. gold_sql is required exactly for answer, aggregate, and mask, and forbidden otherwise. clarify requires missing_slot. Question ids are unique. tune and holdout must be disjoint. as_of may be a date (coerced to midnight) or a datetime. verify_frozen expects GNU sha256sum lines (hex, two spaces, filename; a leading * is stripped) for questions.yaml and split.json, and returns false while any file is missing.
Match knowledge/metrics.yaml when a question is about these metrics. DATE literals must be 2026-10-22 (as_of.txt is 2026-10-22T14:11:26+00:00). Business dates end 2026-09-30. MRR months run 2025-04-01 through 2026-09-01; the snapshot month is 2026-09-01. Churn is the per-account drop in active_subscriptions, not a cancellation count and not net MRR (that is net_new_mrr). Invoiced revenue sums non-void invoice amounts by issue month. Collected revenue sums payments by revenue_date. Outstanding and overdue skip void and fully paid invoices; overdue also needs days_outstanding > 30.
compare ignores column names and column order. Row order is ignored unless order_matters. Default rel_tol is 1e-6, with abs_tol 1e-9. None equals only None. A date equals a timestamp at midnight. Do not copy questions or gold SQL into prompts. Pin as_of before freezing gold numbers; a rebuild rewrites as_of.txt and days_outstanding.

## G2b result
*Golden set with gold SQL, frozen split, review table, 23 Oct 2026 15:02.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 1 fix loop(s); branch `factory/G2b`.

| check | ok | detail |
|---|---|---|
| metrics.yaml: >= 8 metrics with all fields | yes | 10 metrics; incomplete: [] |
| metrics.yaml covers the required metrics | yes | missing: [] |
| questions.yaml as_of equals artifacts/green/as_of.txt | yes | 2026-10-22 14:11:26+00:00 vs 2026-10-22T14:11:26+00:00 |
| exactly 40 questions, unique ids | yes | 40 / 40 unique |
| category counts | yes | {'simple': 6, 'join': 6, 'time_grain': 6, 'metric': 6, 'ambiguous': 5, 'policy': 6, 'unanswerable': 5} |
| expect matches category | yes | bad: [] |
| gold_sql present exactly for answer/aggregate/mask | yes | bad: [] |
| ambiguous questions name a missing_slot | yes | bad: [] |
| policy items cover both roles and refuse/aggregate/mask | yes | roles ['analyst', 'finance_admin'], kinds ['aggregate', 'mask', 'refuse'] |
| questions do not name tables, columns or SQL | yes | bad: [] |
| gold SQL: no SELECT *, no now()/current_date | yes | bad: [] |
| gold and metric SQL can be checked | yes | {"s01": {"rows": 1, "bad_tables": []}, "s02": {"rows": 1, "bad_tables": []}, "s03": {"rows": 1, "bad_tables": []}, "s04" |
| every gold/metric SQL executes on the green warehouse | yes | 38 ok |
| every gold/metric SQL returns rows | yes | empty: [] |
| gold/metric SQL uses allowlisted marts only | yes | {} |
| split 25 tune / 15 holdout, disjoint, covers all | yes | 25/15 |
| every category in both tune and holdout | yes | missing: [] |
| FROZEN.sha256 matches questions.yaml and split.json | yes | golden set unchanged |
| evaluation/golden/REVIEW.md lists every question for the gate review | yes |  |
| governor.eval.golden loads the files and verify_frozen() is true | yes |  |
| no agent prompts exist yet (golden set frozen first) | yes | found: [] |
| pytest tests/eval | yes | 73 passed in 1.58s |

Review: Forty questions match the G2b counts and expect rules, with gold SQL only for answer, aggregate, and mask. The SQL follows the wording: right mart grain, void filters where the question excludes them, and relative dates as DATE '2026-10-22'. Metric items copy metrics.yaml; churn is that definition limited to Q3 2026. Ambiguous items each miss one slot (metric, entity, grain, or time range). Policy matches access.yaml for both roles and refuse, aggregate, and mask. Split is 25/15, every category on both sides, and the freeze hash checks out.

For Amir: At the gate, check four choices. s05 and p06 rank dim_accounts.lifetime_billed_eur, and p05 ranks open_balance_eur; both columns include void invoices, while metrics.yaml uses billed and open balance for measures that drop voids. t01 and t06 omit empty periods (no Q4 2026 row; 2025 starts in May). a03 expects a grain clarification even though the collections metric is defined as monthly. Every account has a contact name, so p04 equals the Peru account count. m01-m03 return the snapshot month plus the value, and top-N gold is a set (order_matters false).

## Additions for G3
Do not read evaluation/golden/questions.yaml, REVIEW.md, or gold SQL when writing prompts, cards, examples, or tests, and do not edit evaluation/golden/ from G3 on. as_of is 2026-10-22T14:11:26+00:00; date literals are DATE '2026-10-22'. Latest MRR month is 2026-09-01. Business facts end 2026-09-30. compare ignores column names and column order, requires the same column count, and ignores row order unless order_matters (every gold item leaves it false). m01-m04 return (month_start, value); a bare scalar fails those items. Policy: analyst plus contact_name or contact_email values is refuse; analyst COUNT or COUNT(DISTINCT) on those columns is aggregate; finance_admin masks contact_name as '***' in an outer projection; dim_accounts.contact_email is granted. Clarify slots: a01 metric, a02 entity, a03 grain, a04 time_range, a05 metric. Holdout ids: s03 s05 j02 j05 t03 t06 m02 m04 a02 a05 p02 p04 p06 u02 u05. m05, m06, and j04 depend on days_outstanding in this green build; a rebuild that moves as_of changes results without changing FROZEN.sha256.

## Additions for G4
G4 builds catalog cards and hybrid retrieval. Do not read evaluation/golden/questions.yaml or put question text in cards. Gold tables for the retrieval eval come from gold_sql through governor.eval.golden. as_of is pinned: fixture/AS_OF and artifacts/green/as_of.txt are '2026-10-22 14:11:26+00:00' (same instant as 2026-10-22T14:11:26+00:00). paths.as_of() reads the green file. The report's as_of uses datetime.isoformat() with a T; compare datetimes, not strings. Allowlist: dim_accounts, fct_invoices, fct_revenue_daily, mrr_monthly. Mart PII tags are dim_accounts.contact_name (name) and dim_accounts.contact_email (email). The only grant is dim_accounts.contact_email for finance_admin; mask value is ***. card_last4 is staging-only and is outside detect_leak. detect_leak flags PII that reaches an output column (COUNT and aggregate FILTER do not); WHERE, JOIN, and GROUP BY alone are not leaks. That runtime policy is G5a. Leave governor.ask.baseline as schema-plus-question with no retrieval. The registry lazy-imports it from governor.ask.baseline. System.answer receives the full Question, including gold_sql and expect; only oracle may read those. chromadb is not installed and EMBED_MODEL is still a guess; tests need a fake embedder. dbt source freshness still uses the wall clock, so green sources.json can be warn or error while the marts stay pinned.

## Relocks
- 23 Oct 2026 16:27: G5a: _g5_cases.py imports the executor only when execute cases exist (it lands in G5b); placeholder executor.py removed (via supervise, by claude.ai) (changed: plan/accept/_g5_cases.py)

## G4 result (implementer notes)
`governor.ask.catalog` builds 14 cards (4 allowlisted models + 10 metrics) from meta.duckdb, access.yaml and metrics.yaml into artifacts/catalog_cards.jsonl. Model cards list the metrics that read them (from metrics.yaml SQL). Grain is the description's "One row per ..." phrase, else the unique-tested column. `governor.ask.retrieval.search` does bm25/dense/hybrid. Hybrid fuses with `governor.core.retrieval.rrf` (k=60, each list depth max(10, k)). No chromadb: dense uses numpy over artifacts/card_embeddings.npz, keyed by embedder name plus card texts. The default embedder is core.llm.get_embeddings (EMBED_MODEL still a guess, not run); `fake` is HashEmbedder. Tune recall@3: bm25 0.8333, hybrid(fake) 0.8056, dense(fake) 0.7778 (n=18). The fake hybrid score says nothing about real embeddings. Acceptance: 16/16. Full pytest: 163 passed. The test file is tests/ask/test_cards_retrieval.py, because tests/ask/test_retrieval.py clashed with tests/core/test_retrieval.py (no __init__.py).

## G4 result
*Catalog and metric cards, hybrid schema retrieval, recall@k on gold tables, 23 Oct 2026 15:56.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G4`.

| check | ok | detail |
|---|---|---|
| catalog build exits 0 | yes | {"out": "C:\\Users\\amir0\\portfolio\\governor\\artifacts\\catalog_cards.jsonl", "cards": 14, "model": 4, "metric": 10} |
| every card has the required fields | yes | 14 cards |
| one model card per allowlisted model, nothing else | yes | ['dim_accounts', 'fct_invoices', 'fct_revenue_daily', 'mrr_monthly'] |
| one metric card per metrics.yaml entry | yes | missing: [] |
| dim_accounts card lists its PII columns | yes |  |
| metric cards list the tables their SQL uses | yes |  |
| no golden questions or gold SQL in cards or code | yes |  |
| retrieval.search runs | yes |  |
| 'monthly recurring revenue' finds mrr_monthly in top 3 | yes | ['mrr_monthly'] |
| snake_case split: 'days outstanding' finds fct_invoices in top 3 | yes | ['fct_invoices'] |
| retrieval eval (bm25) runs | yes | {"mode": "bm25", "k": 3, "n": 18, "recall": 0.8333} |
| eval counts only tune questions with gold SQL | yes | n=18, expected 18 |
| bm25 recall@3 on gold tables >= 0.80 | yes | recall=0.8333 |
| hybrid eval runs with the fake embedder | yes | {"mode": "hybrid", "k": 3, "n": 18, "recall": 0.8056} |
| golden set still frozen | yes | golden set unchanged |
| pytest tests/ask | yes | 15 passed in 3.88s |

Review: Catalog and metric cards are built from meta.duckdb and metrics.yaml (4 models, 10 metrics). Card text is schema and metric definitions; golden questions and gold SQL are absent. Recall@3 is the mean share of tables parsed from gold_sql that appear on the top-k hits: BM25 0.8333 (n=18) and hybrid with HashEmbedder 0.8056. A fake meta store supplies the unit tests, so a hardcoded catalog cannot pass.

For Amir: Hybrid recall is reported and not gated; only BM25 must be at least 0.80. The probe days outstanding also matches prose on the overdue definition and the invoice column description, so test_tokens_split_snake_case is what locks the splitter. search() with embedder None calls the configured embedding model and will use the network.

## Additions for G5a
Cards in artifacts/catalog_cards.jsonl (4 models, then 10 metrics). Fields: id, kind, name, text, tables, pii_columns. Ids model:{name} and metric:{id}. Models: dim_accounts, fct_invoices, fct_revenue_daily, mrr_monthly. dim_accounts PII: contact_email, contact_name. Model text: description, grain, owner, columns (type, description, pii tag), tests, upstream sources, metrics that read the model. Metric text: label, definition, synonyms, grain, physical tables, time column. sqlglot drops CTEs and schemas. SQL is not on the card. search(query, k=5, mode=hybrid|bm25|dense, embedder=None) returns Hit(card_id, score, tables); join text on id. Hybrid: depth max(10, k), RRF k=60, then top k. embedder None uses get_embeddings (network unless EMBED_BACKEND=local). Offline: embedder fake or HashEmbedder. Cache: artifacts/card_embeddings.npz. Eval: python -m governor.ask.retrieval eval --split tune --mode bm25|hybrid --k 3 --embedder fake. Mean share of gold-SQL tables in top-k hits. Tune n=18. BM25 0.8333. Hybrid+fake 0.8056, ungated. Snake_case tokens keep the word and its parts. Do not copy questions or gold SQL into prompts or cards. as_of is 2026-10-22.

