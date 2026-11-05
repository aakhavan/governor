# D8a: Build evaluation harness (agent vs one-shot baseline)

Capstone batch 2b, step 3. Contract: `docs/capstone/batch2b.md` section 15. Do not edit anything under `evaluation/build_gold/` or `evaluation/FROZEN_CAPSTONE.sha256`.

Build:
1. `src/governor/eval/build_eval.py` and CLI `python -m governor.eval.build_eval --system agent|baseline --runs N --gold <file> --out <report.json> [--plan-model ...] [--write-model ...] [--llm fake:<script>|openrouter]` exactly as section 15: empty target and emptied `dev_governor` per run (drop only objects owned by `governor_build`), the agent approved programmatically as `eval-harness` (only inside this harness), the baseline as one plan-model call writing every silver and gold file (prompt `src/governor/eval/prompts/baseline_build.md`, no templates), built once and never repaired.
   Fake LLM script: the agent uses the build script format (`propose`, `intermediate`, `repair`); the baseline reads `{"baseline": ["<json {\"files\": [{\"path\", \"content\"}]}>", ...]}` and writes each file under the target (paths under `models/` or `tests/` only).
2. Gold checks read from the gold file (table, expr, where, expected, tol) against the run's schema; a missing table or column fails that check.
3. Report JSON: per run the section 15 fields; summary with means and pass rates; the gold file's sha256; the models used; total cost. A budget flag `--max-cost-usd` stops further runs.
4. Tests in `tests/eval/`: report shape, gold check scoring (pass, out of tolerance, missing table), the run loop with the fake LLM.

Read: `docs/capstone/batch2b.md` section 15, `evaluation/build_gold/*.yaml`, `src/governor/build/{graph,llm,dbt}.py`, `src/governor/eval/harness.py`.

Done when `plan/accept/accept_d8a.py` passes; Docker Desktop must be running.
