# G10a tuning (tune split only, 25 items)

Real models via OpenRouter: plan on FAST_MODEL (gpt-5-nano), draft/repair/answer on gpt-5-mini. No holdout run.
Golden questions were not read; changes came from the agent's own SQL, the report's failure reasons and the decision traces (plan JSON, rejected SQL, validator codes).

## Runs

| run | system | execution_accuracy | valid_sql_final | clarify p / r | policy_compliance | pii_leak | cost $ |
|---|---|---|---|---|---|---|---|
| 0 | baseline | 0.556 | 0.955 | - / 0.00 | 0.333 | true | 0.036 |
| 1 | agent (G6 prompts) | 0.389 | 1.000 | 0.50 / 0.67 | 0.333 | false | 0.108 |
| 2 | agent | 0.556 | 1.000 | 0.67 / 0.67 | 0.667 | false | 0.118 |
| 3 | agent | 0.778 | 1.000 | 0.67 / 0.67 | 0.667 | false | 0.109 |
| 4 | agent (frozen) | 0.778 | 1.000 | 0.67 / 0.67 | 1.000 | false | 0.097 |

Stopped after run 4, the run cap. Total spend about $0.47 of the $2 budget. The reports in this folder are baseline run 0 and agent run 4, and run 4's prompts are the ones frozen in `PROMPTS_FROZEN.sha256`.

## What changed and why

1. **Output columns (draft_sql, repair), runs 2-4.** Run 1 lost most items on "column count differs". The drafts had added constant columns (an `as_of` date, period start and end), extra measures (a count next to a requested sum) and an id next to a name. The fix states the output shapes: one number gives one column; a per-group value gives key + value; a list gives one identifier (the name if there is one) plus the requested values. Repair keeps the rejected query's columns.
2. **Metric shape by grain (draft_sql), run 3.** The run 2 rule wrongly gave every snapshot metric a month column. It now follows the catalog grain: "snapshot (latest month…)" returns month_start + value, "snapshot (as_of)" returns the values its definition lists with no date, and "month" returns month_start + value. Run 4 added one more rule: when a metric is used to rank or break down by an entity, return the key and the one named measure.
3. **Bare COUNT on a column (plan, draft_sql), runs 2-4.** The aggregate policy item was refused (PII_FORBIDDEN) in runs 1-3. The plan kept adding an "is not null" filter, and the draft wrapped or filtered the counted column (`LOWER(...)`, `IS NOT NULL`, `TRIM(...) <> ''`). The prompts now say the counted column appears only bare inside COUNT, and the plan no longer adds not-null filters. Policy compliance went from 0.33 to 1.0. The prompts do not restate access.yaml.
4. **Upstream sources are not tables (plan, draft_sql), run 3.** One join item used `crm.accounts`, a name taken from the card's "upstream sources" line, and was refused with TABLE_NOT_ALLOWED. Both prompts now say to query only names listed after "model".
5. **Clarify bar (plan), run 2.** Two join items asked for clarification although they had a default reading. The plan prompt now lists the cases that count as answerable: a top-N, a named period, "so far", "last N days" or a named metric. Clarify is kept for a missing period or a term that maps to two catalog metrics.

Retrieval settings (BM25, k) and the repair logic were not changed. The traces showed the right cards in context for the remaining failures, and the SQL that ran was always valid (valid_sql_final 1.0).

## Remaining failure categories (run 4)

- **Plan intent instability on join questions (3 items).** The join items move between answer, clarify and unanswerable across runs, even where the run 3 prompt answered them. The plan runs on gpt-5-nano, and its intent call is the noisiest step. A stronger model for `plan`, or a vote over several samples, is the next step to try (G10b or later, not tuned here).
- **Value mismatch on one join (1 item).** It has the right shape but wrong numbers, likely the business meaning of "overdue"/"unpaid" or the ranking key.
- **Ambiguous question answered (1 item).** One item that expects clarify is answered with a default reading. Clarify precision and recall are both 0.67.
- Resolved on tune: extra or missing columns, metric shapes, the PII aggregate refusal and the source-table refusal.
