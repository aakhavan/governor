# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G1 is in place: governor.core resolves paths from the repo root (GOVERNOR_ROOT), warehouse.connect() opens artifacts/green/warehouse.duckdb read-only with the marts schema on the search path, and harvest fills artifacts/meta.duckdb. The green build publishes the four marts (dim_accounts 2000, fct_invoices 30000, fct_revenue_daily 24708, mrr_monthly 11910). fct_invoices is one row per invoice; days_outstanding counts days from issued_at to the build as_of and is 0 when the invoice is fully paid. PII tags in meta are copied from policy.yaml by column name, so dim_accounts.contact_name and contact_email are tagged. access.yaml was not edited. as_of.txt is the UTC time of the build, so rebuilding moves days_outstanding while seed 42 keeps the raw data fixed.

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

## Additions for G1
- Start from `PROVENANCE.md`: it lists every imported file and its original path. Rename imports `triage.` → `governor.core.`; replace any path built from the S4 folder with `governor.core.paths`.
- Keep changes to imported code minimal and list each one in `PROVENANCE.md` ("changed: …").

## Additions for G2a
G2a should resolve every relative date with governor.core.paths.as_of() (artifacts/green/as_of.txt). build_green.py stamps that file from UTC now, so days_outstanding changes on each rebuild even though seed 42 fixes raw rows; pin as_of before gold numbers are frozen. Marts: dim_accounts 2000, fct_invoices 30000 (one row per invoice), fct_revenue_daily 24708, mrr_monthly 11910. days_outstanding is 0 only when paid_amount_eur >= amount_eur; unpaid void invoices stay nonzero. PII is not lineage: policy.yaml maps contact_name to name, contact_email to email, card_last4 to payment_card, and harvest tags every column of that name (8 rows). card_last4 is staging/source only. Do not edit access.yaml; allowlist is those four marts; the only grant is dim_accounts.contact_email. dbt build excludes exposures, so meta.results has no exposure rows; meta.exposures still has 2. warehouse.connect() is read-only with search_path=marts. config.FAST_MODEL and EMBED_MODEL are guesses; chromadb is not installed; the Chroma collection is still named triage_knowledge.
