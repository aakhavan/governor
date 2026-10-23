# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
G5b is in place. governor.ask.executor validates, EXPLAINs the rewritten SQL, then runs it through warehouse.connect() read-only with external access and extension autoload off and configuration locked. A validator reject returns its codes, sql null, and no rows. Timeouts interrupt the connection and surface as QueryTimeout (execute code TIMEOUT). Writes and external reads fail as QueryError even if run_readonly is called directly. Masking remains the G5a outer projection, so DISTINCT and GROUP BY keep their row meaning and COUNT(DISTINCT pii) stays a number. Limits come from access.yaml: default_limit 100, row_cap 1000, timeout_s 10, mask ***. G5a validator and policy were not changed. G4 catalog and retrieval are unchanged (4 model cards, 10 metric cards, tune BM25 recall@3 0.8333, hybrid+fake 0.8056). The golden set stays frozen. as_of remains 2026-10-22.

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

## Additions for G6a
G6a should call governor.ask.executor. execute(sql, role) returns ExecResult(ok, codes, reasons, sql, columns, rows, row_count). On a validator reject, ok is false, codes and reasons are the validator's, sql is None, and rows are empty; do not run the user SQL. On success, sql is the rewritten statement (comments removed, LIMIT injected or lowered, mask roles wrapped so DISTINCT and GROUP BY stay inside) and row_count is len(rows). Executor-only codes, with that rewritten sql kept: DRY_RUN_FAILED (reasons[0] is the EXPLAIN error, first line, at most 300 chars), TIMEOUT, and EXEC_ERROR. dry_run(sql) returns DryRun(ok, error) for the repair node; EXPLAIN is not under the interrupt timer. run_readonly(sql, *, timeout_s, row_cap) raises QueryTimeout (a QueryError subclass) or QueryError and is the bypass used by tests. The graph execute node should call execute() so the validator still runs. Optional database, access_path, and meta_path are for fixtures. Take timeout_s 10, row_cap 1000, and mask *** from Policy; do not hardcode models or PII columns. Answer placeholders must be filled from these rows (ints, decimals, dates). as_of remains 2026-10-22. Every connection is closed.
