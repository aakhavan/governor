# AGENTS.md: rules for every agent in this repo

This repo is **governor** (core + ask modules), built step by step by the code factory. Your step prompt names the files you need; read those, not whole documents.

## Hard rules
- **Never commit, push, branch or stash.** The factory commits.
- **Never read `.env` or `.env.*`**, never print, log or echo keys or env values. Keys are read by name from the environment (`OPENROUTER_API_KEY`).
- **Change only the paths your step allows** (plus `NOTES.md`). Never edit `plan/` (locked) or, from G3 on, `evaluation/golden/`.
- Never read the Turing College folders. Everything from Sprint 4 is already in this repo (see `PROVENANCE.md`).
- `knowledge/access.yaml` and `knowledge/policy.yaml` are human-owned policy. Code reads them; prompts never restate them.
- Python 3.12 + uv. LangChain v1 / LangGraph v1 only: no `AgentExecutor`, no `langchain_classic`, no `create_react_agent`.
- Prompts live in `prompts/` folders next to the code that uses them (`src/governor/ask/prompts/`, `ask/certified_prompts/`, `build/prompts/`, `eval/prompts/`), never in code strings. Pydantic for every model output and tool argument.
- Time: resolve relative dates against `artifacts/green/as_of.txt`. Never `now()`, `current_date` or `datetime.now()` in data logic.
- Tests run offline: fake or scripted LLMs, no network. Only the G10a/G10b evaluation calls real models.
- DuckDB: open the warehouse `read_only=True`; close every connection (Windows file locks).

## Capstone steps (C1 onwards)
- Contracts: `docs/capstone/design.md`; vocabulary: `CONTEXT.md`; decisions: `docs/adr/`. Read only the sections your step prompt names.
- The Postgres test bed runs in Docker (`testbed/docker-compose.yml`, host port 55432). Never point code or tests at any other database. Connection settings come from env (`GOVERNOR_PG_DSN`, `GOVERNOR_PG_ADMIN_DSN`); the only passwords allowed in files are the documented test-bed defaults.
- Real Olist data lives in `testbed/data/` and is never committed; tests use `testbed/sample/`.
- Warehouse access goes through `governor.core.adapters`. governor's own stores (`meta.duckdb`, `traces.duckdb`, checkpoints) do not.
- After their gates, `knowledge/blueprint.md`, `knowledge/kpis.yaml` and `knowledge/approved.yaml` are human-owned like `access.yaml` and `policy.yaml`: code reads them; a step changes them only when its prompt says so.

## Golden set (from G3 on)
- Never read `evaluation/golden/questions.yaml` to write prompts, examples or tests. Code loads it through `governor.eval`; tests use their own small fixtures.
- Never copy golden questions or gold SQL into prompts. The acceptance scripts check for overlap.

## Never read whole (query or skip instead)
- `uv.lock`, `artifacts/**` (`manifest.json`, `catalog.json`, `run_results.json`, `sources.json`, `*.duckdb`, `*.sqlite`), `fixture/billing_mart/target/`, `.factory/`, `NOTES-archive.md`, `testbed/data/**`, any data file over 200 KB. Use `duckdb` with `LIMIT`, or `python -c` with `json` and a key filter.

## Output rules
- Quiet commands: `uv run pytest -q`; dbt logs to a file; print summaries only.
- Paste results, not logs.

## Coordination
- `NOTES.md`: current state, open questions, last two steps' result + additions. Under 150 lines. Add a short "Gn result" when you finish.
- `PROVENANCE.md`: every file imported from Sprint 4, with its source and what was changed.

## Capstone batch 2 (D1 onwards)

- Contract: `docs/capstone/batch2.md`. Code goes in `src/governor/build/`; it never imports `governor.ask`.
- Tests use the fake LLM only. Never write credentials to a file; connection settings come from env.
- Scratch output goes to the system temp folder, never the repo root.

## Capstone batch 2d (E1 onwards)

- Contract: `docs/capstone/batch2d.md`. `src/governor/build/graph.py`, `src/governor/build/design.py` and everything under `evaluation/` do not change in this batch.
- `governor.integrations` may import `governor.ask` and `governor.build`; those two never import each other or `governor.integrations`.
- No data value from the warehouse goes into a prompt, a log line, a Slack message or a file in the repo. Tests use a marker string to prove it. This holds for build mode and the certified path. The one existing exception is governor-ask's answer step (`ask/prompts/answer.md`), which sees the first result rows to word the answer; it writes placeholders and `fill_answer` puts the values in.

## Capstone batch 4 (V1 onwards): the run console

- Contract: `docs/capstone/batch4.md` (sections 33-39); decision: `docs/adr/0005-run-console.md`. Read only the sections your step prompt names.
- Shared tracing code lives in `src/governor/core/runtrace/`; `governor.build` and `governor.ask` import it, never each other or `governor.integrations`.
- Run logs, summaries, API responses and the UI carry counts, names, codes, statuses, durations, tokens and cost only: never a data value, question, SQL, answer, person's name, full path or secret.
- The front end lives in `apps/console/` (Node 20+, npm). Commit `package.json` and `package-lock.json`, never `node_modules/` or `dist/`. Run npm only inside `apps/console/`.
- Front-end tests are Vitest; Python tests stay offline. Use only original icons and artwork (inline SVG); no third-party logos.
