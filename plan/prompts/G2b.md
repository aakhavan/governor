# G2b: Golden set, gold SQL, frozen split

This step defines ground truth for governor-ask. A human reviews every item at the gate. Nothing here may come from a model's answers, and no agent prompt exists yet.

Build:
1. `evaluation/golden/questions.yaml` in the format of `governor.eval.golden` (read its models): top-level `as_of` (copy of `artifacts/green/as_of.txt`) and exactly 40 questions.
   - Categories and counts: simple 6, join 6, time_grain 6, metric 6, ambiguous 5, policy 6, unanswerable 5.
   - `expect`: `answer` (simple, join, time_grain, metric); `clarify` (ambiguous, with `missing_slot` such as time_range, metric, grain, entity); `refuse` | `aggregate` | `mask` (policy, following `knowledge/access.yaml` for the role; include both roles and all three kinds); `unanswerable` (data not in the marts).
   - `gold_sql` is required for answer/aggregate/mask and absent otherwise. Marts only, explicit columns (no `SELECT *`), relative dates computed from the literal as_of date (never `now()`/`current_date`). Metric questions use the definitions in `knowledge/metrics.yaml`. For `mask`, gold SQL outputs the mask value from access.yaml in place of the masked column, in an outer projection.
   - Questions are worded the way a finance or ops analyst would ask. Do not name tables, columns or SQL in the question.
   - `notes`: one line per item on why the gold SQL answers the question as worded (grain, filters, date bounds).
2. `evaluation/golden/split.json`: 25 tune / 15 holdout, disjoint, stratified so every category appears in both.
3. `evaluation/golden/FROZEN.sha256`: sha256sum format, `<hex>  questions.yaml` and `<hex>  split.json`. `governor.eval.golden.verify_frozen()` must return True.
4. `evaluation/golden/REVIEW.md`: a table id | category | role | question | expect | gold result (first row, from `run_gold`) for Amir's gate review.

Change `src/governor/eval/golden.py` only if its models reject a valid item; note why in NOTES.

Read: `src/governor/eval/golden.py`, `src/governor/eval/checker.py`, `knowledge/metrics.yaml`, `knowledge/access.yaml`, `artifacts/green/as_of.txt`; query marts through `governor.core.warehouse.connect()` with `LIMIT`.

Done when `plan/accept/accept_g2b.py` passes.
