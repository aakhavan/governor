# G2a: Metric definitions, golden-set loader, result checker

First half of the ground-truth work: the parts that are code or definitions. The 40 questions come in G2b.

Build:
1. `knowledge/metrics.yaml`: `metrics:` list, at least 8, each `{id, label, definition, sql, grain, time_column, synonyms: [...], owner}`. `sql` is a SELECT over allowlisted marts only (`knowledge/access.yaml`), explicit columns, no `now()`/`current_date` (use the as_of date as a literal where a reference date is needed). Cover at least: mrr, arr, active_subscriptions, churned_subscriptions (monthly), invoiced_revenue, collected_revenue, outstanding_receivables, overdue_invoices (> 30 days outstanding).
2. `src/governor/eval/__init__.py` and `src/governor/eval/golden.py`: pydantic models for the golden file format below, plus `load_golden()`, `load_split()` and `verify_frozen() -> bool` (sha256 of `evaluation/golden/questions.yaml` and `split.json` against `FROZEN.sha256`; False when any file is missing).
   - File format (written in G2b): top-level `as_of` and `questions:` items `{id, role: analyst|finance_admin, category: simple|join|time_grain|metric|ambiguous|policy|unanswerable, question, expect: answer|clarify|refuse|aggregate|mask|unanswerable, gold_sql?, order_matters: bool=false, rel_tol: float=1e-6, missing_slot?, notes?}`; `split.json` = `{"tune": [...], "holdout": [...]}`.
3. `src/governor/eval/checker.py`:
   - `compare(gold_rows, pred_rows, *, order_matters=False, rel_tol=1e-6) -> Comparison` with `.equal: bool` and `.reason: str`. Rows are lists of tuples; column order is ignored (match columns by permutation when counts agree); numbers compare with relative tolerance; None equals None only; row multiplicity matters.
   - `run_gold(sql) -> list[tuple]`: executes through `governor.core.warehouse.connect()` (read-only, unqualified mart names); connection closed.
4. Tests in `tests/eval/`: checker cases (row order, column permutation, tolerance boundary, row count differs, duplicates, None handling), golden model validation on a small fixture of your own, `verify_frozen` false on missing files.

Do not create `evaluation/golden/questions.yaml` or any agent prompt in this step.

Read: `knowledge/access.yaml`, `knowledge/policy.yaml`, `artifacts/green/as_of.txt`, `src/governor/core/{paths,warehouse}.py`; inspect mart columns with duckdb on `artifacts/meta.duckdb` (`columns`) and run candidate SQL through `governor.core.warehouse.connect()` with `LIMIT`.

Done when `plan/accept/accept_g2a.py` passes.
