# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G2a is in place: knowledge/metrics.yaml defines 10 metrics (the 8 required, plus net_new_mrr and arpa), and governor.eval loads a golden set and compares results. Snapshot metrics use mrr_monthly for 2026-09-01, the latest month on or before as_of 2026-10-22. Churned subscriptions are per-account drops in active_subscriptions by month (the first month is omitted). Invoiced revenue, outstanding receivables, and overdue invoices exclude void invoices; overdue keeps rows with days_outstanding > 30. compare checks values with relative tolerance 1e-6, keeps duplicate rows, and ignores column names and column order. evaluation/golden has no files yet, so verify_frozen() is false, and src/governor/ask/prompts has no prompts. as_of.txt is still the build clock (2026-10-22T14:11:26+00:00); pin it before G2b freezes numbers.

## Open questions
- `fct_invoices.days_outstanding` follows the spec literally: 0 only when fully paid. Void invoices (416 not paid) therefore show days outstanding. Should void count as 0 / be excluded? (Amir decides; one-line change in the SQL.)
- `as_of` is the build's wall-clock instant (S4 design: source freshness needs `_loaded_at` within 12 h). Data dates are fixed (seed 42) but `days_outstanding` shifts with each rebuild. Pin as_of if golden answers must be stable across rebuilds.
- `governor.core.config` replaces S4 `triage.config`, which was not imported. Values reconstructed: `ALLOWED_MODELS` from the S4 test, MAX_TOKENS 4096 from the llm docstring; `FAST_MODEL` (`openai/gpt-5-nano`) and `EMBED_MODEL` (`openai/text-embedding-3-small`) are guesses, overridable by env. Check before G4/G5 use them.
- `chromadb` is not a dependency (not in the G1 list). `retrieval.build_index/load_index` need it; add it in the step that uses dense retrieval.
- access.yaml: every model and grant name matches the real warehouse (allowlist = the four marts; `dim_accounts.contact_email` exists and is tagged `email`). No renames needed.
- Capstone brief not yet available; PLAN §1 holds the provisional stance (ask = spine, one triage path = stretch).
- Sol suggested comparing column names/types in the checker; kept name-agnostic on purpose (LLM aliases vary; Spider-style execution accuracy), with equal column counts and permutation matching.

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
