# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G3 is in place. as_of is pinned in fixture/AS_OF at 2026-10-22 14:11:26+00:00 (GOVERNOR_AS_OF overrides the build only), and a rebuild reproduces that instant and the fct_invoices mart. governor.eval scores a split on execution accuracy, valid SQL, clarify precision and recall, policy compliance, and pii_leak, and it refuses an unfrozen golden set. Oracle scores 1.0 with no leak, null scores accuracy 0, and leaky is flagged for every analyst item but not for finance_admin's granted email. A second holdout run of the same system exits 2 unless --force-holdout. governor.ask.baseline is one prompt with the mart schema and the question (gpt-5-mini, max_tokens 4096), with no retrieval, validator, or policy; --llm defaults to fake and returns SELECT 1 at cost 0. The golden set remains frozen: 40 questions, tune 25, holdout 15.

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
