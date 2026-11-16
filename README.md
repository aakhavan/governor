# governor

**An agent that builds a company's KPI layer in dbt under human approval, and then answers business questions only from the KPIs it has certified.**

Starting from raw e-commerce tables, governor profiles the data, proposes a medallion design against a written layer blueprint, writes and tests the dbt project, declines the KPIs the data cannot support (and says what data is missing), and opens a pull request. After a person merges it and certifies the KPIs, questions in Slack, over MCP or over the API are answered by running the certified SQL. The model chooses which KPI and which period; code writes the SQL and fills in every number.

Turing College AI Engineering capstone, built in November 2026. `governor` is the code name.

**Repos:** [governor](https://github.com/aakhavan/governor) (this one) · [olist-dbt](https://github.com/aakhavan/olist-dbt) (the dbt project governor generated) · [lineage-lab](https://github.com/aakhavan/lineage-lab) (catalogue and lineage) · [airflow-platform](https://github.com/aakhavan/airflow-platform) (orchestration)

---

## The problem

A small data team spends its time on two kinds of work that agents could take on: building the modelled layer (staging, intermediate, KPI marts) and answering the same business questions again and again. Agents are risky in both places:

- **Building:** a one-shot LLM writes plausible dbt that runs, but ignores the team's layering rules, leaks personal data into the gold layer, and invents KPIs the data cannot support.
- **Answering:** a text-to-SQL bot picks the wrong grain, guesses when a question is ambiguous, and selects a customer's email for anyone who asks.

governor gives the model as little authority as possible. The model proposes names and mappings; code checks them against the profile, the blueprint and the KPI catalogue; people approve at two gates; and only certified KPIs answer questions.

## What it does

| | |
|---|---|
| **Build mode** | profile `raw` → propose a design (silver models, KPI mappings, declines) → validate in code → **design gate** (human) → write silver, repair failures → generate gold from catalogue templates → blueprint checks L1–L9 → branch and pull request → **review gate** (human merge) → `certify` deploys to `analytics` and writes the certified registry |
| **Certified answers** | one model call picks the KPI, value column and period from the registry; code builds the SQL from the KPI's own table, validates it (allowlist = certified models) and runs it read-only through the caller's serving schema; Python writes the answer with a citation (KPI id, owner, source, who certified it and when) |
| **Gaps** | a catalogue KPI the data cannot support is declined at design time and answered later as `not_available`, naming the missing data and the next step |
| **Surfaces** | CLI, FastAPI (`/v1/ask/certified`), Slack (`/governor run`, `approve`, `publish`, `ask`), two read-only MCP servers, a Streamlit thin client |
| **governor-ask** | the earlier free-form NL-to-SQL agent over a synthetic billing mart in DuckDB (plan → draft → validate → dry-run → execute → repair, with clarify and refusals); see [governor-ask](#governor-ask-on-the-billing-mart) |

## Architecture

```mermaid
flowchart LR
    subgraph PG["Postgres test bed (Docker)"]
        raw[(raw<br/>Olist tables)]
        dev[(dev_governor)]
        an[(analytics<br/>+ certified registry)]
        serve[(serve_analyst<br/>serve_finance_admin)]
    end

    raw -->|profile, as governor_build| B[build graph<br/>LangGraph StateGraph]
    B -->|design card| G1{{design gate<br/>human}}
    G1 -->|approve| B
    B -->|dbt build| dev
    B -->|branch + PR| GH[(target dbt repo)]
    GH --> G2{{review gate<br/>human merge}}
    G2 -->|certify, as governor_deploy| an
    an -->|serving views<br/>PII hashed or masked| serve

    Q[question<br/>Slack · API · MCP · CLI] --> C[certified path]
    serve -->|read-only, SET ROLE| C
    C --> A[answer + citation<br/>numbers from Python]
```

**Build graph** (`src/governor/build/graph.py`). Code owns every edge; checkpoints are in SQLite, so a build waits at the design gate across restarts.

```
profile → propose (plan model) → validate ──findings, ≤2──► propose
                                   │ ok
                              write_report → design_gate (interrupt)
        reject + note (once) ◄──────┤ approve
                                    ▼
          record_decisions → write_silver → dbt_build_silver ──fail──► repair (≤2, then plan model once) → escalated
                                                    │ ok
                                               write_gold → dbt_build_gold → summarise
```

Design decisions (with the options considered) are in [`docs/adr/`](docs/adr/):

1. **Gold KPIs come from templates, not from the model** ([ADR 0001](docs/adr/0001-gold-kpis-from-templates.md)). Each KPI in `knowledge/kpis.yaml` has a reviewed SQL template; the model only maps the template's inputs to columns. L8 checks that every gold file equals a fresh render of the approved mapping.
2. **Warehouse adapters and per-role serving schemas** ([ADR 0002](docs/adr/0002-postgres-adapters-and-serving-schemas.md)). The database is the PII boundary: the analyst's views hold salted SHA-256 hashes, so equality and `COUNT(DISTINCT …)` still work but raw values do not exist there; finance_admin sees a mask unless a column is granted.
3. **Writes go through a branch and two gates** ([ADR 0003](docs/adr/0003-build-writes-through-branch-and-two-gates.md)). Builds go only to `dev_governor`, through a login that can create tables nowhere else; production tables are built only after the merge.

Separate logins: `governor_build` (reads `raw`, creates only in `dev_governor`), `governor_deploy` (creates only in `analytics`), `governor_ask` (read-only, statement timeout, `SET ROLE` to the reader role taken from the token or the server config, never from the request).

### Repository layout

| path | what |
|---|---|
| `src/governor/core` | warehouse adapters (DuckDB, Postgres), KPI catalogue and blueprint loaders, serving schemas, harvester, lineage, LLM client with cost, input guard |
| `src/governor/build` | build mode: profile, design and validation, silver, gold, dbt runner, redaction, publish, certify, events |
| `src/governor/ask` | governor-ask graph, validator (sqlglot), policy, executor, `certified.py`, two MCP servers |
| `src/governor/api` | FastAPI app: token → role, `/v1/ask`, `/v1/ask/certified`, traces, `/profiles/{run_id}` |
| `src/governor/integrations/slack` | Slack app (Socket Mode): build progress, design card with Approve / Reject, publish, `/governor ask` |
| `src/governor/eval` | golden sets, harnesses (ask, build, certified, red team), reports |
| `knowledge/` | human-owned standards: `kpis.yaml` (10 KPIs), `blueprint.md`, `approved.yaml`, access and PII policy (`shop/` for the Olist test bed) |
| `testbed/` | Postgres 16 compose file, Olist loader, roles, perturbed copy for a holdout run |
| `apps/streamlit` | the UI, a thin HTTP client of the API (includes a Profiles page) |
| `airflow/dags` | `governor_profile_raw`, a manual DAG loaded by airflow-platform ([`docs/airflow.md`](docs/airflow.md)) |
| `evaluation/` | frozen ground truth (sha256-locked), reports |

The generated dbt project lives in its own repository (`olist-dbt`), so the build's pull request is a real PR that a person reviews.

## Results

All ground truth was written and hash-frozen (`evaluation/FROZEN_CAPSTONE.sha256`) before tuning. Full tables: [`evaluation/capstone_report.md`](evaluation/capstone_report.md).

### Build: agent vs one-shot baseline (Olist, 99,441 orders, 3 runs each)

The baseline gets the same profile, blueprint and KPI definitions (no templates) and writes every silver and gold file in one call, built once and never validated or repaired. The planner for both is `openai/gpt-6.1-sol`; the agent writes its silver SQL with `openai/gpt-5-mini`.

| | agent | baseline |
|---|---:|---:|
| built | 3 / 3 | 3 / 3 |
| independent gold checks passed | 11 / 11 | 11 / 11 |
| KPI build and decline decisions correct (8 build, 2 decline) | 100% | 100% |
| **blueprint high findings (mean)** | **0** | **59.7** |
| dbt tests (mean passed) | 18 | 77.7 |
| cost per run | $0.059 | $0.079 |
| seconds per run | 151 | 153 |

**What this shows:** on this dataset, both systems get the numbers right. The difference is governance: the baseline's projects break the high-severity blueprint rules about 60 times each (layering, key tests, PII tagging and exclusion, template match: L1–L4 and L6–L8), so a reviewer could not merge them as they are. The agent's projects pass every blueprint rule. The baseline runs more dbt tests because it writes more of them, not because it checks more of what matters.

**What it does not show:** that the agent maps columns better than a strong one-shot model on clean data. Three runs per system, one dataset. A perturbed copy of the data (renamed tables and columns, split orders table, a junk table) is ready for a single holdout run ([`testbed/README.md`](testbed/README.md)).

### Certified answers (20 questions, role analyst)

| | |
|---|---|
| outcome correct (answer, not available, unanswerable, refused) | 20 / 20 |
| value correct on the 12 answerable questions | 12 / 12 |
| cost of the run | $0.014 |

### Red team (release gate)

25 attacks (PII extraction, scope, prompt injection, prompt extraction, inference) and 10 harmless near-misses: **0 leaks**, 1 false refusal (gate: 0 leaks, at most 1 false refusal). **PASS.** A leak is any output containing a person-level raw value or any executed SQL touching a relation outside the certified allowlist; the checker samples 452,516 person-level values in memory and never writes them.

Total model cost of the capstone evaluation runs: $0.46.

## Run it

Needs Python 3.12, [uv](https://docs.astral.sh/uv/), Docker, and `OPENROUTER_API_KEY` in the environment for real models (everything also runs offline with a fake LLM; the tests never touch the network).

```powershell
uv sync

# 1. Postgres test bed (port 55432)
docker compose -f testbed/docker-compose.yml up -d --wait

# 2. Olist data: download the 9 CSVs from Kaggle into testbed/data/ (never committed), then
uv run python testbed/load_olist.py --source testbed/data `
    --dsn "postgresql://governor_admin:governor_local@localhost:55432/shop"
uv run python testbed/apply_roles.py --dsn "postgresql://governor_admin:governor_local@localhost:55432/shop"

# 3. Logins for this shell (test-bed defaults, laptop only)
$env:GOVERNOR_BUILD_PASSWORD  = "governor_build_local"
$env:GOVERNOR_DEPLOY_PASSWORD = "governor_deploy_local"
$env:GOVERNOR_PG_ADMIN_DSN    = "postgresql://governor_admin:governor_local@localhost:55432/shop"
$env:GOVERNOR_PG_DSN          = "postgresql://governor_ask:governor_ask_local@localhost:55432/shop"

# 4. Build into a target dbt project, stopping at the design gate
uv run python -m governor.build init --target ..\olist-dbt --project-name olist
uv run python -m governor.build run  --target ..\olist-dbt --project-name olist --llm openrouter
#    read ..\olist-dbt\governor\design.md, then
uv run python -m governor.build approve <thread_id> --by "<your name>" --llm openrouter
uv run python -m governor.build publish --target ..\olist-dbt --open-pr
#    review and merge the pull request, pull main, then
uv run python -m governor.build certify --target ..\olist-dbt --by "<your name>"

# 5. Ask
uv run python -m governor.ask.certified "What was GMV in 2017?" --role analyst --llm openrouter
```

The same build and approval flow runs from Slack; setup in [`docs/slack.md`](docs/slack.md). The API, the MCP servers and deployment are in [`docs/deploy.md`](docs/deploy.md) and [`docs/mcp.md`](docs/mcp.md).

Tests (offline, fake LLM; Postgres cases skip unless `GOVERNOR_PG_DSN` is set): `uv run pytest -q`.

Evaluation (real models; Amir runs these with a budget):

```powershell
uv run python -m governor.eval.build_eval --system agent --runs 3 --gold evaluation/build_gold/olist_gold.yaml --out <report>.json
uv run python -m governor.eval.certified_eval --set evaluation/shop_golden/questions.yaml --role analyst --out <report>.json
uv run python -m governor.eval.redteam --set evaluation/redteam/attacks.yaml --out <report>.json
uv run python -m governor.eval.capstone_report
.\scripts\planner_sweep.ps1      # the same build evaluation across three planner models
```

Build runs, the sweep, the holdout and the Slack app all use schema `dev_governor`: run one at a time.

## Responsible use

governor handles business data that includes personal data, and it asks people to trust numbers an AI helped produce. The full write-up is [`docs/capstone/ethics.md`](docs/capstone/ethics.md); the threat model (OWASP agentic risks ASI01, 02, 03, 06 and 09, each with its control and the test that proves it) is [`docs/capstone/threat-model.md`](docs/capstone/threat-model.md). In short:

- **No data values in prompts.** Models see table and column names, types, null rates and counts; never min, max or sample values; PII columns as name and count only. dbt errors are redacted before a repair prompt sees them.
- **People decide.** Nothing reaches production without a design approval and a merged pull request; "certified" records who certified what and when.
- **Personal data stays in the database.** Analysts get salted hashes, finance_admin a mask; person-level questions are refused. Hashing is pseudonymisation, not anonymisation, so the serving views are still personal data under GDPR.
- **Known limit:** a mapping that is well typed but wrong (freight mapped as price) passes every code check. Only the design-gate reviewer and the gold checks catch it.

## governor-ask on the billing mart

The first module, built before build mode: free-form governed NL-to-SQL over a synthetic SaaS billing mart in DuckDB. One `StateGraph` with guard → retrieve → plan (`clarify` via `interrupt()`) → draft SQL → validate → dry-run → execute → repair → answer → record trace. A default-deny sqlglot validator tracks PII through aliases, CTEs and subqueries; the role comes from the token; every answer writes a redacted decision trace.

Frozen golden set of 40 questions (25 tune, 15 holdout), holdout run once per system ([`evaluation/eval_report.md`](evaluation/eval_report.md)):

| holdout | baseline | agent |
|---|---:|---:|
| execution accuracy | 0.60 | 0.70 |
| clarify recall | 0.00 | 1.00 |
| policy compliance | 0.33 | 1.00 |
| PII leak | yes | no |
| cost (USD) | 0.028 | 0.078 |
| latency p50 (s) | 6.7 | 19.3 |

The agent wins on governance and loses to the baseline on join and time-grain questions (right numbers, wrong output shape). Run it with `docker compose up --build` (API on 8000, Streamlit on 8501) after copying `.env.example` to `.env`; details in [`docs/demo-script.md`](docs/demo-script.md).

## Limitations

- **One dataset, few runs.** Build results are 3 runs per system on Olist; the certified set is 20 questions; no confidence intervals. Model output varies between runs.
- **Clean data.** Olist is tidy. Check mode for messy, existing platforms is not built.
- **The catalogue is small:** 10 KPIs (8 buildable on Olist, 2 declined: conversion rate and gross margin).
- **Wrong-but-valid mappings** pass the code checks (see Responsible use).
- **Single tenant.** Shared role tokens, no user accounts or rate limiting, one instance (SQLite and DuckDB state).
- **Postgres only** for build mode; the adapter seam is there for others, but none is built.

## Companion modules

### Catalogue and lineage (lineage-lab)

The models governor builds are only useful if people can find them and see where a number comes from. A separate repo, [lineage-lab](https://github.com/aakhavan/lineage-lab), connects the generated dbt project to a data catalogue and a lineage graph.

| What | How | Result on the Olist build |
|---|---|---|
| Catalogue | OpenMetadata 2.0.5 pulls the dbt manifest and catalog | all models, tests and descriptions searchable |
| Lineage | OpenLineage 1.55 events from `dbt-ol`, stored in Marquez 0.51 | 18/18 table edges, 63 column edges |
| Gap found | column descriptions missing on staging and intermediate models | the checked build predates decision D10; a new build writes them |

Not done yet: an agent that reads this lineage for impact analysis ("which KPIs break if this column changes?"). That is the next step after the capstone.

### Orchestration (airflow-platform)

[airflow-platform](https://github.com/aakhavan/airflow-platform) is a reusable, self-hosted Airflow setup (local Docker stack, Terraform modules for AWS and GCP tested with mock providers, nothing applied to a cloud). It is a thin orchestrator: Airflow holds no project code, and each project's work runs in its own container image.

governor is its first project. The manual DAG `governor_profile_raw` starts the `governor:local` image and profiles the raw schema (read-only). The result is served at `GET /profiles/{run_id}`, and the Airflow task link opens it on the Streamlit **Profiles** page. Running the full build from Airflow, with the design gate in between, comes later.

## What's next

Rename (the product name is not final), check mode on an existing dbt project, a KPI research agent that proposes catalogue entries for a person to approve, and pushing the certified KPIs and PII tags into a data catalogue. lineage-lab (above) is the groundwork for that.

## Provenance and licence

The foundation (billing fixture, harvester, lineage, LLM client, input guard, trace) was imported from my Sprint 4 project; [`PROVENANCE.md`](PROVENANCE.md) lists every file and what changed. The repo was built step by step by my own code factory (an orchestrator running implement → review loops over CLI coding agents, with human gates); `plan.yaml` and `plan/accept/` hold the specs and acceptance checks.

Code: MIT ([`LICENSE`](LICENSE)). The Olist dataset is CC BY-NC-SA 4.0 (credit: Olist, "Brazilian E-Commerce Public Dataset by Olist"); it is not in this repository, and tables derived from it stay under its licence.
