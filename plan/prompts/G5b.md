# G5b: Dry-run and read-only executor

Part 2 of the security boundary. The validator from G5a decides what may run; the executor makes sure that even a wrong validator cannot write, read files or run forever.

Build:
1. `src/governor/ask/executor.py`:
   - `dry_run(sql) -> DryRun{ok, error}` with `EXPLAIN` on a read-only connection;
   - `run_readonly(sql, *, timeout_s, row_cap) -> (columns, rows)`: `governor.core.warehouse.connect()` (read-only), interrupt the connection after `timeout_s` (raise `QueryTimeout`), raise `QueryError` on any database error, fetch at most `row_cap` rows, always close;
   - `execute(sql, role) -> ExecResult{ok, codes, reasons, sql, columns, rows, row_count}`: validate (G5a) → dry_run → run_readonly with the access.yaml limits. On a validator reject, return its codes and no rows.
   - Disable DuckDB extension autoloading and external file access on the connection where DuckDB allows it (`enable_external_access`, `autoinstall_known_extensions`, `autoload_known_extensions`); note what the installed version supports in NOTES.
2. Tests in `tests/ask/`: execute for both roles, masking results (values are the mask, DISTINCT row count unchanged, `COUNT(DISTINCT pii)` stays a number), LIMIT and row cap on real rows, timeout, a write refused by the connection even with the validator bypassed, dry_run on a bad column.
3. Fix `validator.py` only where an executed locked case shows a validator bug; note each fix in NOTES.

Read: `src/governor/ask/{validator,policy}.py`, `src/governor/core/{paths,warehouse}.py`, `knowledge/access.yaml`. The locked cases in `plan/accept/_g5_cases.py` are the contract; read them, do not edit them.

Done when `plan/accept/accept_g5b.py` passes.
