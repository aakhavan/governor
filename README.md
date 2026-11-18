# governor

**An agent that builds a company's KPI layer in dbt under human approval, then answers business questions only from the KPIs a person has certified.**

![The model proposes. Code checks. People decide.](docs/showcase/00-cover.png)

**Goal.** Small data teams spend much of their time building the modelled layer of their warehouse and answering the same business questions again and again; agents could take both jobs, but a one-shot model ignores the team's rules, leaks personal data and invents numbers. governor lets an agent do the work while keeping it governed: the model only proposes a design and picks KPIs, code validates everything against a written blueprint and KPI catalogue, people approve at two gates, and answers come only from certified KPIs, computed by SQL that code writes.

governor profiles raw tables, proposes a medallion design against a written layer blueprint, writes and tests the dbt project, declines the KPIs the data cannot support (naming the missing data), and opens a pull request. After a person merges it and certifies the KPIs, questions from Slack, MCP or the API are answered by running the certified SQL: the model picks the KPI and the period, code writes the SQL and fills in every number.

Turing College AI Engineering capstone, November 2026. The 7-step walkthrough is in [`docs/showcase/`](docs/showcase/).

**Repos:** [governor](https://github.com/aakhavan/governor) · [olist-dbt](https://github.com/aakhavan/olist-dbt) (a generated dbt project) · [lineage-lab](https://github.com/aakhavan/lineage-lab) (catalogue and lineage) · [airflow-platform](https://github.com/aakhavan/airflow-platform) (orchestration)

## The problem

Agents could take over two jobs of a small data team: building the modelled layer and answering repeated business questions. Both are risky:

- **Building:** a one-shot model writes dbt that runs but ignores the team's layering rules, leaks personal data into gold, and invents KPIs the data cannot support.
- **Answering:** a text-to-SQL bot picks the wrong grain, guesses on ambiguous questions, and returns personal data to anyone who asks.

governor gives the model as little authority as possible: it proposes names and mappings, code checks them against the profile, the blueprint and the KPI catalogue, people approve at two gates, and only certified KPIs answer questions.

## What it does

| | |
|---|---|
| **Build** | profile `raw` → propose a design → validate in code → **design gate** (human) → write and repair silver → gold from catalogue templates → blueprint checks → pull request → **review gate** (human merge) → `certify` |
| **Answer** | the model picks KPI and period from the certified registry; code builds, validates and runs the SQL read-only in the caller's serving schema; the answer cites the KPI, its owner and who certified it |
| **Gaps** | a KPI the data cannot support is declined at design time and later answered as `not_available`, with the missing data and the next step |
| **Surfaces** | CLI, FastAPI, Slack (`/governor run`, `approve`, `publish`, `ask`), two read-only MCP servers |

## Architecture

```mermaid
flowchart LR
    subgraph PG["Postgres"]
        raw[(raw)]
        dev[(dev_governor)]
        an[(analytics<br/>+ certified registry)]
        serve[(serving views<br/>per role)]
    end

    raw -->|profile, as governor_build| B[build graph<br/>LangGraph StateGraph]
    B -->|design card| G1{{design gate<br/>human}}
    G1 -->|approve| B
    B -->|dbt build| dev
    B -->|branch + PR| GH[(target dbt repo)]
    GH --> G2{{review gate<br/>human merge}}
    G2 -->|certify, as governor_deploy| an
    an -->|PII hashed or masked| serve

    Q[question<br/>Slack · API · MCP · CLI] --> C[certified path]
    serve -->|read-only, SET ROLE| C
    C --> A[answer + citation]
```

**Build graph** (`src/governor/build/graph.py`). Code owns every edge; checkpoints are in SQLite, so a build waits at the design gate across restarts.

```
profile → propose → validate ──findings, ≤2──► propose
                       │ ok
                  write_report → design_gate (interrupt)
reject + note (once) ◄──┤ approve
                        ▼
record_decisions → write_silver → dbt_build_silver ──fail──► repair (≤2) → escalated
                                        │ ok
                                   write_gold → dbt_build_gold → summarise
```

Design decisions, with the options considered, are in [`docs/adr/`](docs/adr/):

1. **Gold KPIs come from reviewed SQL templates, not from the model** ([ADR 0001](docs/adr/0001-gold-kpis-from-templates.md)). The model only maps template inputs to columns; a blueprint check proves every gold file equals a fresh render of the approved mapping.
2. **The database is the PII boundary** ([ADR 0002](docs/adr/0002-postgres-adapters-and-serving-schemas.md)). Each reader role gets its own serving views: salted hashes for analysts, masks for finance unless a column is granted.
3. **Writes go through a branch and two gates** ([ADR 0003](docs/adr/0003-build-writes-through-branch-and-two-gates.md)). Separate logins: `governor_build` creates only in `dev_governor`, `governor_deploy` only in `analytics`, `governor_ask` is read-only with `SET ROLE` taken from the token, never from the request.
4. **Build mode rebuilds from raw on every run.** A rerun is safe, because nothing reaches a stakeholder without a design approval, a merged pull request and certification, but it is not incremental. Maintain mode (compare the new profile with the last one, skip the model call when nothing changed, open a pull request with only the diff) was added after submission ([ADR 0004](docs/adr/0004-maintain-mode-and-tenancy.md), see [the last section](#after-submission-maintain-mode-and-tenants)).

### How it applies the course

| Technique | In governor |
|---|---|
| Agent orchestration | LangGraph `StateGraph`s where code owns every edge; `interrupt()` for the human gate; SQLite checkpoints, so approval survives a restart |
| Structured output | every model call returns JSON-schema-validated output (Pydantic); no free-text parsing |
| Prompt engineering | prompts are versioned files; the model sees names, types and counts, never data values; validation findings are fed back for a bounded repair (at most 2) |
| Model routing | a strong planner model for the design, a small model for writing silver SQL |
| Memory | short term: graph checkpoints; long term: approved decisions per company, reused by later builds |
| Tools | Postgres profiling, dbt runner, git and GitHub pull requests, Slack, MCP servers, OpenRouter |
| Retrieval | governor-ask: hybrid BM25 + dense search with reciprocal rank fusion; the certified path needs none, because answers are exact numbers from certified tables |
| Evaluation | frozen golden sets, a one-shot baseline, a red-team release gate |

| path | what |
|---|---|
| `src/governor/build` | build mode: profile, design and validation, silver, gold, dbt runner, publish, certify |
| `src/governor/ask` | certified answers, the governor-ask agent, SQL validator, MCP servers |
| `src/governor/core` | warehouse adapters, KPI catalogue and blueprint loaders, serving schemas, LLM client |
| `src/governor/integrations/slack` | Slack app (Socket Mode) |
| `src/governor/eval` | golden sets, harnesses, reports |
| `knowledge/` | human-owned standards: KPI catalogue, layer blueprint, approved decisions, PII and access policy |
| `testbed/` | Postgres compose file, loaders, roles |

## Data

The test bed is the public Olist Brazilian e-commerce dataset (real, anonymised; 9 related tables), loaded unchanged into a `raw` schema as text, so typing and cleaning happen in the silver layer governor builds. Tests use a small synthetic sample with the same tables and the edge cases that matter (duplicate customers, cancelled orders, split payments). Data never enters the repository or a prompt.

## Results

Measured on the Olist test bed against frozen, hash-locked ground truth ([`evaluation/capstone_report.md`](evaluation/capstone_report.md) has the full tables, costs and timings).

| | agent | one-shot baseline |
|---|---:|---:|
| gold values correct | 11 / 11 | 11 / 11 |
| KPI build and decline decisions correct | 100% | 100% |
| **blueprint high-severity findings per run** | **0** | **~60** |

Both systems get the numbers right; only the agent's projects follow the layering, key-test and PII rules, so only they could be merged as they are. Certified answers: 20 / 20 correct outcomes. Red team (25 attacks, 10 near-misses): **0 leaks**, 1 false refusal; the release gate passes.

A second dataset (a retail chain: sales, products, stores, inventory, with its own KPI catalogue) built end to end from Slack, after two bugs it exposed were fixed in code, with tests: a missing `sources.yml` on a fresh target, and model-qualified column names in KPI mappings.

## Run it

Needs Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, and `OPENROUTER_API_KEY` for real models (tests run offline with a fake LLM).

```powershell
uv sync
docker compose -f testbed/docker-compose.yml up -d --wait          # Postgres on port 55432

# Olist data: the 9 Kaggle CSVs in testbed/data/ (never committed), then
uv run python testbed/load_olist.py --source testbed/data --dsn "postgresql://governor_admin:governor_local@localhost:55432/shop"
uv run python testbed/apply_roles.py --dsn "postgresql://governor_admin:governor_local@localhost:55432/shop"

$env:GOVERNOR_BUILD_PASSWORD  = "governor_build_local"
$env:GOVERNOR_DEPLOY_PASSWORD = "governor_deploy_local"
$env:GOVERNOR_PG_ADMIN_DSN    = "postgresql://governor_admin:governor_local@localhost:55432/shop"
$env:GOVERNOR_PG_DSN          = "postgresql://governor_ask:governor_ask_local@localhost:55432/shop"

uv run python -m governor.build init    --target ..\olist-dbt --project-name olist
uv run python -m governor.build run     --target ..\olist-dbt --project-name olist
uv run python -m governor.build approve <thread_id> --by "<your name>"     # after reading governor/design.md
uv run python -m governor.build publish --target ..\olist-dbt --open-pr
uv run python -m governor.build certify --target ..\olist-dbt --by "<your name>"   # after the merge, on an up-to-date main

uv run python -m governor.ask.certified "What was GMV in 2017?" --role analyst
```

- **Slack:** the same flow, set up as in [`docs/slack.md`](docs/slack.md). API, MCP and deployment: [`docs/deploy.md`](docs/deploy.md), [`docs/mcp.md`](docs/mcp.md).
- **Another dataset:** point `GOVERNOR_ROOT` at a folder with its own `knowledge/`, and `GOVERNOR_PG_PORT` at its own database.
- **Tests:** `uv run pytest -q` (offline). **Evaluation** (real models): `governor.eval.build_eval`, `certified_eval`, `redteam`, then `capstone_report`; build runs and the Slack app share schema `dev_governor`, so run one at a time.

## Responsible use

Full write-up: [`docs/capstone/ethics.md`](docs/capstone/ethics.md); threat model with a control and a test per risk: [`docs/capstone/threat-model.md`](docs/capstone/threat-model.md).

- **No data values in build or answer prompts:** names, types and counts only; dbt errors are redacted before a repair prompt.
- **People decide:** nothing reaches production without a design approval and a merged pull request; certification records who and when.
- **Personal data stays in the database:** hashed or masked by role; person-level questions are refused. Hashing is pseudonymisation, so the serving views remain personal data under GDPR.
- **Known limit:** a mapping that is well typed but wrong passes every code check; only the design-gate reviewer and the gold checks catch it.

## Limitations

- **No outside users yet**; tested by the author as the target user, end to end through Slack.
- **Few runs, two datasets**; model output varies between runs.
- **Maintain mode watches the raw schema only**: a hand edit to a generated model is not detected, and `force` restores it.
- **Wrong-but-valid mappings** pass the code checks.
- **Postgres only** for build mode; `ask` and the certified registry serve one tenant.

## Companion modules and earlier work

- **[lineage-lab](https://github.com/aakhavan/lineage-lab):** the generated dbt project in OpenMetadata and OpenLineage (Marquez). Next: an agent that answers "which KPIs break if this column changes?".
- **[airflow-platform](https://github.com/aakhavan/airflow-platform):** a reusable Airflow setup; the `governor_profile_raw` DAG profiles the raw schema.
- **governor-ask:** the first module, free-form governed NL-to-SQL over a synthetic billing mart ([`evaluation/eval_report.md`](evaluation/eval_report.md)).

## Provenance and licence

Built step by step by my own code factory (implement → review loops over CLI coding agents, with human gates); foundation files from my Sprint 4 project are listed in [`PROVENANCE.md`](PROVENANCE.md).

Code: MIT ([`LICENSE`](LICENSE)). The Olist dataset is CC BY-NC-SA 4.0 (credit: Olist, "Brazilian E-Commerce Public Dataset by Olist"); it is not in this repository, and values derived from it, including [`evaluation/build_gold/`](evaluation/build_gold/NOTICE.md) and [`evaluation/shop_golden/`](evaluation/shop_golden/NOTICE.md), stay under that licence.

## After submission: maintain mode and tenants

Added on 17–18 Nov 2026, after the capstone was submitted. Built by the same factory in six reviewed steps, and run end to end from one Slack bot serving three datasets as tenants: retail, education and short-term rentals (Inside Airbnb Berlin). Decision and options: [ADR 0004](docs/adr/0004-maintain-mode-and-tenancy.md).

| | |
|---|---|
| **Idempotent reruns** | At approval, governor stores a fingerprint of the raw schema: table and column names, inferred types, PII flags and candidate keys, never counts or values. A later run with the same fingerprint and a finished build ends as `up_to_date`, with no model call and no dbt run. `run <target> force` designs again. |
| **Drift-aware design** | When the fingerprint differs, the planner gets the last approved design and the list of changes, and is told to change only what they require. The design report lists the changes; both human gates stay. |
| **Safer publish** | `publish` fetches `origin/main`, fast-forwards a local `main` that is only behind, refuses one that has diverged, and makes no commit when the build matches `main`. |
| **Safety rails** | Every database connection gives up after `GOVERNOR_PG_CONNECT_TIMEOUT` seconds (default 10); the Slack bot shows the knowledge folder and the database (`host:port/db`) it serves. |
| **Tenants** | One registry file (`GOVERNOR_TENANTS`) lists tenants, each with its own knowledge folder, run state, dbt repository and database. The build, the CLI (`--tenant`), `certify` and one Slack bot route every command to exactly one tenant; tests check that a run never reads another tenant's knowledge, state or database. See [`docs/tenants.md`](docs/tenants.md). |

Seen on the retail dataset: a rerun with no change ended `up_to_date` in seconds, and publishing the merged build again made no commit. The education dataset added two code checks before the design gate: keys of three columns, and casts that the raw values cannot hold.
