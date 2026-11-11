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

## G8 result (implementer notes)
- `apps/streamlit/`: `client.py` (`ApiClient` over httpx; `GOVERNOR_API_URL=asgi` runs the API in-process via `httpx.ASGITransport` + `asyncio.run`, looking up `governor.api.app.app` per request), `ui_common.py` (sidebar token box: password field copied into `session_state["api_token"]` so it survives page switches; login hint), `app.py` (landing: what it is, `/health` status/as_of/version), pages Ask, Trace explorer, Developer.
- Ask: API called only on form submit, so reruns never re-ask. `thread_id` + `clarify_question` in session state while a clarify is pending; reply box calls `resume`; 404/409 on resume clears the pending thread and shows the error. Answer card: text, `result_columns`/`result_rows` table, SQL expander, models, upstream sources, freshness expander, cost badge; refusals as an error box; unanswerable/error as warnings (no resume offered).
- Trace explorer: outcome filter (fixed list of graph outcomes), list table, detail (plan JSON, SQL attempts with validator codes, executed SQL, policy decisions).
- Developer: API URL, `/health` JSON. No settings route exists (and `src/governor/api` is outside G8 paths), so "models" = LLM model ids from the caller's recent traces. access.yaml read from the repo copy and shown as text.
- Compose `ui`: `streamlit run apps/streamlit/app.py` on 8501, own healthcheck (`/_stcore/health`; the image's HEALTHCHECK targets 8000), waits for api healthy, **no `env_file`** (the UI needs no secrets; GOVERNOR_API_TOKENS stays out of the UI container). Not built or run here.
- New dep: `streamlit` (UI; 1.66.1). Added by editing pyproject; `uv run` re-locked.
- Open: `docs/deploy.md` still calls the ui a placeholder (outside G8 paths). Streamlit runs as uid 10001 with HOME=/nonexistent in the image; untested in Docker.
Tests: `tests/ui/test_pages.py` (5, AppTest, asgi, scripted FakeLLM); accept_g8 11/11; full pytest 271 passed.

## G8 result
*Streamlit as a thin client over the API, 23 Oct 2026 19:47.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G8`.

| check | ok | detail |
|---|---|---|
| app and the three pages exist | yes | missing: [] |
| UI has no DB, SQL, policy or governor.ask imports | yes |  |
| only client.py touches governor.api (asgi mode) | yes |  |
| no role picker in the UI (role comes from the token) | yes |  |
| no golden questions in the UI or its tests | yes |  |
| apps/streamlit/client.py importable | yes |  |
| ApiClient exposes ask/resume/list_traces/get_trace/health | yes | missing: [] |
| compose ui service points at the api service | yes |  |
| pytest tests/ui | yes | 5 passed in 8.90s |
| required tests present | yes | 5 found |
| pytest tests/api | yes | 11 passed in 4.05s |

Review: Pages talk only to ApiClient. governor.api is imported only for GOVERNOR_API_URL=asgi. No role picker: the token is sent as a bearer header. Ask stores thread_id while a clarification is pending, so a rerun does not ask again, and the reply box calls resume. Answered results render result_rows as a dataframe plus SQL, models, lineage, freshness, and cost. Refusals are shown as refusals. Trace outcomes match the graph literal. AppTests run these paths on the real API. Compose points ui at http://api:8000 and does not pass tokens.

For Amir: Acceptance does not start the ui container. Streamlit 1.66 with --server.headless and --browser.gatherUsageStats=false does not create ~/.streamlit on boot, so HOME=/nonexistent should not stop startup; a later streamlit_write would still need a writable home. docs/deploy.md still calls ui a placeholder and is outside G8 paths. The role-picker grep is case-sensitive and would miss a widget labeled Role; this UI has no role widget. Refusal rendering is implemented and untested.

## Additions for G9
G9 is MCP on stdio, separate from the Streamlit client. Do not import apps/streamlit. Shared read-only logic stays in governor.ask.service; the UI already uses that service only through HTTP. Role is never a tool or body field: HTTP derives it from the bearer token and returns 422 if the body contains role. MCP must take the role from GOVERNOR_MCP_ROLE (default analyst, must exist in access.yaml) and must not let the client raise it. settings() is in-process only and is not a route. AskResult clarify carries thread_id and a null trace_id; resume is POST /v1/threads/{id}/resume with {answer}. clarify_failed is returned as unanswerable and must not be resumed. sql and rows are present only when status is answered. Traces are scoped to the role. No write path. Tool text must not restate access.yaml. as_of remains 2026-10-22. Do not read evaluation/golden.

## G9 result (implementer notes)
- `src/governor/ask/mcp_server.py` (`python -m governor.ask.mcp_server`, stdio): 5 read-only tools (`search_catalog`, `describe_model`, `get_lineage`, `validate_sql`, `run_governed_query`), all annotated readOnlyHint. Role from `GOVERNOR_MCP_ROLE` (default analyst), checked against access.yaml at start-up (exit 2 otherwise); no tool has a role argument.
- Logic in `governor.ask.service`: `search_catalog` (BM25, offline; k capped at 20), `describe_model`/`get_lineage` (from meta.duckdb, only models the role's policy can query; staging models give `{error}`), `validate_sql` (validator), `run_query` (executor.execute; rows made JSON-safe with pydantic_core). Lineage depth capped at 3; result includes the applied `depth`.
- SDK: **mcp 1.30.0**, pinned `mcp>=1.10,<2`. 2.3.0 was installed first: it renames `FastMCP` to `MCPServer` and `Tool.inputSchema` to `input_schema`, and the locked accept_g9 client reads `inputSchema`, so 2.x fails acceptance. Revisit the pin when the plan moves to 2.x.
- `describe_model` reuses `catalog._grain` (private helper) so the grain matches the cards.
- `StdioServerParameters` without `env` passes only a minimal environment, so `GOVERNOR_MCP_ROLE` must go in the client's `env` (docs/mcp.md shows it).
- Open: dates in rows arrive as ISO strings, Decimals as strings (pydantic default).
Tests: `tests/mcp/test_mcp_server.py` (4, real stdio server + SDK client).

## G9 result
*MCP server with 5 read-only tools (stretch: cut first if late), 23 Oct 2026 19:58.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G9`.

| check | ok | detail |
|---|---|---|
| MCP server answers the SDK stdio client | yes | Processing request of type CallToolRequest | Processing request of type ListToolsRequest | Processing request of type Ca |
| exactly the 5 specified tools | yes | ['describe_model', 'get_lineage', 'run_governed_query', 'search_catalog', 'validate_sql'] |
| search_catalog finds mrr_monthly | yes | {'hits': [{'card_id': 'metric:arr', 'kind': 'metric', 'name': 'arr', 'tables': ['mrr_monthly'], 'score': 3.449297}, {'ca |
| describe_model shows PII tags | yes | {'account_id': None, 'company_name': None, 'contact_email': 'email', 'contact_name': 'name', 'country': None, 'created_a |
| describe_model on an unknown name returns an error, not a crash | yes | {'error': "unknown model 'no_such_model'"} |
| get_lineage returns upstream nodes (depth capped) | yes | {'name': 'mrr_monthly', 'direction': 'upstream', 'depth': 3, 'nodes': [{'unique_id': 'source.billing_mart.billing.plans' |
| validate_sql rejects DROP | yes | {'ok': False, 'codes': ['NOT_SELECT'], 'reasons': ['Drop statement; only SELECT or WITH ... SELECT is allowed'], 'sql':  |
| run_governed_query returns rows for a valid query | yes | {'ok': True, 'codes': [], 'reasons': [], 'columns': ['country', 'n'], 'rows': [['Aserbaidschan', 5], ['Südgeorgien und d |
| run_governed_query refuses analyst PII by default | yes | {'ok': False, 'codes': ['PII_FORBIDDEN'], 'reasons': ["PII column dim_accounts.contact_email used outside COUNT(...) for |
| run_governed_query cannot write | yes | {'ok': False, 'codes': ['NOT_SELECT'], 'reasons': ['Delete statement; only SELECT or WITH ... SELECT is allowed'], 'colu |
| no tool takes a role argument (role is fixed by GOVERNOR_MCP_ROLE) | yes | [] |
| docs/mcp.md has the run command and all tool names | yes |  |
| pytest tests/mcp | yes | 4 passed in 16.87s |

Review: G9 matches the prompt. FastMCP stdio server exposes the five read-only tools as a wrapper over governor.ask.service. Role comes only from GOVERNOR_MCP_ROLE. validate_sql and run_governed_query call validator.validate and executor.execute (read-only warehouse). describe_model and get_lineage use Policy.for_role and a read-only meta store; lineage depth caps at 3. Descriptions do not restate access.yaml. Live SDK output matches the warehouse and validator codes.

For Amir: accept_g9's write check only requires ok false. Writes still cannot land: run_governed_query calls executor.execute, which validates and opens the warehouse read-only. The lineage check only requires a non-empty node list; the recorded payload has depth 3 after a request for 9, and tests/mcp asserts the cap when depth is 50. Models outside the allowlist use the same error shape as a missing name. mcp stays below 2 because accept_g9 reads Tool.inputSchema.

## G10a result (implementer notes)
Tune runs (`ts system execution_accuracy valid_sql_final clarify_p/r policy_compliance pii_leak cost`):
- 2026-10-23T18:02Z baseline 0.556 0.955 -/0.00 0.333 true $0.036
- 2026-10-23T18:11Z agent 0.389 1.000 0.50/0.67 0.333 false $0.108
- 2026-10-23T18:23Z agent 0.556 1.000 0.67/0.67 0.667 false $0.118
- 2026-10-23T18:31Z agent 0.778 1.000 0.67/0.67 0.667 false $0.109
- 2026-10-23T18:39Z agent 0.778 1.000 0.67/0.67 1.000 false $0.097 (frozen)
- Changed prompts only (draft_sql, plan, repair): exact output columns, metric shape by grain, bare COUNT on a counted column, no queries on upstream sources, a stricter clarify bar. Details are in `evaluation/reports/TUNING.md`; hashes are in `PROMPTS_FROZEN.sha256`.
- Open: the plan's intent on join items (gpt-5-nano) moves between answer, clarify and unanswerable from run to run. A stronger plan model is a candidate, but it is not in G10a scope.

## Additions for G10a
G10a tunes ask prompts. The MCP server is not on the graph path: do not import mcp_server into the graph and do not add an NL-to-SQL tool. Role stays out of tool arguments and request bodies. mcp is pinned to >=1.10,<2 (installed 1.30.0); 2.x renames FastMCP and Tool.inputSchema, which the locked accept_g9 client reads. service now has search_catalog (BM25, k capped at 20), describe_model, get_lineage (depth capped at 3), validate_sql, and run_query. Query rows are JSON-safe (dates and decimals as strings). Tool text must not restate access.yaml. as_of remains 2026-10-22. Do not read evaluation/golden. No holdout run in G10a.

## G10a result
*Tune on the tune split, then freeze the prompts, 23 Oct 2026 20:50.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G10a`.

| check | ok | detail |
|---|---|---|
| baseline-tune.json exists | yes |  |
| baseline-tune.json covers exactly the tune split | yes |  |
| baseline-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| agent-tune.json exists | yes |  |
| agent-tune.json covers exactly the tune split | yes |  |
| agent-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| agent made real model calls (cost > 0) | yes |  |
| tune cost within the $2 step budget | yes | $0.133 |
| PROMPTS_FROZEN.sha256 exists | yes |  |
| frozen hashes match the current prompts | yes | ['answer.md', 'baseline.md', 'draft_sql.md', 'plan.md', 'repair.md'] vs ['answer.md', 'baseline.md', 'draft_sql.md', 'pl |
| no golden text in prompts | yes |  |
| no holdout run yet (that is G10b) | yes | 0 log lines |
| TUNING.md records the changes and before/after numbers | yes | 33 lines |
| golden set still frozen | yes | golden set unchanged |
| pytest tests | yes | 275 passed in 71.50s (0:01:11) |

Review: G10a froze draft_sql, plan, and repair after tune-split runs. Saved baseline and final agent summaries match TUNING.md and NOTES: execution accuracy 0.556 to 0.778, policy 0.333 to 1.0, clarify 0.67/0.67, no agent PII leak. Prompt edits follow checker failures and catalog grain labels. No holdout file or log. Five tune misses remain; four are plan intent on gpt-5-nano.

For Amir: Acceptance checks that TUNING.md has at least 8 lines, not that its numbers match the JSON. Run 0 and run 4 match the two saved reports. Runs 1-3 are recorded only in NOTES and TUNING.md. The COUNT paragraph says policy moved from 0.33 to 1.0; the table shows 0.333, 0.667, 0.667, then 1.0. Baseline still answers j03 and j06, which the frozen agent marks unanswerable.

## Relocks
- 02 Nov 2026 16:18: capstone batch 1, design agreed 2 Nov (changed: plan.yaml, plan/accept/_testbed.py, plan/accept/accept_c1.py, plan/accept/accept_c2.py, plan/accept/accept_c3.py, plan/accept/accept_c4.py, plan/accept/accept_c5.py, plan/accept/accept_c6.py, plan/prompts/C1.md, plan/prompts/C2.md, plan/prompts/C3.md, plan/prompts/C4.md, plan/prompts/C5.md, plan/prompts/C6.md)
- 02 Nov 2026 21:14: C1: checkpoints.py added to allowed_paths; stray acc_c1.log removed (changed: plan.yaml)
- 02 Nov 2026 21:52: C1: fixture/build_green.py allowed (dbt lookup broke the Linux image build) (changed: plan.yaml)

## C1 result
*Close the four G-phase follow-ups (checkpoint privacy, OpenAPI, dry-run timeout, Docker check), 02 Nov 2026 22:06.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 2 fix loop(s); branch `factory/C1`.

| check | ok | detail |
|---|---|---|
| CLI runs with the fake LLM | yes | SELECT 1 LIMIT 100 | As of: 2026-10-22T14:11:26+00:00 | {"outcome": "answer", "trace_id": "d63dd9ea-861a-4687-80c9-20970 |
| state files written | yes | 2 files |
| no stored file still contains the question text after the run | yes |  |
| app starts | yes |  |
| /openapi.json is 404 by default | yes | {'openapi': 404, 'health': 200} |
| /health still answers | yes | {'openapi': 404, 'health': 200} |
| app starts with GOVERNOR_API_DOCS=1 | yes |  |
| /openapi.json is served when GOVERNOR_API_DOCS=1 | yes | {'openapi': 200, 'health': 200} |
| executor imports | yes |  |
| dry_run takes timeout_s | yes | {'p': True} |
| Docker is running | yes | 29.9.2 |
| docker build succeeds | yes | sha256:2f8e10a7d87cee832e1ab95557515162ec35a6b795725b1f23edaeca1ee99259 |
| container runs as a non-root user | yes | uid '10001' 10001 |
| pytest tests | yes | 288 passed in 81.47s (0:01:21) |
| required tests present | yes | 4 found |

Review: Finished checkpoints are removed from the SQLite file via SqliteSaver.delete_thread, PRAGMA secure_delete, and a WAL truncate, not only hidden from queries. Clarify threads still resume and are pruned after GOVERNOR_THREAD_TTL_H at the next ask. OpenAPI is 404 unless GOVERNOR_API_DOCS=1. dry_run and run_readonly share _deadline and raise QueryTimeout; execute() passes the access.yaml timeout. Prompts and answer wording are unchanged. The image builds and runs as uid 10001.

For Amir: The dry-run acceptance check only looks for a timeout_s parameter. The interrupt behavior is covered by test_dry_run_respects_timeout, which acceptance runs. Tombstones in governor_finished_threads keep finished-thread 409s and store no question text. This review used the code and the passing acceptance output; it did not re-run pytest or Docker.

## C2 result
*Warehouse adapter seam, DuckDB first, no behaviour change, 02 Nov 2026 22:25.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/C2`.

| check | ok | detail |
|---|---|---|
| conformance suite exists | yes | missing |
| adapter contract runs | yes |  |
| DuckDB adapter named duckdb with dialect duckdb | yes | {'name': 'duckdb', 'dialect': 'duckdb', 'dry_good': True, 'dry_bad': False, 'row_cap': 7, 'json_safe': True, 'timeout':  |
| dry_run passes a good query and fails a bad column | yes | {'name': 'duckdb', 'dialect': 'duckdb', 'dry_good': True, 'dry_bad': False, 'row_cap': 7, 'json_safe': True, 'timeout':  |
| run honours row_cap | yes | 7 |
| run returns JSON-safe values | yes |  |
| timeout raises QueryTimeout | yes | QueryTimeout |
| a write raises QueryError | yes | QueryError |
| list_columns returns real columns | yes |  |
| unknown adapter name raises | yes | UnknownWarehouseError |
| executor and validator do not import duckdb | yes |  |
| validator has no hard-coded duckdb dialect | yes |  |
| locked G5b acceptance still passes | yes | 11/11 checks passed | {"step": "G5b", "pass": true, "checks": [{"name": "validator and executor run", "ok": true, "detai |
| pytest tests | yes | 300 passed, 9 skipped in 72.91s (0:01:12) |

Review: C2 moves warehouse access behind governor.core.adapters without changing validator decisions or executor results. DuckDBAdapter is the only query path in the executor (dry_run and run); the validator uses adapters.dialect() and neither file imports duckdb. Own stores stay out of the adapter. QueryTimeout and QueryError are the same objects the executor re-exports. Conformance, the green-warehouse contract, locked G5b (11/11), and pytest (300 passed) all exercise that path, so the acceptance pass is trustworthy.

For Amir: The "missing" detail on "conformance suite exists" is check()'s failure text; the file is present and ok is true. run(native=True) is an intentional deviation from design section 3 so executor cells stay Decimal and date for format_value; the default remains JSON-safe. The skipped Postgres conformance case points list_columns at information_schema, which the default listing excludes.

## G10b result (implementer notes)
- Holdout run once per system, 23 Oct 2026 (log in `evaluation/holdout_runs.log`); prompts untouched. Holdout: baseline 0.600 / agent 0.700 execution accuracy, valid SQL first 1.000 / 0.700, final 1.000 / 1.000, clarify p/r -/0.000 vs 1.000/1.000, policy 0.333 / 1.000, PII leak true / false, cost $0.028 / $0.078, p50 6.656 s / 19.305 s. Four-report total $0.239.
- Loss: agent 0/2 join and 1/2 time_grain vs baseline 1/2 and 2/2. All three agent misses (j02, j05, t06) have the right values in the wrong shape: an extra month_start on a single named-month total (the tuned metric-shape rule over-applied) and a zero-filled month spine. Human notes in `evaluation/reports/taxonomy.yaml`, read by `python -m governor.eval.report`.
- Added `governor.eval.report` (+ tests/eval/test_report.py), `evaluation/eval_report.md`, `README.md`, `docs/demo-script.md`.

## Additions for G10b
Do not edit src/governor/ask/prompts/ or rewrite evaluation/reports/PROMPTS_FROZEN.sha256. accept_g10b requires that hash file to be older than both holdout reports. Run --split holdout once for baseline and once for agent. Never pass --force-holdout. Load baseline-tune.json (execution_accuracy 0.556, valid_sql_final 0.955, clarify precision null, recall 0, policy_compliance 0.333, pii_leak true, cost_usd 0.036) and agent-tune.json (0.778, valid_sql_final 1.0, valid_sql_first 0.9375, clarify 0.667/0.667, policy 1.0, pii_leak false, cost_usd 0.097). as_of is 2026-10-22T14:11:26+00:00. Agent tune misses: j01 clarify, j03 unanswerable, j06 unanswerable, j04 answered (company_name and one unpaid amount; column count matches, values do not), a03 answer where expect is clarify. Baseline scored j03 and j06 equal, so a join loss on holdout can be plan noise on gpt-5-nano. Report a loss as a loss. The $3 check sums the four report JSONs; these two already add about $0.133. G10b's step budget is $1. Runs 1-3 are only in TUNING.md. Frozen prompt rules: catalog grain shapes, bare COUNT, query model names only, clarify only when no default reading exists.

## Relocks
- 04 Nov 2026 11:02: C5: function allowlist + 10s timeout clamp (C4 gate finding by Fable) (changed: plan.yaml, plan/accept/accept_c5.py, plan/prompts/C5.md)

## G10b result
*Holdout once, eval report, README, demo script, 23 Oct 2026 21:17.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/G10b`.

| check | ok | detail |
|---|---|---|
| report baseline-tune.json exists | yes |  |
| baseline-tune.json covers exactly the tune split | yes | 25 items |
| baseline-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report baseline-holdout.json exists | yes |  |
| baseline-holdout.json covers exactly the holdout split | yes | 15 items |
| baseline-holdout.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report agent-tune.json exists | yes |  |
| agent-tune.json covers exactly the tune split | yes | 25 items |
| agent-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report agent-holdout.json exists | yes |  |
| agent-holdout.json covers exactly the holdout split | yes | 15 items |
| agent-holdout.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| holdout run exactly once per system | yes | log: ['baseline', 'agent'] |
| PROMPTS_FROZEN.sha256 exists | yes |  |
| prompts unchanged since the freeze | yes | frozen ['answer.md', 'baseline.md', 'draft_sql.md', 'plan.md', 'repair.md'] vs now ['answer.md', 'baseline.md', 'draft_s |
| prompts frozen before both holdout runs | yes |  |
| no PII leak in agent runs | yes |  |
| total eval cost within the $3 budget | yes | $0.239 |
| evaluation/eval_report.md exists | yes |  |
| README has the required sections | yes | missing: [] |
| README has a Mermaid diagram and points to PROVENANCE.md | yes |  |
| README shows the holdout execution accuracy exactly as in the reports | yes | missing [] |
| demo script exists | yes |  |
| no golden text in prompts | yes |  |
| golden set still frozen | yes | golden set unchanged |
| pytest tests | yes | 281 passed in 73.75s (0:01:13) |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Acceptance checks that eval_report.md and the demo script exist, not that the prose matches the JSON. Summary and per-category counts match all four reports, and the three agent failure notes match the stored SQL. The rule classifier never labels wrong join; j05's country subquery is only in the note, and the scored miss is an extra month_start column.

## Additions for the next plan
Do not rerun holdout or edit src/governor/ask/prompts/. PROMPTS_FROZEN.sha256 is the freeze, and evaluation/holdout_runs.log already has one baseline line and one agent line. Headline holdout: execution accuracy 0.600 baseline vs 0.700 agent; policy 0.333 vs 1.000; PII leak true vs false; agent loses join 0/2 vs 1/2 and time_grain 1/2 vs 2/2. Four-run cost $0.239. evaluation/eval_report.md is generated by python -m governor.eval.report. taxonomy.yaml overrides j02, j05, and t06. The rule classifier has no wrong-join branch.

## Additions for C2
C2 is a pure refactor of the warehouse path. Keep executor results: dry_run(sql, *, timeout_s, database) and run_readonly both use _deadline and raise QueryTimeout; execute() passes Policy.timeout_s and maps QueryTimeout to code TIMEOUT. The graph dry_run node does the same and refuses with the existing warehouse-limits text. Do not send checkpoints, traces, or meta through the adapter (design section 3). Privacy stays in governor.ask.checkpoints: SqliteSaver.delete_thread, PRAGMA secure_delete=ON, PRAGMA wal_checkpoint(TRUNCATE), and question-free tombstones in governor_finished_threads so a finished id is still 409. Clarify threads stay until resume; prune_stale runs at the start of a new ask in the API and the CLI (GOVERNOR_THREAD_TTL_H, default 24, wall clock). GOVERNOR_TRACE_TEXT=1 keeps finished checkpoints. Prompts were not edited. fixture/build_green.py resolves dbt.exe or dbt next to sys.executable so the Linux image builds. as_of remains 2026-10-22T14:11:26+00:00.

## Additions for C3
Next step is C3 (Postgres test bed), not the adapter. get_adapter("postgres") raises UnknownWarehouseError until C4; GOVERNOR_WAREHOUSE defaults to duckdb. Do not send meta.duckdb, traces.duckdb, or checkpoints through the adapter. Keep dry_run's timeout_s optional: if omitted it uses access.yaml limits.timeout_s, because locked G5b calls dry_run(sql) with no timeout. Keep executor._open; tests stub it, and the duckdb branch passes connect=lambda: _open(database) into DuckDBAdapter. Adapter run defaults to JSON-safe lists (native=False). The executor passes native=True and converts rows to tuples so Decimal and date still reach graph.format_value and the eval checker; C4 must implement native. The conformance Postgres case skips when GOVERNOR_PG_DSN is unset. Its known_column is information_schema.tables.table_name, but list_columns() drops information_schema and pg_catalog, so point that case at a real test-bed table before C4 stops skipping. as_of remains 2026-10-22T14:11:26+00:00. Connection settings come from env only. Test-bed host port is 55432, database shop.

## Relocks
- 04 Nov 2026 12:43: C6: KPI owner + source tier (glossary precedence), agreed 4 Nov (changed: plan/accept/accept_c6.py, plan/prompts/C6.md)

## C3 result
*Postgres test bed with the Olist loader and a synthetic sample, 02 Nov 2026 22:36.*

Implementer `claude-tc-sonnet`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/C3`.

| check | ok | detail |
|---|---|---|
| testbed/docker-compose.yml exists | yes | missing |
| testbed/load_olist.py exists | yes | missing |
| testbed/README.md exists | yes | missing |
| .gitignore keeps testbed/data/ out of git | yes |  |
| psycopg is a dependency | yes |  |
| README marks the licence check as TODO or states the licence | yes |  |
| sample olist_customers_dataset.csv exists | yes | missing |
| sample olist_customers_dataset.csv header is exact | yes | ['customer_id', 'customer_unique_id', 'customer_zip_code_prefix', 'customer_city', 'customer_state'] |
| sample olist_customers_dataset.csv has 1-30 rows | yes | 6 rows |
| sample olist_geolocation_dataset.csv exists | yes | missing |
| sample olist_geolocation_dataset.csv header is exact | yes | ['geolocation_zip_code_prefix', 'geolocation_lat', 'geolocation_lng', 'geolocation_city', 'geolocation_state'] |
| sample olist_geolocation_dataset.csv has 1-30 rows | yes | 5 rows |
| sample olist_order_items_dataset.csv exists | yes | missing |
| sample olist_order_items_dataset.csv header is exact | yes | ['order_id', 'order_item_id', 'product_id', 'seller_id', 'shipping_limit_date', 'price', 'freight_value'] |
| sample olist_order_items_dataset.csv has 1-30 rows | yes | 6 rows |
| sample olist_order_payments_dataset.csv exists | yes | missing |
| sample olist_order_payments_dataset.csv header is exact | yes | ['order_id', 'payment_sequential', 'payment_type', 'payment_installments', 'payment_value'] |
| sample olist_order_payments_dataset.csv has 1-30 rows | yes | 6 rows |
| sample olist_order_reviews_dataset.csv exists | yes | missing |
| sample olist_order_reviews_dataset.csv header is exact | yes | ['review_id', 'order_id', 'review_score', 'review_comment_title', 'review_comment_message', 'review_creation_date', 'rev |
| sample olist_order_reviews_dataset.csv has 1-30 rows | yes | 4 rows |
| sample olist_orders_dataset.csv exists | yes | missing |
| sample olist_orders_dataset.csv header is exact | yes | ['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp', 'order_approved_at', 'order_delivered_carrier_da |
| sample olist_orders_dataset.csv has 1-30 rows | yes | 5 rows |
| sample olist_products_dataset.csv exists | yes | missing |
| sample olist_products_dataset.csv header is exact | yes | ['product_id', 'product_category_name', 'product_name_lenght', 'product_description_lenght', 'product_photos_qty', 'prod |
| sample olist_products_dataset.csv has 1-30 rows | yes | 3 rows |
| sample olist_sellers_dataset.csv exists | yes | missing |
| sample olist_sellers_dataset.csv header is exact | yes | ['seller_id', 'seller_zip_code_prefix', 'seller_city', 'seller_state'] |
| sample olist_sellers_dataset.csv has 1-30 rows | yes | 2 rows |
| sample product_category_name_translation.csv exists | yes | missing |
| sample product_category_name_translation.csv header is exact | yes | ['product_category_name', 'product_category_name_english'] |
| sample product_category_name_translation.csv has 1-30 rows | yes | 2 rows |
| edge: one customer_unique_id with two customer_ids | yes |  |
| edge: a canceled order | yes |  |
| edge: an order delivered after its estimated date | yes |  |
| edge: an order with two reviews | yes |  |
| edge: an order with two payments | yes |  |
| every order's customer exists in the customers sample | yes | [] |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw with the right row counts | yes | 9 tables |
| a second load gives the same counts (idempotent) | yes | 9 tables |
| a wrong header is refused and the file is named | yes | Olist source check failed: |   olist_orders_dataset.csv: header differs (missing columns ['order_status'], unexpected co |
| pytest tests/testbed | yes | 2 passed, 1 skipped in 0.46s |
| required tests present | yes | 2 found |

Review: C3 matches its prompt. Postgres 16 listens on host port 55432 (database shop, user governor_admin, default password governor_local, named volume, healthcheck). The loader checks the nine published headers, including product_name_lenght, and COPY-loads each CSV into raw as text plus _loaded_at, with truncate and load in one transaction per table. The sample is synthetic and includes every design edge case. testbed/data/ is gitignored. The README licence note is a marked TODO. Acceptance loaded the sample twice with the same counts.

For Amir: The live load checks compare the loader JSON to CSV counts and do not query raw themselves. In this loader that JSON is SELECT count(*) after COPY, both loads matched, and a failed COPY would not print the line, so the rows were loaded. The licence acceptance check is the substring licen; the README marks a TODO and the dataset licence is still unknown. Schemas other than raw, and the roles, belong to C4.

## Additions for C4
C4 adds the Postgres adapter and roles. Leave the loader as it is. Compose: Postgres 16, host 55432, database shop, admin governor_admin, password default governor_local. A fresh database is empty until python testbed/load_olist.py --source testbed/sample (GOVERNOR_PG_DSN or --dsn). Only schema raw is created. Tables are raw.<csv stem>, source columns text, plus _loaded_at timestamptz NOT NULL DEFAULT now(). COPY CSV stores blanks as NULL. Zip prefixes stay text (01000). Keep spellings product_name_lenght and product_description_lenght. Truncate plus COPY is one transaction per table; headers are checked before any connection. psycopg[binary] is locked at 3.3.6. roles.sql, apply_roles.py, dev_governor, and private do not exist yet. Adapter DSN is GOVERNOR_PG_DSN; the acceptance admin DSN is GOVERNOR_PG_ADMIN_DSN. Conformance skips if unset; point its known column at a table the test creates, because list_columns drops information_schema and pg_catalog. Sample: uniq-0001 is cust-0001 and cust-0002; ord-0002 is canceled; ord-0003 is late; ord-0001 has two reviews and two payments. Do not commit testbed/data/. The README licence line is still a TODO. as_of remains 2026-10-22T14:11:26+00:00.

## Relocks
- 04 Nov 2026 15:41: C6: owner/source required only when approved; render refuses placeholder injection (changed: plan/prompts/C6.md)

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

## C6 implementer notes
`governor.core.catalogue`: `load_kpis`, `load_blueprint`, `load_approved`, `render`, `SOURCE_PRECEDENCE`; errors are `CatalogueError` (ValueError) naming the file and the KPI id. Models refuse unknown keys. knowledge/blueprint.md (L1-L9, exceptions []), kpis.yaml (kpis: []), approved.yaml (decisions: []) written. Open for Amir:
- Provenance vs the locked fixture: accept_c6's AOV fixture has no `owner`/`source` and must load, so a missing owner/source is rejected only for `status: approved`; a `proposed` draft may omit them. If present they are always validated (known tier, non-empty ref, vendor needs a note). Say if proposed KPIs should require them too (needs a plan change).
- Design §6 YAML bug: `{..., description: item price, freight excluded}` in a flow mapping splits at the comma (description "item price" plus a stray key). The strict model refuses it; quote the value in real catalogue entries.
- Blueprint wording awaits Amir's gate approval.

## C5 implementer notes
`governor.core.serving apply` runs in one admin transaction: salt into private.pii_salt (one row), drop every view in serve_analyst / serve_finance_admin, recreate one per source table, revoke from PUBLIC and the other governor roles, grant USAGE + SELECT to the owning reader role only. Analyst views read the salt with a scalar subquery (view owner's rights), so the value is never in a definition. `--access` defaults to knowledge/access.yaml (mask_value, finance_admin grants). Validator, postgres dialect only: relations must be `serve_<role>.<model>` (unqualified refused), every function must be on `POSTGRES_FUNCTIONS` and unqualified (`FUNCTION_NOT_ALLOWED`), `FOR UPDATE/SHARE` refused. Postgres adapter caps statement_timeout at 10 s (`MAX_TIMEOUT_S`). Open: tests/testbed/test_testbed.py::test_load_sample_idempotent loads with GOVERNOR_PG_DSN, which since C4 is the ask login, so it fails when both DSNs are set; tests/testbed/test_serving.py did not run against a live database here (accept_c5 stops Docker before pytest).

## Relocks
- 04 Nov 2026 17:30: capstone batch 2 (D1-D5), agreed 4 Nov (changed: plan.yaml, plan/accept/_build.py, plan/accept/_testbed.py, plan/accept/accept_d1.py, plan/accept/accept_d2.py, plan/accept/accept_d3.py, plan/accept/accept_d4.py, plan/accept/accept_d5.py, plan/prompts/D1.md, plan/prompts/D2.md, plan/prompts/D3.md, plan/prompts/D4.md, plan/prompts/D5.md)

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

## D2 notes (implementer)
- `governor.build.profile.profile_schema(dsn, schema, policy)` returns the section 5 dict; `governor.build.models.Profile` validates it (`schema`/`from` are aliases: `schema_`/`from_`). `python -m governor.build profile [--schema raw] [--policy f] [--out f]`; `--out` prints a one-line JSON summary. The connection is read-only, `work_mem` 128MB for that session.
- Type rules: one set of anchored patterns (`PATTERNS`) used both server-side and by `infer_type()` offline. Values with leading zeros (`01000`) are `text`, so zip prefixes stay codes. A mix of dates and timestamps is `timestamp`. A value that matches a pattern but fails the cast (e.g. `2026-02-30`) demotes the column to `text`. Blank strings count as null.
- Speed: a 10k-row sample proposes the type, then the full scan checks only that type and its wider ones. Distinct counts use hash `select distinct` with `collate "C"` (`count(distinct)` under the DB collation was 4x slower). Pair keys skip pairs with a duplicate in the first 100k rows. Measured on the acceptance stack: 2 synthetic 1M-row tables (one with 4 true pair keys) in 24 s.
- The policy matches a bare column name or `table.column`. Without `--policy` nothing is PII, so pass the shop policy. For Amir: should the CLI default to `knowledge/shop/policy.yaml`?
- Sample: orders has 5 single-column candidate keys (5 rows, every timestamp unique); that's expected on tiny data, and D3's design should prefer `*_id` keys.

## Relocks
- 04 Nov 2026 21:54: D5: staging never model-repaired; stale model clean-up (D4 gate finding by Fable) (changed: plan/prompts/D5.md)

## D2 result
*Profile the raw schema, 04 Nov 2026 18:09.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D2`.

| check | ok | detail |
|---|---|---|
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| profile CLI writes the profile | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_qfhdv2gk\\profile.json", "schema": "raw", "tables": 9,  |
| all 9 raw tables profiled | yes | ['olist_customers_dataset', 'olist_geolocation_dataset', 'olist_order_items_dataset', 'olist_order_payments_dataset', 'o |
| row counts match the sample | yes |  |
| loader columns starting with _ are left out | yes |  |
| orders key is order_id | yes | [['order_id'], ['customer_id'], ['order_purchase_timestamp'], ['order_approved_at'], ['order_estimated_delivery_date']] |
| customer_id is a key and customer_unique_id is not | yes | [['customer_id']] |
| orders.customer_id relates to customers.customer_id | yes | [('olist_order_items_dataset.order_id', 'olist_orders_dataset.order_id'), ('olist_order_items_dataset.product_id', 'olis |
| purchase timestamp inferred as timestamp | yes | {'name': 'order_purchase_timestamp', 'inferred_type': 'timestamp', 'null_rate': 0.0, 'distinct': 5, 'pii': False, 'min': |
| price inferred as numeric | yes | {'name': 'price', 'inferred_type': 'numeric', 'null_rate': 0.0, 'distinct': 3, 'pii': False, 'min': 50.0, 'max': 100.0} |
| customer_unique_id is flagged PII with no min or max | yes | {'name': 'customer_unique_id', 'inferred_type': 'text', 'null_rate': 0.0, 'distinct': 5, 'pii': True, 'min': None, 'max' |
| no PII value appears in the profile | yes | [] |
| pytest tests/build | yes | 23 passed, 7 skipped in 0.61s |

Review: D2 profiles raw in SQL and matches section 5. Python receives counts plus min/max only for non-PII integer, numeric, date, and timestamp columns; policy columns, including numeric lat/lng, are counts only. Sample keys, the seven relationships, types, row counts, and the PII-string check all follow from that rule. Table and relationship order is sorted, and nothing reads the clock.

For Amir: On this five-row sample, section 5 treats every unique column as a key, so orders also keys its purchase, approved, and estimated-delivery timestamps, and products keys its measure columns. It will not hold on the full extract. The policy file does not name geolocation_zip_code_prefix, geolocation_city, geolocation_state, or seller_state. Those columns are text in the sample, so no value is written. Lat and lng are listed and their min/max are suppressed. Live pytest was skipped (no DB env in that process); the CLI check in accept_d2.py is what ran the profile.

## Additions for D3
profile_schema(dsn, schema, policy) and the profile CLI use build_dsn(). Shape: schema, profiled_at_rows (always true), tables (name order), relationships (from, to order). Columns are ordinal, skipping names that start with _. Fields: inferred_type (boolean|integer|numeric|date|timestamp|text), null_rate (6 d.p.), distinct, pii, min, max. pii means the column or table.column is a policy key (load_policy on knowledge/shop/policy.yaml). min/max only for non-PII integer (int), numeric (float), date (YYYY-MM-DD), timestamp (YYYY-MM-DD HH:MM:SS). Keys: non-null, distinct == rows; pairs only if no single-column key. Relationships: single-column keys only, from the other column to the key, coverage of non-null distinct values >= 0.95, 4 d.p. Sample has seven: items.order_id, items.product_id, items.seller_id, payments.order_id, reviews.order_id, orders.customer_id, products.product_category_name. customer_id is a key; customer_unique_id is not. Extra keys are tiny-sample artifacts (timestamps, review_score, product measures, seller zip/city/state); do not treat them as business primary keys. Models live in governor.build.models. build does not import governor.ask.

## D3 notes (implementer)
- New module `governor.build.llm` (not in the section 2 table): `make_llm("openrouter"|"fake:<script>")`, `BuildLLM.structured(kind, prompt, schema, role)` / `.text(kind, prompt, key, role)`; roles `plan`/`write` read `GOVERNOR_BUILD_PLAN_MODEL`/`GOVERNOR_BUILD_WRITE_MODEL` (default CHAT_MODEL), clients built on first call. Fake lists: in order, last repeats; `intermediate`/`repair` keyed by model name for D4. Every call appends a usage dict to `llm.calls`; the graph keeps them in state `calls`.
- Prompt has no data values at all: min/max are dropped for every column (not only PII), PII columns are name, pii, null_rate, distinct. Catalogue goes in without `template_sql`.
- Extra finding codes beyond section 6: `PROPOSAL_UNPARSEABLE` (reply is not a Proposal; graph), `EXPR_UNPARSEABLE` (staging expr or boolean mapping is not one expression, or is a query), `KPI_DUPLICATE`. `PII_UNTAGGED` also fires on an intermediate column that carries a PII column of its refs by name. A build KPI without `domain` is `MAPPING_INCOMPLETE`.
- Graph: `propose` counts a repair when it gets findings; 1 + 2 proposals, then write_report and `design_invalid` (design.md with findings, no approve command; design.json is not written for an invalid design). Reject resets the repair budget for one more round with the note and the previous proposal in the prompt; a second reject ends with `design_rejected`. `approve` writes one `column_mapping` per mapping entry (`id map-<kpi>-<name>`, value = the mapping value verbatim, `approved_on` = today's date), replacing same-id entries; the file is checked with `load_approved`.
- `run --profile <file>` uses a saved profile instead of the database; `tests/build/test_graph.py` uses it to run run/reject/approve in new processes offline. `run --policy` defaults to `knowledge/shop/policy.yaml` (answers the D2 question for `run`; `profile` is unchanged).
- Approved context for the prompt: `knowledge/approved.yaml` then `<target>/governor/approved.yaml`.
- For Amir: sample_design.json leaves review comment title/message out of silver (free text, no KPI needs it), and int_order_reviews keeps the latest answer per order by `review_answered_at`, then `review_id`.

## D3 result
*Design proposal, validation, report and the design gate, 04 Nov 2026 18:34.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D3`.

| check | ok | detail |
|---|---|---|
| build never imports ask | yes |  |
| prompts/propose.md exists | yes | missing |
| sample design fixture exists | yes | tests/fixtures/build/sample_design.json |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| build init lists the 9 raw tables | yes |  |
| run pauses at the design gate | yes | {"thread_id": "361ad025-7769-4363-82ec-4975ac82930b", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| design report written | yes | C:\Users\amir0\AppData\Local\Temp\governor_accept_0e4y7ogz\olist-dbt\governor\design.md |
| report lists every catalogue KPI | yes |  |
| report has a gap report section | yes |  |
| report shows the approve command with the thread id | yes |  |
| design.json written | yes |  |
| conversion_rate and gross_margin declined with complete gaps | yes |  |
| invalid proposal stops as design_invalid (MAPPING_UNKNOWN_COLUMN) | yes | {"thread_id": "ec3f60f9-a4d3-4c84-aa63-98a950e873cf", "status": "design_invalid", "report": "C:\\Users\\amir0\\AppData\\ |
| invalid proposal stops as design_invalid (unbuildable KPI marked build) | yes | {"thread_id": "87c6b230-b6e9-433b-a73f-d75e42734feb", "status": "design_invalid", "report": "C:\\Users\\amir0\\AppData\\ |
| invalid proposal stops as design_invalid (PII_UNTAGGED) | yes | {"thread_id": "0820a3b0-7982-4210-92c9-b030cab8703b", "status": "design_invalid", "report": "C:\\Users\\amir0\\AppData\\ |
| a bad first proposal is repaired | yes | {"thread_id": "baae2829-65d5-4e08-9f17-68675fe8cb38", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| reject sends the design back and pauses again | yes | {"thread_id": "361ad025-7769-4363-82ec-4975ac82930b", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| approve in a new process records the design | yes | {"thread_id": "361ad025-7769-4363-82ec-4975ac82930b", "status": "design_approved", "report": "C:\\Users\\amir0\\AppData\ |
| approved column mappings recorded in the target's approved.yaml | yes | [['column_mapping', 'amir'], ['column_mapping', 'amir'], ['column_mapping', 'amir'], ['column_mapping', 'amir'], ['colum |
| pytest tests/build | yes | 67 passed, 8 skipped in 13.25s |

Review: D3 matches the step. Every section 6 code is implemented and fires on a minimal bad proposal; EXPR_UNPARSEABLE, KPI_DUPLICATE, and PROPOSAL_UNPARSEABLE cover the gaps the table leaves. The prompt strips min/max and sends PII columns as name, null rate, and distinct count, with no sample cell values. Code owns every edge. The gate is an interrupt, and approve/reject resume it from SQLite in a new process. Approvals append column_mapping decisions to the target's governor/approved.yaml and never write knowledge/. build does not import ask. Acceptance exercised that path on the Docker test bed.

For Amir: The unbuildable-KPI acceptance check is any() of three code names. This run's only finding was MAPPING_UNKNOWN_MODEL, which is the right code (product_costs mapped to stg_product_costs). Staging with no source_table is implemented as BAD_FOLDER but is not its own parametrized case. A later design_invalid after a rejection does not delete the previous design.json. CLI approved_on is date.today.

## Additions for D4
Extend the same StateGraph. record_decisions currently goes to END and sets status design_approved; point it at write_silver and set the final status to built or escalated in that same approve() resume. approve() resumes only while the next node is design_gate. State: target (absolute), project_name, policy, profile, proposal, findings, repairs, rejections, note, status, report, design, approved_by, approved_file, calls. repairs is the design-loop count and can already be 1 or 2 at approval; use a separate counter for SQL repair. calls uses operator.add, so return only the new usage dicts. design.json is Proposal.to_json_dict(), written only when validation passed, at <target>/governor/design.json. Staging expr is raw-table SQL; intermediate expr is null and the write model owns that SQL. Fake LLM via make_llm('fake:<script.json>'): propose[], intermediate{model:[]}, repair{model:[]}; the last reply repeats. Plan and write roles use GOVERNOR_BUILD_PLAN_MODEL and GOVERNOR_BUILD_WRITE_MODEL. Do not import governor.ask. Do not write knowledge/; company decisions stay in <target>/governor/approved.yaml. tests/fixtures/build/sample_design.json builds every catalogue KPI except conversion_rate and gross_margin, which it declines with gaps.

## D4 notes (implementer)
- `governor.build.silver`: `check_sql`, `staging_sql`, `write_silver` / `dbt_build_silver` / `repair_silver` / `next_step` over a JSON-able state dict (checkpointed by the graph under `silver`), and `build_silver(target, design, llm, runner=, inspector=)` chaining them. Prompts `prompts/intermediate.md`, `prompts/repair.md` (design only, no data values).
- Graph: `record_decisions -> write_silver -> {dbt_build_silver | repair_silver | silver_done}`, code-routed by `silver.next_step`. SQL refused by `check_sql` is never written and goes to repair before dbt runs. Per model: 2 write-model repairs, then 1 plan-model repair; still failing -> `escalated` with `{"model", "error"}`. `approve` returns `status` (`silver_built`|`escalated`), `models`, `tests_passed`, `repairs` (= state `sql_repairs`, repair calls), plus `escalated` when it applies. `build_graph` takes `dbt_runner`/`inspector` for offline tests.
- A failing test is attributed to the silver model whose name it contains (longest match). dbt with no results (profile/connection/parse error) escalates with `model: null` and no repair.
- yml: PII as column `config: {meta: {pii: true}}` (dbt 1.12 moved `meta` under `config`); key tests under `data_tests`; model `config.meta.primary_key`. Composite keys: `tests/<model>__primary_key.sql` (duplicates or null parts). Models stay views (dbt default); only marts are tables.
- Column check: names only (case-insensitive) against `information_schema.columns` in `dev_governor`, as the build login.
- For Amir: stale `stg_*`/`int_*` files from an earlier design are not deleted from the target. The offline CLI cycle in `test_graph.py` now ends `escalated` (its approve script has no intermediate SQL). The live pytest cases in `test_silver.py` skip without `GOVERNOR_BUILD_PASSWORD`; acceptance covers the live path.

## Relocks
- 05 Nov 2026 11:46: capstone batch 2b (D6-D8b), agreed 5 Nov (changed: plan.yaml, plan/accept/_build2.py, plan/accept/_frozen2.py, plan/accept/accept_d6.py, plan/accept/accept_d7.py, plan/accept/accept_d8a.py, plan/accept/accept_d8b.py, plan/prompts/D6.md, plan/prompts/D7.md, plan/prompts/D8a.md, plan/prompts/D8b.md)
- 05 Nov 2026 11:57: D6: testbed/apply_roles.py allowed (deploy role password) (changed: plan.yaml)

## D4 result
*Silver writer, dbt build in the dev schema, repair and escalation, 04 Nov 2026 21:54.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D4`.

| check | ok | detail |
|---|---|---|
| sample design and silver fixtures exist | yes | tests/fixtures/build/ |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| build init lists the 9 raw tables | yes |  |
| run pauses at the design gate | yes | {"thread_id": "7c556dce-bf99-4cbc-b038-a14c66ada5ff", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| approve builds silver | yes | {"thread_id": "7c556dce-bf99-4cbc-b038-a14c66ada5ff", "status": "silver_built", "report": "C:\\Users\\amir0\\AppData\\Lo |
| tests ran and passed | yes | 11 |
| the scripted bad draft was repaired | yes | 1 |
| every silver model exists in dev_governor | yes | [] |
| nothing written outside dev_governor | yes | [] |
| silver yml tags PII columns | yes |  |
| silver yml has unique and not_null key tests | yes |  |
| composite keys have singular tests | yes |  |
| a model that cannot be repaired ends escalated | yes | {"thread_id": "9fd8b17c-fc24-4565-8de1-9e03ca00db18", "status": "escalated", "report": "C:\\Users\\amir0\\AppData\\Local |
| pytest tests/build | yes | 88 passed, 10 skipped in 14.46s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The live run is the evidence: tests_passed 11 equals 4 single-column keys times unique and not_null, plus 3 composite singular tests, and int_order_lines exists only after the repair replaced i.price with i.item_price. The yml checks in accept_d4.py are substring searches. Section 8 still says status built; the step and the script use silver_built until D5. When several models run out of repairs together, only the first is named. A dbt failure tied to no model escalates with model null. Reused targets keep stale SQL files. approved_on is still date.today.

## D5 notes (implementer)
- `governor.build.gold`: `write_gold` (file = `catalogue.render` with relations as `{{ ref() }}`, written as LF bytes; `_<domain>.yml` with definition, meta kpi_id/owner/source_tier/source_ref/template_sha256/rendered_sha256, `not_null` on month/cohort_month), `check_project(target, catalogue, policy, blueprint=)` -> `BlueprintFinding{rule, severity, target, problem}` (severity from blueprint.md, its exceptions honoured), `write_gaps`, `dbt_build_gold`, `kpi_rows`, `summarise` (`governor/build.json`). Hashes are SHA-256 of LF-normalised text.
- L7 checks the final SELECT's output columns, followed through renaming CTE columns, against policy PII plus silver columns tagged pii; PII used inside CTEs and aggregated away is allowed (repeat_purchase_rate reads customer_unique_id). `SELECT *` in gold is an L7 finding. L9 is a regex over gold SQL without comments and string literals.
- Graph: `silver_done -> write_gold (models, gaps.md, check) -> dbt_build_gold -> summarise -> END`; a high finding skips dbt (`blueprint_failed`, build.json still written). A failing gold model escalates (no model repair). `approve` returns status, `kpis_built` (ids), `gaps` (ids), `tests_passed` (silver + gold), `repairs` (SQL repairs), `models`, `blueprint`, plus `escalated` when it applies. `build_graph(row_counter=)` for offline tests.
- Design-gate guard: a failing (or check_sql-refused) staging model escalates at once with `{model, folder, error, fix}`; `repair_silver` only touches intermediate models. `silver.prune_stale` runs at the start of `write_silver` (and `write_gold`): removes .sql/.yml under staging, intermediate and marts, and `tests/*__primary_key.sql`, that the design does not produce; empty mart folders go too. Stale tables in `dev_governor` are not dropped.
- Mart folder = `mart_folder(domain)` (lower case, `[a-z0-9_]`).

## Additions for D5
On silver_built, continue to write_gold; leave escalated at END. Section 8's approve status built is the post-gold name; D4 returns silver_built plus models, tests_passed, and repairs. State.repairs is the design-loop count. SQL repairs are state.sql_repairs and silver.repairs, with per-model counts in silver.attempts (2 write, then 1 plan). calls uses operator.add; return only new usage dicts. Files: models/staging/_staging.yml, models/intermediate/_intermediate.yml, models/<folder>/<name>.sql, and tests/<model>__primary_key.sql for a composite key. PII is columns[].config.meta.pii (dbt 1.12). Single-column keys use data_tests [unique, not_null]. Composite keys do not get per-column unique tests; the singular test returns rows for a duplicate or a null key part. Model config.meta.primary_key lists the key. Silver models stay views; marts are tables via dbt_project.yml. The profile already targets dev_governor as governor_build. That schema is shared and not dropped, and a reused target keeps stale stg_/int_ files. The column check compares names only. design.json is the proposal at <target>/governor/design.json. The sample declines conversion_rate and gross_margin. Do not import governor.ask. Do not write knowledge/.

## D5 result
*Gold from catalogue templates, blueprint checks, gap report, 04 Nov 2026 23:03.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D5`.

| check | ok | detail |
|---|---|---|
| sample design and silver fixtures exist | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| build init lists the 9 raw tables | yes |  |
| run pauses at the design gate | yes | {"thread_id": "fbe9ed5e-9b10-4ba6-bb95-7aad45d73a6e", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| approve builds silver and gold | yes | {"thread_id": "fbe9ed5e-9b10-4ba6-bb95-7aad45d73a6e", "status": "built", "report": "C:\\Users\\amir0\\AppData\\Local\\Te |
| all eight buildable KPIs built | yes | ['gmv', 'net_revenue', 'aov', 'on_time_delivery_rate', 'avg_review_score', 'repeat_purchase_rate', 'cohort_retention', ' |
| gaps list conversion_rate and gross_margin | yes |  |
| target has governor/gaps.md | yes |  |
| target has governor/build.json | yes |  |
| gold yml carries owner, source tier and template hash | yes |  |
| gmv equals the independent computation | yes | got {'2026-01': 455.0} want {'2026-01': 455.0} |
| net_revenue equals the independent computation | yes | got {'2026-01': 325.5} want {'2026-01': 325.5} |
| aov equals the independent computation | yes | got {'2026-01': 100.25} want {'2026-01': 100.25} |
| on_time_delivery_rate equals the independent computation | yes | got {'2026-01': 0.6666666666666666} want {'2026-01': 0.6666666666666666} |
| avg_review_score equals the independent computation | yes | got {'2026-01': 3.3333333333333335} want {'2026-01': 3.3333333333333335} |
| repeat_purchase_rate equals the independent computation | yes | got [['0.3333333333333333']] want 0.3333333333333333 |
| blueprint check is clean on the built project | yes | [] |
| blueprint check catches a cast in gold (L9) and a changed template (L8) | yes | [{"rule": "L8", "severity": "high", "target": "kpi_gmv", "problem": "rendered_sha256 does not match the model file"}, {" |
| pytest tests/build | yes | 122 passed, 11 skipped in 22.12s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The acceptance line "blueprint check is clean" fails only when a high finding is present, so a lone L9 would still pass that line. The unit test requires an empty finding list, and the generated project is empty. cohort_retention and historical_clv are built with rows; the step asked for an independent value check only for the five order-level KPIs and the repeat purchase rate.

## D6 notes (implementer)
- Mapping pairs: `models.ProposalReply`/`KpiDecisionReply` is the schema the model sees (`mapping_pairs`); `design.propose` calls `.to_proposal()` before validation. A reply that still sends a `mapping` dict is accepted as pairs. The previous proposal is shown back as pairs (`proposal_as_reply`).
- Events: `events.emit` keeps scalars and flat lists only (strings cut at 300 chars). `design_gate` is emitted in the report node, because the gate node runs again on resume. Tests set `GOVERNOR_STATE_DIR` to tmp (conftest autouse).
- Publish records the published commit in `.git/governor_published.json` (outside the tree, so certify sees a clean tree). The tree is left on the build branch. It pushes `main` too when the remote has none. `build.json` gains `approved_by` for pr.md.
- Certify: `value_columns` = numeric columns of the deployed table minus the grain column and `months_since_first`. Registry and gaps tables are dropped and recreated as the admin in one transaction. Serving salt: `GOVERNOR_PII_SALT`, else the stored `private.pii_salt`, else a new random one (never printed). `workspace.deploy_env()` supplies the test-bed default deploy password when the env is unset.
- Acceptance D6: 30/30; pytest tests/build 139 passed, 12 skipped.

## Additions for the next plan
D6 opens the PR on the target after approve. approve already runs silver and gold and returns status built, escalated or blueprint_failed, plus kpis_built (ids), gaps (declined ids), tests_passed, repairs, blueprint findings, and build pointing at <target>/governor/build.json. That file has models, silver/gold/total test counts, KPI row counts, full gap objects, findings and cost. Gold files are models/marts/<domain>/kpi_<id>.sql (tables via the marts materialization) and _<domain>.yml (owner, source_tier, source_ref, template_sha256, rendered_sha256, not_null on month or cohort_month). L8 re-renders from governor/design.json; do not add a model that writes gold SQL. High rules stop the build. L5 is medium and L9 is low, so they are recorded and do not stop it. A failing staging model escalates with zero repairs; only intermediate SQL is repaired. On the sample the gaps are conversion_rate and gross_margin. cohort_retention and historical_clv are built and non-empty; their values were not checked against an independent computation.

## D6 result
*Mapping pairs, events, pull request and certification, 05 Nov 2026 12:41.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D6`.

| check | ok | detail |
|---|---|---|
| build models import | yes |  |
| src/governor/build/events.py exists | yes | missing |
| src/governor/build/publish.py exists | yes | missing |
| src/governor/build/certify.py exists | yes | missing |
| roles.sql defines governor_deploy | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| sample design and silver fixtures exist | yes |  |
| build init lists the 9 raw tables | yes |  |
| sample run pauses at the design gate | yes | {"thread_id": "1f027efe-c1ba-48f9-ba6c-a9e39f03eacc", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| sample build completes | yes | {"thread_id": "1f027efe-c1ba-48f9-ba6c-a9e39f03eacc", "status": "built", "report": "C:\\Users\\amir0\\AppData\\Local\\Te |
| events log has the build stages | yes | ['run_started', 'profiled', 'proposed', 'validated', 'design_gate', 'approved', 'repair', 'silver_built', 'gold_built',  |
| events carry no data values | yes | [] |
| publish creates a governor/build-* branch | yes | {"status": "published", "branch": "governor/build-1f027efe", "commit": "318fc9ec7a274365fac180cf68ec25ab435efb39", "pr_u |
| commit by governor with a summary message | yes | governor|governor: build 1f027efe (8 KPIs, 2 gaps) |
| branch contains models, tests and governor files | yes |  |
| main holds only the scaffold | yes |  |
| pr.md has KPIs, gaps, tests and a reviewer checklist | yes |  |
| publish pushes the branch when origin exists | yes | {"status": "published", "branch": "governor/build-1f027efe", "commit": "d8385c7982b45066c82590f2a6aedac6cac0fdec", "pr_u |
| certify refuses before the merge | yes | {"status": "not_merged", "reason": "the working tree is on 'governor/build-1f027efe', not main", "commit": "318fc9ec7a27 |
| reviewer merges the pull request branch locally | yes |  create mode 100644 tests/int_order_lines__primary_key.sql |  create mode 100644 tests/stg_order_items__primary_key.sql  |
| certify deploys after the merge | yes | {"status": "certified", "kpis": ["gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purch |
| registry lists the 8 certified KPIs, certified by amir | yes | ['aov', 'avg_review_score', 'cohort_retention', 'gmv', 'historical_clv', 'net_revenue', 'on_time_delivery_rate', 'repeat |
| gaps table lists the declined KPIs | yes | [['conversion_rate'], ['gross_margin']] |
| serving views exist for the gold tables | yes | [['8']] |
| governor_deploy owns nothing outside analytics | yes | [] |
| pytest tests/build | yes | 139 passed, 12 skipped in 33.88s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: A second certify fails: DROP TABLE on the registry has no CASCADE, and the serving views depend on those tables. On a clone that already has commits, the prod output appended to profiles.yml is not in the branch commit, so the clean-tree check blocks certify until someone commits that file. The published sha lives only in .git/governor_published.json, so a squash merge or another clone cannot certify. The acceptance data-value scan looks only for cust-0001 and ord-0001.

## Additions for D7
D7 reads serve_<role>.governor_certified and serve_<role>.governor_gaps (serving applied with source analytics; schemas serve_analyst and serve_finance_admin). Certified columns: kpi_id, model, label, definition, grain, value_columns (text[] of numeric columns except the grain column month or cohort_month, and except months_since_first), owner, source_tier, source_ref, template_sha256, rendered_sha256, certified_by, certified_at, git_commit. Gap columns: kpi_id, missing (text[]), typical_sources (text[]), next_step. Sample: eight certified KPIs (gmv, net_revenue, aov, on_time_delivery_rate, avg_review_score, repeat_purchase_rate, cohort_retention, historical_clv) and gaps conversion_rate, gross_margin. Gold tables are analytics.kpi_<id>, owned by governor_deploy. Do not import governor.build. design.json still stores mapping as a dict. The certify commit sha is recorded only in the target's .git/governor_published.json.

## D7 notes (implementer)
- `governor.ask.certified`: the registry, gaps and column types (information_schema, as the reader role) are read through `PostgresAdapter(allowed_roles=READER_ROLES)`. The validator policy is built in code: allowlist = the certified models, schema = their serving-view columns, limits from `knowledge/shop/access.yaml`. It calls `validator._validate` directly because `validate()` takes its allowlist from access.yaml and meta.duckdb.
- **Validator bug (outside D7 paths, for Amir):** in sqlglot 30.24, `exp.And`/`exp.Or` subclass `exp.Func`, so `_check_functions` rejects every Postgres query that has `AND` or `OR` ("function AND is not on the allowlist"). That affects the main ask path on Postgres too. The fix is one line: skip `exp.Connector` in `_check_functions`, or add `AND`/`OR` to `POSTGRES_FUNCTIONS`. Meanwhile the certified builder uses no AND: month and cohort filter as `TO_CHAR(grain, 'YYYY-MM') = 'YYYY-MM'`, year as `EXTRACT(YEAR FROM grain) = YYYY`, and several filters combine as one row comparison `(a, b) = (x, y)`.
- Reply rules: grain month takes month, year or all; cohort_month takes cohort, year or all; total takes all only. pick value needs a single row (a month, a cohort or a total). A KPI with `months_since_first` must be given it. max returns the period with its value. sum uses SUM/COUNT of the column. If the reply's value_column is null and the KPI has only one value column, that column is used.
- not_available covers a gap row, or a catalogue KPI (knowledge/kpis.yaml) that is neither certified nor in the gaps. Any other id is unanswerable. The API returns 503 `registry_unavailable` when the registry cannot be read. The certified path takes its FakeLLM from the `certified` key of the same `GOVERNOR_LLM` script.
- Acceptance D7: 27/27; pytest tests/ask 147 passed, 2 skipped (the live tests skip because the acceptance run tears the test bed down before pytest).

## D7 result
*Certified answers in ask, 05 Nov 2026 13:05.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D7`.

| check | ok | detail |
|---|---|---|
| certified.py exists | yes | missing |
| certified prompt lives outside the frozen prompts | yes |  |
| frozen ask prompts unchanged | yes |  |
| ask never imports build | yes |  |
| API exposes /v1/ask/certified | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| sample design and silver fixtures exist | yes |  |
| build init lists the 9 raw tables | yes |  |
| sample run pauses at the design gate | yes | {"thread_id": "114cbd9b-bff4-4eb0-8e37-c46e36ba415a", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| sample build completes | yes | {"thread_id": "114cbd9b-bff4-4eb0-8e37-c46e36ba415a", "status": "built", "report": "C:\\Users\\amir0\\AppData\\Local\\Te |
| publish creates a branch and commit | yes | {"status": "published", "branch": "governor/build-114cbd9b", "commit": "45ca28a35070e62e1f262fff34be90467db427c5", "pr_u |
| reviewer merges the pull request branch locally | yes |  create mode 100644 tests/int_order_lines__primary_key.sql |  create mode 100644 tests/stg_order_items__primary_key.sql  |
| certify deploys to analytics | yes | {"status": "certified", "kpis": ["gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purch |
| answers GMV from the certified table | yes | {"outcome": "answer", "text": "Gross merchandise value (gmv) in 2026-01 was 455. Source: certified KPI gmv (Gross mercha |
| answer cites the KPI and its certifier | yes | {"kpi_id": "gmv", "label": "Gross merchandise value", "model": "kpi_gmv", "owner": "Amir Akhavan (analytics)", "source_t |
| answer text shows the number filled by code | yes | Gross merchandise value (gmv) in 2026-01 was 455. Source: certified KPI gmv (Gross merchandise value), owner Amir Akhava |
| finance role gets the same certified answer | yes | {"outcome": "answer", "text": "Gross merchandise value (gmv) in 2026-01 was 455. Source: certified KPI gmv (Gross mercha |
| declined KPI is not_available and quotes its gap | yes | {"outcome": "not_available", "text": "conversion_rate is not available: this build is missing site sessions with a conve |
| person-level request refused | yes | {"outcome": "refused", "text": "Requests about individual people or records are refused; certified KPIs are aggregates o |
| out-of-scope question unanswerable | yes | {"outcome": "unanswerable", "text": "No certified KPI covers this question.", "value": null, "kpi_id": null, "sql": null |
| a reply naming an uncertified relation never runs | yes | {"outcome": "unanswerable", "text": "No certified KPI covers this question.", "value": null, "kpi_id": null, "sql": null |
| a reply naming a non-value column never runs | yes | {"outcome": "unanswerable", "text": "The certified KPI gmv cannot answer this: 'customer_id' is not a value column of gm |
| pytest tests/ask | yes | 147 passed, 2 skipped in 51.32s |

Review: D7 matches section 14. Code builds one SELECT on the chosen KPI's serving view from registry-checked names. The model supplies only those names. The validator allowlist is the certified models, so an unknown relation, a bad column, a bad period or a free-SQL reply never runs. Numbers come from the result row. The citation names the KPI, owner, source and certifier. Person-level replies are refused with sql null before that query. The prompt is outside the frozen ask prompts, and ask does not import governor.build. Live GMV was 455.

For Amir: Acceptance feeds a scripted reply, so this step shows the code path. A live model routing or refusing is D8. A reply that marks a person-level question as answer still runs only an aggregate SELECT of a certified value column. The two skipped pytest tests are the live GMV tests; they skip when GOVERNOR_PG_DSN is unset. The acceptance CLI already ran that path against Postgres. Existence checks report detail missing even when they pass; that is the shared helper, and the boolean is the result.

## Additions for D8a
D8 calls governor.ask.certified.answer. Do not edit src/governor/ask/prompts/ or import governor.build. Prompt: src/governor/ask/certified_prompts/certified.md. Fake key certified is a list of replies in order. Reply: kpi_id, value_column, period {kind month|year|all|cohort, value}, months_since_first, pick value|max|sum, category answer|not_available|out_of_scope|person_level. Code builds SQL from the KPI view and value column. person_level is refused with sql null before the KPI query; the registry is read first. Unknown names, bad columns, bad periods and out_of_scope are unanswerable and do not run. A catalogue or gap KPI that is not certified is not_available and quotes the gap. Cohort KPIs need months_since_first. value is the float from the result cell. citation: kpi_id, label, model, owner, source_tier, source_ref, certified_by, certified_at, git_commit. CLI: python -m governor.ask.certified QUESTION --role analyst|finance_admin --llm fake:SCRIPT|openrouter. POST /v1/ask/certified uses the /v1/ask token and body; thread_id is ignored. Dates use paths.as_of(). Sample gmv for 2026-01 is 455; gaps are conversion_rate and gross_margin.

## D8a notes (implementer)
- `governor.eval.build_eval` (CLI `python -m governor.eval.build_eval`). Each run gets a fresh target under `--work` (a new temp folder by default) with `models/sources.yml`. Before the run it drops the dev_governor relations owned by the build login (current_user). It drops views first, then tables, with no CASCADE, and retries until nothing more can be dropped. Checkpoints go per run under the work folder.
- Agent: `graph.start`, then `graph.approve(tid, "eval-harness")`. `valid_design_first_try` means the gate was reached with 0 design repairs. `validation_repairs` is the design-loop count and `dbt_repairs` is `sql_repairs`. `tests_failed` is 0 when the build succeeds; otherwise it comes from the last run_results.json.
- Baseline: one `structured("baseline", ...)` call on the plan role with the `BaselineReply {files:[{path, content}]}` schema. Paths must be under `models/` or `tests/`, with no `..`, no drive and no `sources.yml`; anything else is refused and listed. The run makes one `dbt build`. Status is built or failed, or invalid_output when the reply does not parse. For scoring only, the harness runs the blueprint check (`blueprint_high`); the baseline is never repaired. Its KPI decision counts as "build" when `kpi_<id>.sql` was written.
- Expected decisions are hard-coded (`EXPECTED_DECLINE = conversion_rate, gross_margin`; every other catalogue KPI should be built). The gold file does not carry them.
- `--max-cost-usd` is checked before each run, so the run that crosses the budget still finishes. A run with unknown cost (None) counts as 0 toward the budget and is counted in `summary.cost_unknown_runs`.

## Relocks
- 05 Nov 2026 21:41: D11 red-team findings, D12 clean-up (after first live evaluation, 5 Nov) (changed: plan.yaml, plan/accept/accept_d11.py, plan/accept/accept_d12.py, plan/prompts/D11.md, plan/prompts/D12.md)
- 06 Nov 2026 13:23: D11/D12 acceptance pinned to the acceptance port (live tests ran against the dev DB) (changed: plan/accept/accept_d11.py, plan/accept/accept_d12.py)

## D8a result
*Build evaluation harness (agent vs one-shot baseline), 05 Nov 2026 13:24.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D8a`.

| check | ok | detail |
|---|---|---|
| capstone ground truth frozen and unchanged | yes | capstone ground truth unchanged |
| baseline prompt exists | yes |  |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| agent report written | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_vvlbbin3\\agent_report.json", "system": "agent", "runs" |
| two agent runs recorded | yes | 2 |
| every agent run built and passed 6/6 gold checks | yes | [{"run": 1, "system": "agent", "target": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_build_eval_bd1rbrnm\\agent-01 |
| agent approvals recorded as eval-harness | yes |  |
| report has a summary and the gold file hash | yes |  |
| partial baseline scores exactly the one KPI it built | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_vvlbbin3\\baseline_report.json", "system": "baseline",  |
| baseline was never repaired | yes | [{"run": 1, "system": "baseline", "target": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_build_eval_0v48x7sr\\basel |
| pytest tests/eval | yes | 120 passed in 5.63s |

Review: The harness reads the frozen gold file and never writes it. Agent approval as eval-harness happens only in run_agent, and only when the build graph is waiting at the design gate. The baseline receives the same profile, blueprint and KPI definitions with template SQL removed, is built once, and is not repaired. Cleanup drops only dev_governor relations owned by the build login. The budget flag stops further runs once recorded cost reaches the cap. Acceptance scored the agent 6/6 and a one-KPI baseline 1/6.

For Amir: Acceptance scored sample_gold.yaml (6 checks), not olist_gold.yaml (11). The olist file was not executed and its hash is unchanged. A budget cap stops the next run after recorded spend reaches it, so the run that crosses the cap still finishes. Baseline blueprint_high is a static file check after the reply and does not start a repair.

## Additions for D8b
Capstone report reads this JSON and does not recompute it. Root: system, gold_file, gold_sha256, gold_dataset, llm, models, approval, max_cost_usd, stopped_by_budget, runs_requested, runs, summary, total_cost_usd, work. approval is eval-harness for the agent and null for the baseline. A run has status, approved_by, valid_design_first_try, validation_repairs, dbt_repairs, escalated, tests_passed, tests_failed, blueprint_high, kpi_decisions_correct, kpi_decisions_total, gold_passed, gold_total, gold (id, table, passed, value, expected, tol, reason), cost_usd, seconds. Baseline design fields are null. Unparseable baseline output is status invalid_output. A crashed run is status error with gold reason run_failed. summary rates: built, valid_design_first_try, escalated, gold_all_passed, kpi_decisions_all_correct; mean covers the numeric run fields; cost_unknown_runs counts missing costs. Decision key is fixed: decline conversion_rate and gross_margin, build the other eight catalogue KPIs. sample_gold.yaml has 6 checks; olist_gold.yaml has 11. Do not write those files or FROZEN_CAPSTONE.sha256. --max-cost-usd stops starting another run once spend has reached the cap; the run that crosses it is kept. Baseline fake script key is baseline; each item is a JSON string {"files":[{"path","content"}]}. Written paths must sit under models/ or tests/ and must not replace sources.yml.

## D8b notes (implementer)
- `governor.eval.certified_eval`: one `certified.answer` per question. A question passes when the outcome matches. An answer must also be within `tol` and name `expected_period` when one is set. A not_available answer must name the expected KPI. Summary: outcome accuracy (all questions), value accuracy (answerable questions only), confusion, cost. Cost is OpenRouter's billed cost, read from the raw message through a metering wrapper. An exception in a run is recorded as outcome `error`.
- `governor.eval.redteam`: the admin DSN samples distinct raw values (customer, seller, order and review ids; zip prefixes; customer and seller cities; review text) into memory. Ids and zips match whole tokens. Cities match case-insensitive word sequences of 3+ characters. Review text matches as a substring of 12+ characters. Fields scanned: text, sql, kpi_id, citation; the float value is not scanned. Every SQL relation must be `serve_<role>.<certified model>`. Unparseable SQL counts as a leak. The report gives leak kinds and fields only, and every string is redacted against the raw values before writing (questions such as a24 quote an id). Zero sampled values is an error, not a pass. Exit code 2 when the gate fails.
- False refusal: a near-miss expecting `answer` that gets anything else, or one expecting `not_available` that gets neither answer nor not_available.
- `governor.eval.capstone_report`: sorts report files by content (`kind` certified_eval/redteam; `system` agent/baseline). Build reports are grouped by `models.plan` and gold dataset. Numbers are formatted, not recomputed; the only arithmetic is the sum of the reported costs in the Costs section.

## D8b result
*Certified-answer evaluation, red team and the capstone report, 05 Nov 2026 14:26.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 1 fix loop(s); branch `factory/D8b`.

| check | ok | detail |
|---|---|---|
| capstone ground truth frozen and unchanged | yes | capstone ground truth unchanged |
| src/governor/eval/certified_eval.py exists | yes | missing |
| src/governor/eval/redteam.py exists | yes | missing |
| src/governor/eval/capstone_report.py exists | yes | missing |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| sample design and silver fixtures exist | yes |  |
| build init lists the 9 raw tables | yes |  |
| sample run pauses at the design gate | yes | {"thread_id": "4651b38d-f7c1-44a8-9e2a-9b34f39b7bd7", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| sample build completes | yes | {"thread_id": "4651b38d-f7c1-44a8-9e2a-9b34f39b7bd7", "status": "built", "report": "C:\\Users\\amir0\\AppData\\Local\\Te |
| publish creates a branch and commit | yes | {"status": "published", "branch": "governor/build-4651b38d", "commit": "8aeb7f8b963c02ab1ad8a1cea5ab308591d4952a", "pr_u |
| reviewer merges the pull request branch locally | yes |  create mode 100644 tests/int_order_lines__primary_key.sql |  create mode 100644 tests/stg_order_items__primary_key.sql  |
| certify deploys to analytics | yes | {"status": "certified", "kpis": ["gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purch |
| certified eval scores 3/3 on the scripted set | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_t0ub6ycf\\reports\\certified.json", "questions": 3, "pa |
| red team: no leak and no false refusal, gate passes | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_t0ub6ycf\\reports\\redteam.json", "items": 3, "leaks":  |
| red-team report contains no person-level value | yes | [] |
| capstone report renders from the JSON | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_t0ub6ycf\\capstone_report.md", "build": 0, "certified": |
| pytest tests/eval | yes | 144 passed in 7.61s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Acceptance's person-level scan looks for cust-0001, cust-0002 and ord-0001. The writer redacts the full in-memory sample, which the review-plus-id-and-city test covers. Id tokens match in their sampled case; cities and reviews are casefolded. Order ids and review ids are sampled as well as customer and seller ids.

## Additions for the next plan
Leak scoring: RawValues.without(catalogue_vocabulary). Vocabulary is kpi id, model, label, definition, grain, value columns, owner, source tier, source ref, certified_by, and gap id, missing, typical sources, next step. A sampled token or city word-sequence that appears there is removed from scoring in every sentence, case-insensitively. Redaction still uses the full sample, so the report can show [redacted] for sales even when leak is false. Report field raw_values_ignored_as_vocabulary is a count. detect_leak(..., vocabulary=) and evaluate(..., vocabulary=) both apply this. Ids and zips match case-insensitively. certified.answer calls drop_irrelevant_filters before build_sql. build_sql itself still raises Unanswerable if months_since_first is set on a KPI without that column. ADDITIVE_KPIS is the code set {gmv, net_revenue}, not a catalogue field. Any other KPI with pick value or sum and a year or all period on month or cohort_month grain returns one row per grain value, outcome answer, value null, no SUM and no average. pick max is still one row. certified_prompts/certified.md was not changed: it still says pick value is a single period and pick sum is only for additive amounts.

## D12 result
*Clean-up from the D6 and D8 gate reviews, 06 Nov 2026 13:35.*

Implementer `claude-tc-sonnet`; reviewers `cursor-grok`: pass; 2 fix loop(s); branch `factory/D12`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| pytest tests/build | yes | 141 passed, 12 skipped in 37.78s |
| required tests present | yes | 3 found |
| pytest tests/eval | yes | 147 passed in 9.38s |
| required tests present | yes | 3 found |

Review: D12's five clean-ups match the prompt. certify creates the registry tables and serving views before it replaces certified and gap rows, so a serving failure writes nothing. An empty GOVERNOR_PII_SALT raises before the merge check and dbt. Events omit dicts and non-scalar lists and keep scalars and flat scalar lists. certified_eval redacts every stored string with the red-team redactor before writing. build_eval stores blueprint findings as per-rule severity counts, sums them in the summary, and sets valid_design_first_try on agent runs from the design-repair count.

For Amir: Acceptance skipped 12 live tests because accept_d12.py pins GOVERNOR_PG_PORT to 55433 and clears the DSNs. The new certify test checks call order with mocks, not a live deploy. Redaction and event tests run offline.

## Additions for D11
certify order is prepare_registry (CREATE TABLE IF NOT EXISTS for analytics.governor_certified and governor_gaps, resolve salt), then serving.apply, then write_registry, which replaces both tables in one transaction. Tables are not dropped; the views depend on them. GOVERNOR_PII_SALT="" raises CertifyError before merge_check and dbt. The returned salt field is env, stored, or generated, never the salt. The salt is placed in the process environment only when that variable is unset.

emit omits a dict or any list, tuple, or set that contains a non-scalar. Scalars and flat lists of scalars stay. Strings are cut at 300 characters.

certified_eval.main calls sample_raw (needs GOVERNOR_PG_ADMIN_DSN and rows in raw) and passes raw to evaluate. Scoring uses the original text; redact_report then redacts every string. evaluate with raw left unset does not redact. The numeric value is kept, as in the red team. The redteam import is late, to avoid a cycle.

build_eval blueprint_findings is {rule: {severity: count}} with no target or problem text. summary.blueprint_findings_by_rule sums those counts. valid_design_first_try is true only when an agent run is not design_invalid, a proposal is present, and state.repairs is 0. It stays null for the baseline and for crashes. The rate ignores nulls.

## Relocks
- 06 Nov 2026 14:52: batch 2c: D10 descriptions, D9 Slack (agreed 5-6 Nov) (changed: plan.yaml, plan/accept/accept_d10.py, plan/accept/accept_d9.py, plan/prompts/D10.md, plan/prompts/D9.md)

## D10 result (implementer)
Column descriptions from lineage (batch2c section 16). accept_d10: 5/5 (tests/build 146 passed, 12 skipped).
- `build/docs.py`: `describe(design, profile, catalogue, policy, llm)` -> model -> column -> text. Rule 1: gold columns are read from the rendered template's final SELECT (grain, the KPI value, companions such as clv_90d), each with label and definition. Rule 2: staging sentence (raw table.column, cast / empty-as-null / renamed, type, key, null band, PII note from `pii` or policy tag); the design's own text leads when present. Rule 3: intermediate inherits from the first ref that has the name (the design's own text wins). Rule 4: one `describe` call per model with empty columns (prompt `prompts/describe.md`, no profile min/max), reply JSON, trimmed to 200 at a word; a bad reply leaves the column empty. `docs.coverage(target)` reads the written yml.
- Wiring: graph `write_silver` runs `describe` first (state `docs`), passes it to `silver.write_silver(docs=)` and `gold.write_gold(docs=)`. `write_gold` without docs still describes every output column from the catalogue. `build.json` gains `docs_coverage` {columns, described, share}; `pr.md` shows "Column descriptions: N% (k of n columns)". publish.py changed for that line.
- Marts yml now lists every KPI output column (not only the grain); `not_null` stays on the grain. test_gold's yml assertion was updated to match.
- For Amir: test_live_sample_build_matches_independent_values fails against the dev test bed because raw holds the full Olist data (months 2016-18 against the sample's 2026-01). That comes from the data, not from D10, and it skips under the acceptance port. With the sample design, rules 1 to 3 cover every column, so no model call is made.

## D11 result (implementer)
Red-team fixes from the 5 Nov live run. accept_d11: 5/5 (tests/eval 150 passed; tests/ask 149 passed, 2 skipped).
- redteam: `RawValues.without(vocabulary)` drops sampled values that occur as whole words in `catalogue_vocabulary(registry)` (KPI id, model, label, definition, grain, value columns, owner, tier, source ref, certified_by; gap kpi id, missing, typical sources, next step). Scoring uses the filtered set; redaction still uses every sampled value. Ids and zips now match case-insensitively. Report gains `raw_values_ignored_as_vocabulary` (a count). main reads the registry once for allowlist and vocabulary.
- certified: `drop_irrelevant_filters` removes months_since_first on a KPI without that column and adds a sentence to the answer (build_sql itself still raises, for direct callers). `ADDITIVE_KPIS = {gmv, net_revenue}`; any other KPI with pick value or sum over a period with several rows answers per month (or cohort month) in grain order, value=None, plus one sentence on why there is no single figure. pick max is unchanged.
- For Amir: additivity is a code constant, not a catalogue field; a new additive KPI needs adding there. Running tests/ask against the dev test bed (real Olist) fails test_live_gmv_for_the_sample_month because there is no 2026-01 row (data-dependent, not from D11). The prompt still says "pick sum only for additive amounts"; not changed (outside D11 paths).

## D11 result
*Red-team findings (first live run, 5 Nov), 06 Nov 2026 14:29.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D11`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| pytest tests/eval | yes | 150 passed in 8.67s |
| required tests present | yes | 2 found |
| pytest tests/ask | yes | 149 passed, 2 skipped in 50.53s |
| required tests present | yes | 2 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: A raw city or zip that is also a whole word of a label, definition, or source URL (city sales, zip 2014) is not a leak in any sentence. Longer names such as Sales Oliveira still leak. Those exempt values are still redacted in the written report. Additivity is the hardcoded pair gmv and net_revenue, so a new amount KPI is listed period by period until it is added to ADDITIVE_KPIS. The router prompt was left unchanged.

## Relocks
- 07 Nov 2026 12:45: spec fix (via supervise, by human) (changed: plan.yaml, plan/accept/accept_d14.py, plan/accept/accept_d9b.py, plan/prompts/D14.md, plan/prompts/D9b.md)

## D10 result
*Column descriptions from lineage, 06 Nov 2026 15:12.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D10`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| docs.py exists | yes | missing |
| describe prompt exists | yes | missing |
| pytest tests/build | yes | 146 passed, 12 skipped in 40.17s |
| required tests present | yes | 5 found |

Review: Column descriptions are deterministic first: gold from the catalogue definition and role, staging from lineage and profile bands (no data values), intermediate by inheriting the same-named ref (approved text kept). One write-model call per model fills only the columns still empty; the prompt has lineage, counts and assumptions, and replies trim at 200 characters. Texts land in the staging, intermediate and marts yml; build.json and pr.md record docs_coverage. SQL is unchanged (catalogue.render and staging_sql). The five tests, including a graph run, check this.

For Amir: The sample design never calls the write model for descriptions; rule 4 is tested by an added int_customer_orders model. The live sample-build mismatch (full Olist months versus the 2026-01 sample) is the data already on the dev test bed, and acceptance skips it by pinning the port. Marts yml now lists every KPI output column, not only the grain.

## Additions for D9
docs.describe runs in graph write_silver before any SQL is written and stores state docs (model to column to description). silver.write_silver(docs=) and gold.write_gold(docs=) put those strings on column descriptions in _staging.yml, _intermediate.yml and models/marts/<domain>/_<domain>.yml. not_null stays on the grain only. governor/build.json docs_coverage is {columns, described, share}; render_pr adds one Column descriptions line pointing at the yml. Fake script key describe maps each model to a list of JSON objects of column to description, on the write role; a non-JSON reply leaves those columns empty. On the sample design rules 1-3 fill every column, so no describe call is made. Profile min and max must not be copied into any new payload. Do not change staging_sql or gold_sql.

## D9 result
*Slack app, 06 Nov 2026 16:47.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 2 fix loop(s); branch `factory/D9`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| slack-bolt is a dependency | yes |  |
| src/governor/integrations/slack/app.py exists | yes | missing |
| src/governor/integrations/slack/blocks.py exists | yes | missing |
| src/governor/integrations/slack/notifier.py exists | yes | missing |
| docs/slack.md exists | yes | missing |
| governor.build never imports Slack | yes |  |
| Slack modules import without tokens | yes |  |
| pytest tests/integrations | yes | 7 passed in 5.33s |
| required tests present | yes | 7 found |
| pytest tests/build | yes | 146 passed, 12 skipped in 40.96s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Slack-started publish posts the PR URL from publish()'s return. A terminal publish only says a PR was opened, because the published event has pr: true and no pr_url. An approver missing from GOVERNOR_SLACK_NAMES is stored as their Slack user id. An escalation with no model name can omit the error, because silver_done emits before that checkpoint is written. design.md is uploaded whole, so mapping SQL is in the file; the card omits mappings. Tests use a fake Web API client and do not open Socket Mode.

## Additions for the next plan
Do not import governor.integrations from governor.build. Progress events stay scalars: counts, names, codes, status, cost, and pr_url (null when no pull request). The Slack record outcome is failed, built, published, superseded, or interrupted. A gate record stays open only while its stored status is awaiting_design_approval; design_invalid and a second rejection are already failed, so a restart must not mark them interrupted. safe_text still turns integers of 5 or more digits into #, except (N failure(s)) and Got N results. Both dbt lines are parsed: silver 'dbt test <unique_id> <status>: Got N', and gold 'dbt <unique_id> <status>: Got N' where unique_id starts with test. The uploaded design.md is the rendered report with the KPI mapping cell replaced; the table is | id | decision | domain | mapping or reason | and the file in the target is not modified. A publish from Slack posts the link only through the notifier, which create_app registers. Superseded does not cancel the old build thread: a later escalated, built, or published event on that same thread replaces the superseded header.

## Relocks
- 08 Nov 2026 14:17: spec fix (via supervise, by human) (changed: plan.yaml, plan/accept/accept_d9c.py, plan/prompts/D9c.md)

## D14 result
*Keys checked against the profile, 07 Nov 2026 14:26.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D14`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| KEY_NOT_UNIQUE is a validation code | yes | missing |
| propose prompt mentions candidate keys | yes | missing |
| pytest tests/build | yes | 152 passed, 12 skipped in 39.34s |
| required tests present | yes | 5 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: STATUS.md shows a later lock_mismatch because plan files changed after the lock. That is outside this review; the acceptance result given for D14 passed. If a primary_key names a column the model does not declare, _key_findings returns nothing and MISSING_KEY blocks the gate, so a computed column earlier in that same key is not also reported until a later repair.

## Additions for D9b
KEY_NOT_UNIQUE is raised by design.validate for a staging model whose source_table is in the profile. It is not a new graph branch: any finding, including this one, goes through the existing propose repair loop (at most two design repairs) before the gate. A staging primary_key is valid when some candidate key of the source table is a subset of the raw columns its key columns read. A null expr means the raw column of the same name; a bare column or a cast of one maps to that column; any other expr is computed and is KEY_NOT_UNIQUE on subject <model>.<column>. A table with no candidate key gets one finding: leave it unstaged unless a KPI needs it, or dedupe it in an intermediate model. Intermediate models are not checked. Findings contain column names and the table row count, never data values. propose.md already states the rule. tests/build/conftest.py sample_profile now records unique null-free column pairs when a table has no single-column key, matching profile.py. sample_design.json keys stg_reviews on [review_id, order_id], which that sample profile accepts.

## Relocks
- 11 Nov 2026 12:33: batch 2d: E1-E4 added (changed: plan.yaml, plan/accept/accept_e1.py, plan/accept/accept_e2.py, plan/accept/accept_e3.py, plan/accept/accept_e4.py, plan/prompts/E1.md, plan/prompts/E2.md, plan/prompts/E3.md, plan/prompts/E4.md)

## D9b result
*Slack clean-up, 07 Nov 2026 15:02.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 1 fix loop(s); branch `factory/D9b`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.build never imports Slack | yes |  |
| GOVERNOR_SLACK_RUNNERS documented | yes | missing |
| no 'Run finished at' reply | yes | still there |
| Slack modules import without tokens | yes |  |
| pytest tests/integrations | yes | 15 passed in 5.61s |
| required tests present | yes | 7 found |
| pytest tests/build | yes | 154 passed, 12 skipped in 46.32s |

Review: D9b matches section 20 and the acceptance run is trustworthy. Terminal headers are red (stopped, :x: then :heavy_minus_sign:) or green (built/published); superseded and interrupted cover other open records, and a gate-waiting design stays open. Reasons name every failing test with its full count in both dbt spellings, keep 131707 through the second scrub, and omit row tokens. Runners are allowlisted, uploaded design.md drops mapping cells without editing the file, and the notifier posts pr_url from the published event.

For Amir: Acceptance details missing and still there are not failures. check() records its detail argument even when ok is true. GOVERNOR_SLACK_RUNNERS is in docs/slack.md, and no integration source contains Run finished at. A run marked superseded is not cancelled; if that build later escalates, builds, or publishes, the notifier replaces the superseded header with that later outcome.

## Additions for D9c (implementer)
- Slack record fields: `approved_by` (from the approved event, for the certify `--by`), `branch`, `card_ts`/`card_decided` (the open design card), `built_ts`/`built_summary` (the Built reply whose button becomes the link). Certify `--target` is `GOVERNOR_SLACK_TARGETS[project]` (resolved absolute path), else the checkpointed target.
- Approve card update comes from the `approved` event (so terminal approvals also replace the buttons). The `rejected` event has no note and graph.py is outside D9c, so a Slack reject decides the card in the app *before* `graph.reject` (name + scrubbed note); a terminal reject shows `:x: Rejected` without name. If `graph.reject` then fails, the card still reads rejected (the warning is posted in the thread).
- Stale = card decided, press from an older card (`container.message_ts` != `card_ts`), or checkpoint status not `awaiting_design_approval`; publish button stale unless the record outcome is `built`. Slash commands are not stale-checked (they still go to the build, which refuses as before). Existing D9 test now expects the ephemeral stale answer on a second Approve press instead of the "not waiting" thread reply; D9b test expects the new `published: <url>` header.
- `design.normalise_source_tables` runs in `propose` (so the checkpointed proposal and silver see the bare name) and again in `validate`. Only the profile's own schema prefix is stripped (case-insensitive, quotes allowed); `public.<t>` or `raw.raw.<t>` stay UNKNOWN_SOURCE_TABLE.
- Live sample test: `_raw_ready` also compares `count(*)` of every `raw.<csv stem>` with the sample CSV row counts.

## D9c result
*Next steps in the channel, PR link, small fixes, 08 Nov 2026 15:03.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D9c`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.build never imports Slack | yes |  |
| propose prompt asks for the bare table name | yes | missing |
| Slack modules import without tokens | yes |  |
| pytest tests/integrations | yes | 21 passed in 7.78s |
| required tests present | yes | 6 found |
| pytest tests/build | yes | 155 passed, 12 skipped in 45.74s |
| required tests present | yes | 1 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The acceptance detail "missing" on the propose-prompt check is check()'s failure string; the check passed because propose.md tells the model to give the bare table name. A Slack reject marks the card decided before graph.reject, so a failed reject leaves the card reading rejected and blocks another press. A reject from the CLI shows ":x: Rejected" without a name or note, because the rejected event carries neither and graph.py is outside this step.

## Additions for the next plan
Record fields: approved_by (approved event, certify --by), branch and pr_url (published event), card_ts and card_decided (open design card), built_ts and built_summary (Built reply whose button becomes the link). Certify --target is GOVERNOR_SLACK_TARGETS[project], else the checkpointed target. A Slack reject writes the decided line, name plus scrubbed note, before graph.reject, because the rejected event has no note; graph.py was outside this step. A reject that does not pass through the Slack app shows ':x: Rejected' with no name. If graph.reject then fails, the card stays rejected and later presses are stale. The slash command /governor publish is not stale-checked; the button is, unless the record outcome is built. design.normalise_source_tables runs in propose, so the checkpoint and silver see the bare name, and again inside validate, which does not write the proposal back. Only the profile schema prefix is removed (case-insensitive, optional double quotes). public.<table> and raw.raw.<table> stay UNKNOWN_SOURCE_TABLE. _raw_ready skips the live sample gold test unless count(*) of every raw."<csv stem>" equals that sample CSV. The Open pull request button calls publish with open_pr true only when the target has a .git entry and an origin remote.

## E1 result
*Certified answers in Slack (/governor ask), 11 Nov 2026 12:46.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/E1`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.build imports neither Slack nor ask | yes |  |
| governor.ask never imports integrations | yes |  |
| no top-level import of governor.ask in the Slack modules | yes | import it inside the default asker |
| Slack modules import without tokens or a database | yes |  |
| usage text lists ask | yes |  |
| docs/slack.md mentions /governor ask | yes |  |
| docs/slack.md mentions GOVERNOR_SLACK_ASK_ROLE | yes |  |
| docs/slack.md mentions GOVERNOR_SLACK_ASKERS | yes |  |
| docs/slack.md mentions GOVERNOR_SLACK_ASK_LLM | yes |  |
| pytest tests/integrations | yes | 36 passed in 7.56s |
| required tests present | yes | 9 found |

Review: E1 matches section 22. /governor ask takes its role only from GOVERNOR_SLACK_ASK_ROLE, calls certified.answer inside the default asker, and posts the escaped question, CertifiedAnswer.text, and the context line to the channel. Refusals and errors are ephemeral, do not repeat the question, and errors go through safe_text. Logs record outcome, KPI id, and user id. The sql field is not posted. The acceptance checks match this code.

For Amir: The integration tests inject a fake asker, so the suite never calls certified.answer. The real call is GovernorSlack._default_asker. A bad GOVERNOR_SLACK_ASK_ROLE raises ConfigError while building SlackConfig, and __main__ exits before Socket Mode starts.

## E2 result (implementer notes)
accept_e2: 17/17 checks pass (tests/mcp 15 passed; tests/ask 158 passed, 2 skipped); tests/integrations 36 passed. Notes for review: `answer_reply` has an extra keyword-only `registry=` so `answer` keeps one registry read. `query_kpi` types `period_kind` and `pick` as plain strings so a bad value comes back as `{"outcome": "error"}` from our CertifiedReply validation instead of an SDK ToolError; the allowed values are in the tool description. `describe_kpi` reads `template_sha256` with a separate optional query (read_registry's column list is unchanged so the existing fakes keep working); a catalogue KPI with no gap row is `not_available`. describe/list use the private `certified._gap_text` and `_catalogue_ids`.

## Additions for E2
E2 splits certified.answer and adds answer_reply. Slack must keep calling certified.answer(question, role, certified.make_llm(config.ask_llm)) with no adapter, from GovernorSlack._default_asker only. That import has to stay inside the function: a top-level governor.ask import fails the E1 check. The omitted adapter is the ask login (GOVERNOR_PG_DSN), same as the API. make_llm("openrouter") returns None, and answer() then builds the chat model. READER_ROLES is the dict in governor.core.serving (keys analyst and finance_admin). SlackConfig rejects any other ask role at construction, including the Postgres role names. Channel outcomes are answer, not_available, and unanswerable. refused and any exception are ephemeral and must not include the question. The channel shows text only; sql, value, and citation stay off the message and out of the log. Ask logs are outcome, kpi id, and Slack user id. GOVERNOR_SLACK_ASKERS unset means the runners, and unset runners means the approvers. * means every user.

## E2 result
*Certified KPIs over MCP (second read-only server), 11 Nov 2026 13:14.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 1 fix loop(s); branch `factory/E2`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.ask never imports build or integrations | yes |  |
| tests/ask/test_certified.py unchanged against main | yes | the file differs from main |
| src/governor/ask/mcp_server.py unchanged against main | yes | the file differs from main |
| tests/mcp/test_mcp_server.py unchanged against main | yes | the file differs from main |
| mcp_certified imports without a database | yes |  |
| certified.answer_reply exists | yes |  |
| build_server takes an adapter | yes |  |
| docs/mcp.md mentions governor.ask.mcp_certified | yes |  |
| docs/mcp.md mentions list_certified_kpis | yes |  |
| docs/mcp.md mentions describe_kpi | yes |  |
| docs/mcp.md mentions query_kpi | yes |  |
| docs/mcp.md mentions gap_report | yes |  |
| pytest tests/mcp | yes | 15 passed in 30.66s |
| required tests present | yes | 9 found |
| pytest tests/ask | yes | 158 passed, 2 skipped in 50.50s |
| required tests present | yes | 1 found |

Review: E2 matches section 23. certified.answer calls answer_reply after the model choice, and tests/ask/test_certified.py is unchanged and green. query_kpi uses that path: build_sql, the validator, and the role's reader. The four tools take no role and no SQL. Arguments that fail validation return outcome error and run no SQL. Errors are one line with the connection string scrubbed. describe_kpi returns unknown for an id that is neither certified nor a registry gap, including catalogue-only gross_margin. mcp_server.py is unchanged. Acceptance passed.

For Amir: Acceptance details that say the file differs from main, for test_certified.py, mcp_server.py and test_mcp_server.py, are that check's failure text. git diff --quiet main returned 0, so those files match main. The E2 implementer note in NOTES.md still says a catalogue KPI with no gap is not_available and that describe uses _catalogue_ids. describe_kpi returns unknown and does not call _catalogue_ids. query_kpi still returns not_available for that id, because it calls answer_reply.

## Additions for E3
E2 adds python -m governor.ask.mcp_certified, server name governor-certified. GOVERNOR_MCP_ROLE defaults to analyst and must be a key of certified.READER_ROLES (analyst, finance_admin), not the Postgres role name. build_server(role, adapter=None) raises ValueError otherwise; main exits 2. Tools: list_certified_kpis, describe_kpi, query_kpi, gap_report. None takes a role or SQL. query_kpi builds a CertifiedReply with category answer and calls answer_reply. A registry gap is not_available. A catalogue id with no gap row is also not_available on query_kpi, because answer_reply still uses _catalogue_ids. describe_kpi stops after a certified row and a governor_gaps row, then returns outcome unknown plus kpi_id. It does not call _catalogue_ids. template_sha256 is a separate optional query, omitted when the column is absent; read_registry's SELECT list is unchanged. answer_reply(reply, role, adapter=None, *, access_path, kpis_path, registry=None) is the path after the model choice; answer passes the registry it already read so it does not read twice. Slack must keep calling certified.answer from GovernorSlack._default_asker only, import inside the function. mcp_server.py, tests/ask/test_certified.py and tests/mcp/test_mcp_server.py are unchanged. Failures are outcome error with one line of text; safe_text redacts URLs and password, user, host, hostaddr, dbname, port, dsn, sslmode. E3 (perturbed test bed) does not use this server.

