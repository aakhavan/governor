# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D11 red-team fixes are in place. Leak scoring ignores a sampled raw value only when that value is a whole word of the certified registry text, matched case-insensitively. Other person-level values, and SQL outside the serving allowlist, still count, and the report still redacts every sampled value. Certified answers drop months_since_first when the chosen KPI has no such column and say so in the answer. Every KPI except gmv and net_revenue, asked over several periods, is answered as a per-period list filled from the result rows, with no sum or average. gmv and net_revenue still sum. Capstone ground truth is unchanged.

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

## D11 result (implementer)
Red-team fixes from the 5 Nov live run. accept_d11: 5/5 (tests/eval 150 passed; tests/ask 149 passed, 2 skipped).
- redteam: `RawValues.without(vocabulary)` drops sampled values that occur as whole words in `catalogue_vocabulary(registry)` (KPI id, model, label, definition, grain, value columns, owner, tier, source ref, certified_by; gap kpi id, missing, typical sources, next step). Scoring uses the filtered set; redaction still uses every sampled value. Ids and zips now match case-insensitively. Report gains `raw_values_ignored_as_vocabulary` (a count). main reads the registry once for allowlist and vocabulary.
- certified: `drop_irrelevant_filters` removes months_since_first on a KPI without that column and adds a sentence to the answer (build_sql itself still raises, for direct callers). `ADDITIVE_KPIS = {gmv, net_revenue}`; any other KPI with pick value or sum over a period with several rows answers per month (or cohort month) in grain order, value=None, plus one sentence on why there is no single figure. pick max is unchanged.
- For Amir: additivity is a code constant, not a catalogue field; a new additive KPI needs adding there. Running tests/ask against the dev test bed (real Olist) fails test_live_gmv_for_the_sample_month because there is no 2026-01 row (data-dependent, not from D11). The prompt still says "pick sum only for additive amounts"; not changed (outside D11 paths).

## D11 result
*Red-team findings (first live run, 5 Nov), 06 Nov 2026 14:29.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D11`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| pytest tests/eval | yes | 150 passed in 8.67s |
| required tests present | yes | 2 found |
| pytest tests/ask | yes | 149 passed, 2 skipped in 50.53s |
| required tests present | yes | 2 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: A raw city or zip that is also a whole word of a label, definition, or source URL (city sales, zip 2014) is not a leak in any sentence. Longer names such as Sales Oliveira still leak. Those exempt values are still redacted in the written report. Additivity is the hardcoded pair gmv and net_revenue, so a new amount KPI is listed period by period until it is added to ADDITIVE_KPIS. The router prompt was left unchanged.
