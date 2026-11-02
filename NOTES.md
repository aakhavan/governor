# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
C1 is done. Finished ask runs drop their LangGraph checkpoints from the SQLite file in both the API and the CLI (SqliteSaver.delete_thread, secure_delete, WAL truncate). A tombstone keeps finished-thread 409s and stores no question text. Clarify threads still resume, and paused threads older than GOVERNOR_THREAD_TTL_H (default 24) are pruned at the next ask. /openapi.json is 404 unless GOVERNOR_API_DOCS=1. dry_run uses the same timeout path as run_readonly. The Docker image builds and runs as uid 10001. Prompts and answer wording are unchanged. G10b holdout figures still stand (agent execution accuracy 0.700 vs baseline 0.600). Next is C2, the warehouse adapter seam.

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

## G10b result (implementer notes)
- Holdout run once per system, 23 Oct 2026 (log in `evaluation/holdout_runs.log`); prompts untouched. Holdout: baseline 0.600 / agent 0.700 execution accuracy, valid SQL first 1.000 / 0.700, final 1.000 / 1.000, clarify p/r -/0.000 vs 1.000/1.000, policy 0.333 / 1.000, PII leak true / false, cost $0.028 / $0.078, p50 6.656 s / 19.305 s. Four-report total $0.239.
- Loss: agent 0/2 join and 1/2 time_grain vs baseline 1/2 and 2/2. All three agent misses (j02, j05, t06) have the right values in the wrong shape: an extra month_start on a single named-month total (the tuned metric-shape rule over-applied) and a zero-filled month spine. Human notes in `evaluation/reports/taxonomy.yaml`, read by `python -m governor.eval.report`.
- Added `governor.eval.report` (+ tests/eval/test_report.py), `evaluation/eval_report.md`, `README.md`, `docs/demo-script.md`.

## Additions for G10b
Do not edit src/governor/ask/prompts/ or rewrite evaluation/reports/PROMPTS_FROZEN.sha256. accept_g10b requires that hash file to be older than both holdout reports. Run --split holdout once for baseline and once for agent. Never pass --force-holdout. Load baseline-tune.json (execution_accuracy 0.556, valid_sql_final 0.955, clarify precision null, recall 0, policy_compliance 0.333, pii_leak true, cost_usd 0.036) and agent-tune.json (0.778, valid_sql_final 1.0, valid_sql_first 0.9375, clarify 0.667/0.667, policy 1.0, pii_leak false, cost_usd 0.097). as_of is 2026-10-22T14:11:26+00:00. Agent tune misses: j01 clarify, j03 unanswerable, j06 unanswerable, j04 answered (company_name and one unpaid amount; column count matches, values do not), a03 answer where expect is clarify. Baseline scored j03 and j06 equal, so a join loss on holdout can be plan noise on gpt-5-nano. Report a loss as a loss. The $3 check sums the four report JSONs; these two already add about $0.133. G10b's step budget is $1. Runs 1-3 are only in TUNING.md. Frozen prompt rules: catalog grain shapes, bare COUNT, query model names only, clarify only when no default reading exists.

## G10b result
*Holdout once, eval report, README, demo script, 23 Oct 2026 21:17.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/G10b`.

| check | ok | detail |
|---|---|---|
| report baseline-tune.json exists | yes |  |
| baseline-tune.json covers exactly the tune split | yes | 25 items |
| baseline-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report baseline-holdout.json exists | yes |  |
| baseline-holdout.json covers exactly the holdout split | yes | 15 items |
| baseline-holdout.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report agent-tune.json exists | yes |  |
| agent-tune.json covers exactly the tune split | yes | 25 items |
| agent-tune.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| report agent-holdout.json exists | yes |  |
| agent-holdout.json covers exactly the holdout split | yes | 15 items |
| agent-holdout.json used the frozen golden set | yes | fcce84b6b2f86f3bc194 |
| holdout run exactly once per system | yes | log: ['baseline', 'agent'] |
| PROMPTS_FROZEN.sha256 exists | yes |  |
| prompts unchanged since the freeze | yes | frozen ['answer.md', 'baseline.md', 'draft_sql.md', 'plan.md', 'repair.md'] vs now ['answer.md', 'baseline.md', 'draft_s |
| prompts frozen before both holdout runs | yes |  |
| no PII leak in agent runs | yes |  |
| total eval cost within the $3 budget | yes | $0.239 |
| evaluation/eval_report.md exists | yes |  |
| README has the required sections | yes | missing: [] |
| README has a Mermaid diagram and points to PROVENANCE.md | yes |  |
| README shows the holdout execution accuracy exactly as in the reports | yes | missing [] |
| demo script exists | yes |  |
| no golden text in prompts | yes |  |
| golden set still frozen | yes | golden set unchanged |
| pytest tests | yes | 281 passed in 73.75s (0:01:13) |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: Acceptance checks that eval_report.md and the demo script exist, not that the prose matches the JSON. Summary and per-category counts match all four reports, and the three agent failure notes match the stored SQL. The rule classifier never labels wrong join; j05's country subquery is only in the note, and the scored miss is an extra month_start column.

## Additions for the next plan
Do not rerun holdout or edit src/governor/ask/prompts/. PROMPTS_FROZEN.sha256 is the freeze, and evaluation/holdout_runs.log already has one baseline line and one agent line. Headline holdout: execution accuracy 0.600 baseline vs 0.700 agent; policy 0.333 vs 1.000; PII leak true vs false; agent loses join 0/2 vs 1/2 and time_grain 1/2 vs 2/2. Four-run cost $0.239. evaluation/eval_report.md is generated by python -m governor.eval.report. taxonomy.yaml overrides j02, j05, and t06. The rule classifier has no wrong-join branch.

## Additions for C2
C2 is a pure refactor of the warehouse path. Keep executor results: dry_run(sql, *, timeout_s, database) and run_readonly both use _deadline and raise QueryTimeout; execute() passes Policy.timeout_s and maps QueryTimeout to code TIMEOUT. The graph dry_run node does the same and refuses with the existing warehouse-limits text. Do not send checkpoints, traces, or meta through the adapter (design section 3). Privacy stays in governor.ask.checkpoints: SqliteSaver.delete_thread, PRAGMA secure_delete=ON, PRAGMA wal_checkpoint(TRUNCATE), and question-free tombstones in governor_finished_threads so a finished id is still 409. Clarify threads stay until resume; prune_stale runs at the start of a new ask in the API and the CLI (GOVERNOR_THREAD_TTL_H, default 24, wall clock). GOVERNOR_TRACE_TEXT=1 keeps finished checkpoints. Prompts were not edited. fixture/build_green.py resolves dbt.exe or dbt next to sys.executable so the Linux image builds. as_of remains 2026-10-22T14:11:26+00:00.
