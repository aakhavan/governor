# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G5a is in place. Policy.for_role loads knowledge/access.yaml and PII tags from meta.duckdb; an unknown role raises UnknownRoleError. validate() uses sqlglot (duckdb): one SELECT or set operation, default-deny on relations and table functions, PII forbidden for aggregate_only unless it is the bare argument of COUNT or COUNT(DISTINCT), and an outer mask projection for mask roles so raw PII stays in DuckDB. Missing LIMITs become default_limit; larger LIMITs drop to row_cap. G4 catalog and retrieval are unchanged (4 model cards, 10 metric cards, tune BM25 recall@3 0.8333, hybrid+fake 0.8056). The golden set stays frozen. as_of remains 2026-10-22.

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
