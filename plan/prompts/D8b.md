# D8b: Certified-answer evaluation, red team and the capstone report

Capstone batch 2b, step 4. Contract: `docs/capstone/batch2b.md` section 15. Human gate: release gate and report. Do not edit `evaluation/shop_golden/`, `evaluation/redteam/` or `evaluation/FROZEN_CAPSTONE.sha256`.

Build:
1. `src/governor/eval/certified_eval.py`, CLI `python -m governor.eval.certified_eval --set <questions.yaml> --role analyst --out <report.json> [--llm ...]`: per question the outcome, value and pass; outcome accuracy, value accuracy on answerable questions, cost.
2. `src/governor/eval/redteam.py`, CLI `python -m governor.eval.redteam --set <attacks.yaml> --out <report.json> [--llm ...]`: leak detection as section 15 (person-level raw values sampled from `raw` by the admin into memory only, never written to the report; executed SQL checked against the certified allowlist), false refusals among near-misses, the release gate verdict.
3. `src/governor/eval/capstone_report.py`, CLI `python -m governor.eval.capstone_report [--reports <dir>] [--out <file>]` (defaults `evaluation/reports/capstone/` and `evaluation/capstone_report.md`) writing the report from the report files (build agent vs baseline per planner, certified answers, red team, costs), every number taken from the JSON.
4. Tests in `tests/eval/`: scoring of each outcome, leak detection on crafted outputs (a raw id, a city, an out-of-allowlist relation), the gate verdict, the report renders from fixture reports.

Read: `docs/capstone/batch2b.md` section 15, `evaluation/shop_golden/questions.yaml`, `evaluation/redteam/attacks.yaml`, `src/governor/ask/certified.py`, `src/governor/eval/build_eval.py`.

Done when `plan/accept/accept_d8b.py` passes; Docker Desktop must be running.
