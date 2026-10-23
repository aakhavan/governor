# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
Ask prompts are frozen in evaluation/reports/PROMPTS_FROZEN.sha256 (answer, baseline, draft_sql, plan, repair). Tune split only: baseline execution accuracy 0.556, frozen agent 0.778, agent valid SQL final 1.0, clarify precision and recall 0.67, policy compliance 1.0, no PII leak. as_of remains 2026-10-22T14:11:26+00:00. Holdout has not been run. Retrieval settings and repair code are unchanged. Still open on tune: gpt-5-nano plan intent on j01 (clarify), j03 and j06 (unanswerable), a value miss on j04 with the right column count, and a03 answered instead of clarified.

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

## G10a result (implementer notes)
Tune runs (`ts system execution_accuracy valid_sql_final clarify_p/r policy_compliance pii_leak cost`):
- 2026-10-23T18:02Z baseline 0.556 0.955 -/0.00 0.333 true $0.036
- 2026-10-23T18:11Z agent 0.389 1.000 0.50/0.67 0.333 false $0.108
- 2026-10-23T18:23Z agent 0.556 1.000 0.67/0.67 0.667 false $0.118
- 2026-10-23T18:31Z agent 0.778 1.000 0.67/0.67 0.667 false $0.109
- 2026-10-23T18:39Z agent 0.778 1.000 0.67/0.67 1.000 false $0.097 (frozen)
- Changed prompts only (draft_sql, plan, repair): exact output columns, metric shape by grain, bare COUNT on a counted column, no queries on upstream sources, a stricter clarify bar. Details are in `evaluation/reports/TUNING.md`; hashes are in `PROMPTS_FROZEN.sha256`.
- Open: the plan's intent on join items (gpt-5-nano) moves between answer, clarify and unanswerable from run to run. A stronger plan model is a candidate, but it is not in G10a scope.

## Additions for G10a
G10a tunes ask prompts. The MCP server is not on the graph path: do not import mcp_server into the graph and do not add an NL-to-SQL tool. Role stays out of tool arguments and request bodies. mcp is pinned to >=1.10,<2 (installed 1.30.0); 2.x renames FastMCP and Tool.inputSchema, which the locked accept_g9 client reads. service now has search_catalog (BM25, k capped at 20), describe_model, get_lineage (depth capped at 3), validate_sql, and run_query. Query rows are JSON-safe (dates and decimals as strings). Tool text must not restate access.yaml. as_of remains 2026-10-22. Do not read evaluation/golden. No holdout run in G10a.

## G10a result
*Tune on the tune split, then freeze the prompts, 23 Oct 2026 20:50.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/G10a`.

| check | ok | detail |
|---|---|---|
| baseline-tune.json exists | yes |  |
| baseline-tune.json covers exactly the tune split | yes |  |
| baseline-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| agent-tune.json exists | yes |  |
| agent-tune.json covers exactly the tune split | yes |  |
| agent-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| agent made real model calls (cost > 0) | yes |  |
| tune cost within the $2 step budget | yes | $0.133 |
| PROMPTS_FROZEN.sha256 exists | yes |  |
| frozen hashes match the current prompts | yes | ['answer.md', 'baseline.md', 'draft_sql.md', 'plan.md', 'repair.md'] vs ['answer.md', 'baseline.md', 'draft_sql.md', 'pl |
| no golden text in prompts | yes |  |
| no holdout run yet (that is G10b) | yes | 0 log lines |
| TUNING.md records the changes and before/after numbers | yes | 33 lines |
| golden set still frozen | yes | golden set unchanged |
| pytest tests | yes | 275 passed in 71.50s (0:01:11) |

Review: G10a froze draft_sql, plan, and repair after tune-split runs. Saved baseline and final agent summaries match TUNING.md and NOTES: execution accuracy 0.556 to 0.778, policy 0.333 to 1.0, clarify 0.67/0.67, no agent PII leak. Prompt edits follow checker failures and catalog grain labels. No holdout file or log. Five tune misses remain; four are plan intent on gpt-5-nano.

For Amir: Acceptance checks that TUNING.md has at least 8 lines, not that its numbers match the JSON. Run 0 and run 4 match the two saved reports. Runs 1-3 are recorded only in NOTES and TUNING.md. The COUNT paragraph says policy moved from 0.33 to 1.0; the table shows 0.333, 0.667, 0.667, then 1.0. Baseline still answers j03 and j06, which the frozen agent marks unanswerable.

## Additions for G10b
Do not edit src/governor/ask/prompts/ or rewrite evaluation/reports/PROMPTS_FROZEN.sha256. accept_g10b requires that hash file to be older than both holdout reports. Run --split holdout once for baseline and once for agent. Never pass --force-holdout. Load baseline-tune.json (execution_accuracy 0.556, valid_sql_final 0.955, clarify precision null, recall 0, policy_compliance 0.333, pii_leak true, cost_usd 0.036) and agent-tune.json (0.778, valid_sql_final 1.0, valid_sql_first 0.9375, clarify 0.667/0.667, policy 1.0, pii_leak false, cost_usd 0.097). as_of is 2026-10-22T14:11:26+00:00. Agent tune misses: j01 clarify, j03 unanswerable, j06 unanswerable, j04 answered (company_name and one unpaid amount; column count matches, values do not), a03 answer where expect is clarify. Baseline scored j03 and j06 equal, so a join loss on holdout can be plan noise on gpt-5-nano. Report a loss as a loss. The $3 check sums the four report JSONs; these two already add about $0.133. G10b's step budget is $1. Runs 1-3 are only in TUNING.md. Frozen prompt rules: catalog grain shapes, bare COUNT, query model names only, clarify only when no default reading exists.
