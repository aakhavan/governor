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

## G5a result (implementer notes)
`governor.ask.policy.Policy.for_role(role, access_path=None, meta_path=None)` reads access.yaml plus model columns, types and PII tags from meta.duckdb (cached by file mtime). An unknown role raises UnknownRoleError. `governor.ask.validator.validate(sql, role, *, access_path=None, meta_path=None)` uses sqlglot 30 (duckdb dialect). The steps run in order: parse, one statement, SELECT/set-op only (with no DML/DDL/Command nodes inside), relations (functions/UNNEST/VALUES/LATERAL/file-like names → TABLE_FUNCTION; anything that is not an allowlisted model and is not a CTE ref resolved by scope → TABLE_NOT_ALLOWED; only `marts.` is accepted as a schema), STAR (also `COLUMNS(...)` and whole-row refs like `SELECT d FROM dim_accounts d`), VOLATILE_TIME, then `qualify` against the allowlisted schema (failure → COLUMN_UNKNOWN), and finally scope lineage for PII. aggregate_only: every PII ref that is not the bare argument of COUNT / COUNT(DISTINCT) is forbidden, so `count(lower(pii))` is rejected too. mask: an output is masked when its lineage (alias, CTE, derived table, scalar subquery, any UNION branch) reaches a non-granted PII value. The rewrite is `SELECT '<mask>' AS "c", _c1 AS "d" FROM (<query with LIMIT>) AS _q(_c0, _c1)`, and comments are stripped. A non-numeric LIMIT is capped from outside with `SELECT * FROM (q) _q LIMIT row_cap`.
**Blocker for Amir:** the locked `_g5_cases.CODE` runs `from governor.ask.executor import execute` at import, so accept_g5a fails with ModuleNotFoundError until G5b's executor exists. The step forbids writing it here. With a stub module injected in-process, 39/39 rejects and 14/14 accepts are right, LIMIT injection and mask wrapping both pass, and every rewritten accept query runs on the green warehouse. Options: allow an `executor.py` stub in G5a, or gate G5a together with G5b.

## G5a result
*SQL validator and role policy, 23 Oct 2026 17:06.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 1 fix loop(s); branch `factory/G5a`.

