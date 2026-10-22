# AGENTS.md: rules for every agent in this repo

This repo is **governor** (core + ask modules), built step by step by the code factory. Your step prompt names the files you need; read those, not whole documents.

## Hard rules
- **Never commit, push, branch or stash.** The factory commits.
- **Never read `.env` or `.env.*`**, never print, log or echo keys or env values. Keys are read by name from the environment (`OPENROUTER_API_KEY`).
- **Change only the paths your step allows** (plus `NOTES.md`). Never edit `plan/` (locked) or, from G3 on, `evaluation/golden/`.
- Never read the Turing College folders. Everything from Sprint 4 is already in this repo (see `PROVENANCE.md`).
- `knowledge/access.yaml` and `knowledge/policy.yaml` are human-owned policy. Code reads them; prompts never restate them.
- Python 3.12 + uv. LangChain v1 / LangGraph v1 only: no `AgentExecutor`, no `langchain_classic`, no `create_react_agent`.
- Prompts live in `src/governor/ask/prompts/*.md`, never in code strings. Pydantic for every model output and tool argument.
- Time: resolve relative dates against `artifacts/green/as_of.txt`. Never `now()`, `current_date` or `datetime.now()` in data logic.
- Tests run offline: fake or scripted LLMs, no network. Only the G9 evaluation calls real models.
- DuckDB: open the warehouse `read_only=True`; close every connection (Windows file locks).

## Golden set (from G3 on)
- Never read `evaluation/golden/questions.yaml` to write prompts, examples or tests. Code loads it through `governor.eval`; tests use their own small fixtures.
- Never copy golden questions or gold SQL into prompts. The acceptance scripts check for overlap.

## Never read whole (query or skip instead)
- `uv.lock`, `artifacts/**` (`manifest.json`, `catalog.json`, `run_results.json`, `sources.json`, `*.duckdb`, `*.sqlite`), `fixture/billing_mart/target/`, `.factory/`, `NOTES-archive.md`, any data file over 200 KB. Use `duckdb` with `LIMIT`, or `python -c` with `json` and a key filter.

## Output rules
- Quiet commands: `uv run pytest -q`; dbt logs to a file; print summaries only.
- Paste results, not logs.

## Coordination
- `NOTES.md`: current state, open questions, last two steps' result + additions. Under 150 lines. Add a short "Gn result" when you finish.
- `PROVENANCE.md`: every file imported from Sprint 4, with its source and what was changed.
