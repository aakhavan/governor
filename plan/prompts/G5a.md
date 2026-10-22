# G5a: SQL validator and role policy

This is the security boundary (part 1: the validator). Python decides; the model only proposes SQL. Policy comes from `knowledge/access.yaml` and PII tags from `artifacts/meta.duckdb` (`columns.pii_tag`); do not copy policy values into code.

Build:
1. `src/governor/ask/policy.py`: load access.yaml + PII tags; `Policy.for_role(role)`; unknown role is an error.
2. `src/governor/ask/validator.py`: `validate(sql: str, role: str) -> ValidationResult{ok, codes: list[str], reasons: list[str], sql: str|None, tables: list[str], pii_columns: list[str]}` using sqlglot (duckdb dialect). Reject codes:
   - `PARSE_ERROR`; `MULTI_STATEMENT`; `NOT_SELECT` (anything but SELECT / WITH … SELECT, incl. PRAGMA, ATTACH, COPY, SET, CALL, INSTALL, LOAD);
   - `TABLE_FUNCTION` (any table function or file read: `read_csv`, `read_parquet`, quoted file paths, `duckdb_*()`, `glob`, `range`/`generate_series` as tables);
   - `TABLE_NOT_ALLOWED`: default-deny. Every relation must be an allowlisted model or a CTE defined in the same query; anything else (raw, staging, `information_schema`, other schemas, quoted file paths) is rejected. `TABLE_FUNCTION`: every table-valued function, no exceptions list needed.
   - `COLUMN_UNKNOWN`; `STAR` (`SELECT *` or `t.*`; `count(*)` is fine);
   - `VOLATILE_TIME`: `current_date`, `current_timestamp`, `now()`, `today()`, `localtimestamp`, `get_current_timestamp()` and similar. Time must come as literals derived from `as_of` (the plan supplies them).
   - `PII_FORBIDDEN`: for `aggregate_only`, a PII column anywhere except as the argument of `COUNT` / `COUNT(DISTINCT …)`, followed through aliases, CTEs, subqueries, functions, WHERE, GROUP BY, ORDER BY, JOIN ON;
   - `UNKNOWN_ROLE`.
   - On success `sql` is rewritten: LIMIT added (`default_limit`) or lowered to `row_cap`. For `mask` roles, masking happens in an **outer projection** around the original query (`SELECT '<mask>' AS c1, c2 … FROM (<query>)`), so DISTINCT, GROUP BY, ORDER BY and set operations keep their meaning; an output column is masked when its lineage reaches a non-granted PII column as a value. `COUNT(…)`/`COUNT(DISTINCT …)` of PII is a number, not a value, and is not masked. Raw PII never leaves DuckDB for a mask role.
3. Tests in `tests/ask/`: your own cases for every code, both roles, the LIMIT rewrite, and the masking rewrite through an alias, a CTE and DISTINCT. The executor comes in G5b; do not write it here.

Read: `knowledge/access.yaml`, `src/governor/core/{paths,warehouse}.py`, `src/governor/core/lineage.py`; query `artifacts/meta.duckdb` (`columns`) with `LIMIT`. The locked cases in `plan/accept/_g5_cases.py` are the contract; read them, do not edit them.

Done when `plan/accept/accept_g5a.py` passes.