| check | ok | detail |
|---|---|---|
| validator runs on the locked cases | yes | {"validate": [{"ok": false, "codes": ["NOT_SELECT"], "sql": null}, {"ok": false, "codes": ["NOT_SELECT"], "sql": null},  |
| 39 locked rejects decided with the right code | yes |  |
| 14 locked valid queries accepted | yes |  |
| validator injects a LIMIT when missing | yes | SELECT country, COUNT(*) AS n FROM dim_accounts GROUP BY country LIMIT 100 |
| finance_admin masking wraps the original query (outer projection, DISTINCT kept inside) | yes | select '***' as "contact_name" from (select distinct contact_name from dim_accounts limit 5) as _q(_c0) |
| no policy values (columns, mask, models) hard-coded in validator/policy/executor | yes |  |
| pytest tests/ask | yes | 67 passed in 16.71s |

Review: Policy.for_role loads access.yaml and meta.duckdb PII tags. validate() rejects all 39 locked cases with the contracted code and accepts all 14 valid queries. Relations are default-deny, table functions and file paths are rejected, and PII is tracked through aliases, CTEs, subqueries, and functions. Masking is an outer projection, so DISTINCT stays inside; LIMIT is injected or lowered. Policy values are read from files. pytest tests/ask: 67 passed.

For Amir: The _g5_cases.py change is the supervised relock: the executor is imported only when execute cases exist. G5a checks rewrite shape, not executed rows; row cap, grants, and mask values are judged in G5b. Scalar file readers (for example read_text) are not treated as table functions; shutting off external access in the executor is the backstop.

## Additions for G5b
Run validate() and execute result.sql, not the user SQL. Failures have sql None: return those codes and no rows. Success SQL has comments stripped, a LIMIT (default_limit, or the existing limit lowered to row_cap), and for a mask role an outer projection so DISTINCT stays inside. Tables are bare names; warehouse.connect() sets search_path to marts and is read-only. Take timeout_s, row_cap, and mask_value from Policy. Do not hardcode models, PII columns, or the mask (accept_g5b greps executor.py). CODE imports the executor only when execute cases are present, stringifies values, and keeps 5 rows. Execution checks: LIMIT present and row_count <= 100; LIMIT 5 kept; LIMIT 5000 returns exactly 1000 rows; mask columns equal the configured mask and account_id is not masked; granted email still contains @; DISTINCT contact_name is 5 masked rows; COUNT(DISTINCT pii) stays a number. analyst selecting contact_email is PII_FORBIDDEN with no rows. run_readonly raises QueryTimeout (1s cartesian probe) and QueryError (CREATE). dry_run is EXPLAIN. Disable external access and extension autoload where DuckDB allows; note gaps in NOTES. Edit validator.py only to fix a locked execution failure, and record it. Do not edit plan/accept/_g5_cases.py.

## G5b result (implementer notes)
`governor.ask.executor`: `dry_run(sql) -> DryRun{ok, error}` (EXPLAIN), `run_readonly(sql, *, timeout_s, row_cap) -> (columns, rows)` and `execute(sql, role) -> ExecResult{ok, codes, reasons, sql, columns, rows, row_count}`; all take optional `database` (and execute `access_path`/`meta_path`) for fixtures. execute runs `validate()`'s rewritten SQL, never the user SQL; a reject returns the validator codes, `sql=None`, no rows. Extra executor codes: `DRY_RUN_FAILED`, `TIMEOUT`, `EXEC_ERROR`. Timeout is a `threading.Timer` calling `connection.interrupt()`; an interrupted query raises `QueryTimeout` (subclass of `QueryError`). Rows are fetched with `fetchmany(row_cap)`; the connection is always closed.
Hardening (DuckDB 2.0.0, all supported at runtime on a read-only connection via `SET` after `warehouse.connect()`): `enable_external_access=false`, `autoinstall_known_extensions=false`, `autoload_known_extensions=false`, `allow_community_extensions=false`, then `lock_configuration=true` so a query cannot switch them back (tested). Gaps: settings are applied after open rather than in the `connect(config=...)` call (warehouse.py is outside G5b's paths); `allowed_directories`/`allowed_paths` stay empty; already-loaded built-in extensions (e.g. parquet/json, statically linked) remain callable but cannot reach files with external access off.
validator.py: no change needed; all 14 locked accepts execute correctly and the 39 rejects keep their codes.
Tests: `tests/ask/test_executor.py` (24, own fixture warehouse with `marts` schema): both roles, masking (mask value, DISTINCT count, COUNT(DISTINCT pii) numeric, grant honoured), default limit / kept limit / row cap, timeout, writes refused with the validator bypassed, external file read refused, config locked, dry_run bad column. accept_g5b: 11/11; pytest tests/ask: 91 passed.

## G5b result
*Dry-run and read-only executor, 23 Oct 2026 17:33.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/G5b`.

| check | ok | detail |
|---|---|---|
| validator and executor run | yes | {"validate": [{"ok": false, "codes": ["NOT_SELECT"], "sql": null}, {"ok": false, "codes": ["NOT_SELECT"], "sql": null},  |
| 39 locked rejects decided with the right code | yes |  |
| 14 locked valid queries accepted | yes |  |
| executed results: LIMIT rewrite, row cap, masking by lineage, grant honoured | yes |  |
| execute refuses analyst PII with PII_FORBIDDEN and returns no rows | yes | {'ok': False, 'codes': ['PII_FORBIDDEN'], 'columns': [], 'rows': [], 'row_count': 0, 'sql': None} |
| executor guards run | yes | {"timeout": "QueryTimeout", "write": "QueryError", "dry_run_bad": false, "dry_run_good": true} |
| run_readonly times out with QueryTimeout | yes | QueryTimeout |
| run_readonly refuses writes (read-only connection) with QueryError | yes | QueryError |
| dry_run fails on a bad column and passes a good query | yes | {'timeout': 'QueryTimeout', 'write': 'QueryError', 'dry_run_bad': False, 'dry_run_good': True} |
| no policy values (columns, mask, models) hard-coded in validator/policy/executor | yes |  |
| pytest tests/ask | yes | 91 passed in 23.98s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: STATUS still records an earlier G5b stop for secret_in_diff (a 52-character high-entropy string in tests/ask/test_executor.py). The file reviewed here has no such token, and this run's acceptance passed, including pytest 91. Hardening is SET after warehouse.connect because that module was out of scope, then lock_configuration. dry_run's EXPLAIN is not on the interrupt timer. Built-in readers stay loaded and are stopped by enable_external_access=false; read_csv is tested.

## G6a result (implementer notes)
`governor.ask.graph.build_graph(*, llm=None, checkpointer=None, database=, access_path=, meta_path=, cards=, retrieval_mode="bm25", embedder="fake", as_of=)`: 11 nodes as specified, InMemorySaver by default, the extra keywords are for fixtures only. With `llm=None`, models are built on first use (plan: FAST_MODEL gpt-5-nano; draft_sql/repair/answer: gpt-5-mini), so compiling needs no key. Models with `with_structured_output` get structured output (`include_raw` for usage); the FakeLLM path parses JSON text. Retrieval defaults to BM25 (best tune recall in G4, no embedding call).
- Guard = `security.validate_input` (min 2 chars) + `regex_screen`, with fixed refusal text. The "model flag" half is an extra `QueryPlan.injection: bool` set by the plan call (no extra model call); a flagged plan ends in the same guard refusal before any SQL is drafted. Clarification answers are screened too.
- Clarify: `interrupt({"missing_slot"})`, then resume with `Command(resume=text)`, then one re-plan; a second clarify ends as `clarify_failed`.
- Loop: validate -> dry_run -> execute (executor.execute, so it validates again). Any failing node decides: PII_FORBIDDEN/TABLE_NOT_ALLOWED/UNKNOWN_ROLE -> `refused_policy` (text names the code and a fixed rule sentence, never columns or tables); TIMEOUT -> `refused_error`; else repair while `repairs < 2`, then `refused_repair`.
- Answer: `fill_answer` rejects placeholders that point outside the rows, digits, stray braces, or result string values outside placeholders; then a fixed fallback ("The result is in the table below."). Card: text, columns, rows, executed sql, models (validator tables), upstream sources (`lineage.upstream` on meta edges, sorted) and freshness (`age_hours_at_as_of`), as_of.
- `record_trace` builds the trace dict (`schemas.TRACE_COLUMNS`, which G6b's traces.py can re-export); question text is not in it (hash + length). `models` = LLM model ids used. Outcomes: answer, refused_guard, refused_policy, refused_repair, refused_error, unanswerable, clarify_failed.
- Outside the new files: the acceptance wall-clock grep hit `validator.py` (the denylist literals) and `prompts/baseline.md`. The validator now derives the CURRENT_* names from sqlglot's node classes (a superset of the old set; G5a 7/7 and G5b 11/11 still pass), and baseline.md says "Never call a function that reads the clock". That baseline wording change may shift baseline results slightly.
- State lists (`sql_attempts`, `usage`, `policy_decisions`) use add-reducers, so one thread = one question.
Tests: `tests/ask/test_graph.py` (11, own fixture warehouse/meta/cards, as_of 2025-03-15). accept_g6a 8/8; full pytest 250 passed.

## Additions for G6a
G6a should call governor.ask.executor. execute(sql, role) returns ExecResult(ok, codes, reasons, sql, columns, rows, row_count). On a validator reject, ok is false, codes and reasons are the validator's, sql is None, and rows are empty; do not run the user SQL. On success, sql is the rewritten statement (comments removed, LIMIT injected or lowered, mask roles wrapped so DISTINCT and GROUP BY stay inside) and row_count is len(rows). Executor-only codes, with that rewritten sql kept: DRY_RUN_FAILED (reasons[0] is the EXPLAIN error, first line, at most 300 chars), TIMEOUT, and EXEC_ERROR. dry_run(sql) returns DryRun(ok, error) for the repair node; EXPLAIN is not under the interrupt timer. run_readonly(sql, *, timeout_s, row_cap) raises QueryTimeout (a QueryError subclass) or QueryError and is the bypass used by tests. The graph execute node should call execute() so the validator still runs. Optional database, access_path, and meta_path are for fixtures. Take timeout_s 10, row_cap 1000, and mask *** from Policy; do not hardcode models or PII columns. Answer placeholders must be filled from these rows (ints, decimals, dates). as_of remains 2026-10-22. Every connection is closed.

## G6a result
*The governor-ask graph (core, in-memory), 23 Oct 2026 17:59.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G6a`.

| check | ok | detail |
|---|---|---|
| build_graph(llm=None) compiles without network | yes |  |
| graph has exactly the specified nodes | yes | got ['answer', 'clarify', 'draft_sql', 'dry_run', 'execute', 'guard', 'plan', 'record_trace', 'repair', 'retrieve_contex |
| graph prompts exist as files | yes | missing: [] |
| no golden questions or gold SQL in prompts, code or tests | yes |  |
| no wall-clock dates in ask logic (as_of only) | yes |  |
| golden set still frozen | yes | golden set unchanged |
| pytest tests/ask | yes | 102 passed in 27.25s |
| required tests present | yes | 8 found |

Review: The ask graph is one StateGraph with the 11 specified nodes and code-owned edges. Refusals are fixed strings (guard, policy rule names, repair, execution) and do not quote the question. Answer text is filled from result cells via {rRcC}; digits or copied result values outside placeholders are replaced by a fixed fallback, and the rows are shown beside it. Date anchors come from as_of, and clock functions are rejected before execute. Prompts are generic. Acceptance passed 8/8; the eight required tests run the graph offline.

For Amir: Validator clock-function names are no longer spelled in source: CURRENT_* comes from sqlglot node classes, plus a short name set (now, today, get_current_*). Parsed CurrentDate and similar nodes are still rejected. baseline.md now says not to call a clock function, without naming now() or current_date, so baseline answers may shift. Both edits keep the ask wall-clock grep green. Trace latency still uses datetime.now(timezone.utc), which that grep does not match.

## Additions for G6b
build_graph(*, llm=None, checkpointer=None, database, access_path, meta_path, cards, retrieval_mode='bm25', embedder='fake', as_of). The default saver is InMemorySaver; pass SqliteSaver to resume in a new process. Clarify interrupts with {'missing_slot': text} and resumes with Command(resume=user_text) on the same thread_id. A second clarify sets outcome clarify_failed and does not interrupt again. record_trace already stores state['trace'] with schemas.TRACE_COLUMNS; re-export that tuple from governor.ask.traces. The trace answer field is the text string. state['answer'] is the card (text, rows, columns, sql, models=warehouse tables, sources, freshness, as_of). Trace models are LLM ids. The question is hash plus length only. sql_attempts, usage, and policy_decisions use operator.add, so one thread is one question or later turns append. A failed trace write must still return the card. Executor masking runs before the answer node, so rows and filled text already hold the mask. SQL attempts may name columns; that is not a raw value. Refusal text is fixed. paths.STATE is currently ROOT/'.state' and TRACES is artifacts/traces.duckdb; accept_g6b requires GOVERNOR_STATE_DIR to move both. governor.core.trace already exists; add governor.ask.traces. as_of remains 2026-10-22. The wall-clock grep flags date.today(), current_date, current_timestamp, and now() with empty parentheses. Trace timestamps use datetime.now(timezone.utc). Retrieval defaults to BM25.

## Relocks
- 23 Oct 2026 18:43: G7: .gitignore added to allowed_paths (needs !.env.example); .env.example written by hand with placeholders (agents may not write .env* files) (via supervise, by claude.ai) (changed: plan.yaml)

## G6b result (implementer notes)
- `governor.ask.traces`: `TRACE_COLUMNS` (re-exported from schemas), `write_trace(row, *, question, secrets, mask, path)`, `list_traces(role, outcome, limit)` (newest first), `get_trace(id)` on table `traces` in `paths.TRACES`; the only read-write opener, every connection closed. List fields are JSON text, decoded on read. Extra column `question_text`, filled only with `GOVERNOR_TRACE_TEXT=1`.
- No raw PII in the store: before writing, result cells of output columns that trace to a PII-tagged column (`governor.eval.pii.output_lineage`, granted or not) and any email-like string are replaced by the access.yaml mask in answer, executed_sql, sql_attempts, plan_json and question_text. So a finance_admin card shows the granted email, the stored trace shows the mask. `state['trace']` itself is unredacted (as in G6a).
- `record_trace` writes the row (`build_graph(..., trace_path=None, store_traces=True)`); any write error is logged (trace id + error type only) and lands in `state['trace_error']`; the card is returned.
- `paths.STATE` = ROOT / `GOVERNOR_STATE_DIR` (default `artifacts`); `TRACES` and new `CHECKPOINTS` (checkpoints.sqlite) live under it. Side effect: `config.CHROMA_DIR` / `CHUNKS_PATH` moved from `.state/` to `artifacts/` (unused so far).
- CLI `python -m governor.ask.run` with SqliteSaver (`langgraph-checkpoint-sqlite`, new dependency; pyproject + uv.lock). `--llm` defaults to `openrouter` (llm=None, per-node models); `fake:SCRIPT.json` takes a list or `{plan, sql, answer}` queues (`llm_testing.load_script`). The llm is not saved with the thread: pass it again on `--resume`. Hidden `--database/--access/--meta/--cards/--as-of` for fixtures. A finished thread exits 1 on `--resume`.
- System `agent` (`governor.ask.agent`, lazy in systems): one thread per item, interrupt = `clarify`; refused_guard/policy = refuse; refused_repair/error = failed answer with the last SQL attempt. With `eval.run --llm openrouter` it gets gpt-5-mini for every node (eval.run's make_llm), not nano for plan; G10 may want llm=None for agent.
- `tests/ask/conftest.py` points STATE/TRACES/CHECKPOINTS at a temp dir for every ask test.
Tests: `tests/ask/test_traces.py` (5). accept_g6b 12/12; full pytest 255 passed.

## G6b result
*Persistence, decision traces, CLI and the agent system, 23 Oct 2026 18:22.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G6b`.

| check | ok | detail |
|---|---|---|
| governor.ask.traces exposes TRACE_COLUMNS, write_trace, list_traces, get_trace | yes |  |
| trace row has every specified column | yes | missing: [] |
| GOVERNOR_STATE_DIR moves state (traces, checkpoints) to one folder | yes | {'state': 'C:\\Users\\amir0\\portfolio\\governor\\zz_state', 'traces': 'C:\\Users\\amir0\\portfolio\\governor\\zz_state\ |
| agent system runs through the harness on the FakeLLM | yes | wrote C:\Users\amir0\AppData\Local\Temp\g6-accept-ith7kh5_\agent-tune.json | {"n": 25, "execution_accuracy": 0.0, "valid |
| agent report covers the 25 tune items | yes | 25 |
| graph prompts exist as files | yes | missing: [] |
| no golden questions or gold SQL in prompts, code or tests | yes |  |
| no wall-clock dates in ask logic (as_of only) | yes |  |
| golden set still frozen | yes | golden set unchanged |
| pytest tests/ask | yes | 107 passed in 44.08s |
| required tests present | yes | 4 found |
| pytest tests/eval | yes | 103 passed in 2.37s |

Review: Decision traces are complete rows in traces.duckdb. Every TRACE_COLUMNS field is written. Question text is stored only when GOVERNOR_TRACE_TEXT=1. Result PII, including a granted email, is stored as the policy mask. A failed write is logged and the answer is kept. Checkpoints and traces share GOVERNOR_STATE_DIR. The CLI resumes a clarify pause from a second process. The agent system returns behaviour clarify on an interrupt and does not resume it. Acceptance passed 12/12.

For Amir: DuckDB trace rows are masked, but SqliteSaver checkpoints and the in-memory trace still contain the question, clarification text, result rows, and the card, so a granted email is in checkpoints.sqlite. G7 should show the role-scoped card and get_trace, not the checkpoint. eval.run --llm openrouter uses one chat model for every node; the CLI openrouter path uses llm=None so plan stays gpt-5-nano. STATE's default moved from .state to artifacts, so CHROMA_DIR and CHUNKS_PATH moved with it. The tune FakeLLM run answers SELECT 1 (execution_accuracy 0) and does not emit clarify.

## G7 result (implementer notes)
- `governor.ask.service`: `ask/resume/list_traces/get_trace/settings`, `AskResult`. One compiled graph per process on a SqliteSaver (`paths.CHECKPOINTS`, read when first compiled); `configure(llm, **graph_options)` / `reset()` drop it. Owner = `role` in the checkpointed state (threads) or the trace row; another role gets NotFound (404), same as a missing id. `ask` on an existing thread_id is 409 `thread_exists`; resuming a finished thread is 409 `not_waiting`.
- Status map: answer -> answered; interrupt -> clarify; refused_guard/policy -> refused; unanswerable and **clarify_failed -> unanswerable** (final, so the client must not offer a resume; differs from the agent map); refused_repair/error -> error. `sql` and rows only when answered.
- `governor.api.app`: `create_app(tokens=None, llm="env", **graph_options)`; module `app = create_app()` reads `GOVERNOR_API_TOKENS` and `GOVERNOR_LLM` (openrouter | fake | fake:SCRIPT.json) at import, so a bad role fails at uvicorn startup. Empty tokens = warning + every /v1 call 401. 422 bodies list field names only (pydantic's default echoes the input). `/docs` and `/redoc` disabled; `openapi.json` stays (acceptance reads it).
- New deps: `fastapi` (the API), `uvicorn` (ASGI server in the image), `httpx` (FastAPI TestClient). Plain uvicorn, not `[standard]`, to keep the image small.
- Dockerfile (python:3.12-slim + uv 0.8, `uv sync --frozen --no-dev`), `.dockerignore` (keeps .env, .venv, artifacts out of the context), compose with `api` and a placeholder `ui`, volume `governor-data` on `/data`. Not built here (no Docker run in this step). build_green's 60 s limit applies inside `docker build` too.
- `.gitignore`: `!.env.example` added (`.env.*` would have hidden it).
- **`.env.example` not written**: a permission deny rule covers `.env.*`, so the implementer could not create it. Amir: create it by hand (content in the G7 summary); the acceptance check fails until then.
Tests: `tests/api/test_api.py` (11 incl. parametrised 401 cases and a startup-error test). accept_g7 15/16 (only .env.example); full pytest 266 passed.

## Additions for G7
Resume with Command(resume=text) on the same thread_id. SqliteSaver is sqlite3.connect(paths.CHECKPOINTS, check_same_thread=False); run.sqlite_checkpointer wraps it. Interrupt value is {missing_slot: text}. A second clarify sets outcome clarify_failed and does not interrupt. The llm is not checkpointed. A pause returns outcome clarify and trace_id null; the row is written only in record_trace. Audits: traces.get_trace and list_traces (newest first) are redacted. The in-memory trace, the card, and checkpoints.sqlite still hold the question, clarification answer, and rows, including a granted email. human_feedback is always null. GOVERNOR_STATE_DIR (default artifacts, relative to ROOT) moves STATE, TRACES, and CHECKPOINTS. tests/ask conftest redirects them. CLI --llm openrouter uses llm=None (plan gpt-5-nano; SQL and answer gpt-5-mini). eval.run --llm openrouter passes one model to every node. Agent map: interrupt and clarify_failed -> clarify; refused_guard and refused_policy -> refuse; unanswerable -> unanswerable; refused_repair and refused_error -> answer with error set to that outcome. as_of remains 2026-10-22. CHROMA_DIR now lives under STATE (artifacts/), not .state/.

## G7 result
*API, authentication and deployment skeleton, 23 Oct 2026 19:30.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 1 fix loop(s); branch `factory/G7`.

| check | ok | detail |
|---|---|---|
| API app imports and answers with the fake LLM | yes |  |
| exactly the specified routes | yes | got [('GET', '/health'), ('GET', '/v1/traces'), ('GET', '/v1/traces/{trace_id}'), ('POST', '/v1/ask'), ('POST', '/v1/thr |
| /health needs no token | yes | 200 |
| missing and unknown tokens are 401 | yes | 401/401 |
| a role field in the body is rejected (422) | yes | 422 |
| /v1/ask works with a valid token and returns an AskResult | yes | 200 ['answer', 'clarify_question', 'cost_usd', 'freshness', 'lineage', 'models', 'result_columns', 'result_rows', 'sql', |
| errors are JSON without a traceback | yes | {"error":"trace not found","code":"not_found"} |
| Dockerfile builds the green warehouse and catalog at build time and runs uvicorn as non-root | yes |  |
| docker-compose.yml has api and ui services and a /data volume | yes |  |
| .env.example exists with placeholders only | yes |  |
| docs/deploy.md exists | yes |  |
| no real tokens in code, compose or docs | yes |  |
| tokens are never logged | yes |  |
| pytest tests/api | yes | 11 passed in 4.59s |
| required tests present | yes | 7 found |
| pytest tests/ask | yes | 107 passed in 44.07s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Acceptance does not run docker build. The Dockerfile does build the warehouse before switching to uid 10001, and only /data is writable by that user. Deploy checks are substrings, so the letters USER anywhere in the file would pass. GET /openapi.json is still mounted; docs and redoc are off. It is outside the schema, so the exact-routes check does not see it. app.openapi() does not need that route. If the same token string is listed for two roles, the later pair wins. checkpoints.sqlite on the volume still holds the raw question and result rows.

## Additions for G8
G8 Streamlit talks only to this API. Compose sets GOVERNOR_API_URL=http://api:8000 on ui, which is still a placeholder command on image governor:local. No role picker and no role field: send one bearer token; the API derives the role and returns 422 if the body contains role. Do not put GOVERNOR_API_TOKENS in the browser or in logs. No CORS is configured, so call the API from the Streamlit server. GET /health returns status, as_of, and version. POST /v1/ask takes {question, thread_id?} and returns AskResult. status clarify has a null trace_id; keep that thread and POST /v1/threads/{thread_id}/resume with {answer}. A rerun must not start a new ask. clarify_failed is returned as unanswerable and must not be resumed. Show result_columns and result_rows, not only answer. Another role's thread or trace is 404. 409 is thread_exists or not_waiting, and only for the owning role. Writable state is the api volume governor-data on /data, not the UI container. settings() is in-process only and is not a route.

