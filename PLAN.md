# governor: an agentic data platform on one foundation (first module: governor-ask)

*Spec written 22 Oct 2026 in the Turing College Project; revised the same day after an independent review by GPT-5.6 Sol. Built by the code factory (`..\factory`). This file is the source of truth for this repo; step prompts never point here, they name files.*

**Seed:** factory `PLAN.md` §10 (governor-ask brief), `platform-kernel-thesis.md` (kernel/product split), `idea1-deep-track-plan.md` §4 (build ladder R1–R7), Sprint 4 build spec §3–§6 (fixture, metadata store, tools, PII rule).

---

## 1. What this repo is

A small, code-first "Databricks-lite" for a small data team: **one foundation** (warehouse fixture, catalog/metadata store, lineage, ownership, PII policy, LLM client, traces) and **modules** that put agents on top of it.

| Module | Status | What it does |
|---|---|---|
| `core` | G1 (imported from Sprint 4) | Billing mart fixture (dbt + DuckDB), harvester → `meta.duckdb`, lineage, owners, PII tags, OpenRouter client with cost, trace, input guard |
| `ask` (**governor-ask**) | G2a–G10b, this plan | Governed NL→SQL: retrieve → plan → clarify → draft → validate → dry-run → repair → safe execute → answer → decision trace. |
| `api` | G7 | FastAPI service: token → role, `/v1/ask`, resume, traces; Docker image; Streamlit (G8) and MCP (G9) are clients |
| `triage` | later (after the Sprint 4 defence) | The Sprint 4 incident-triage agent moved onto `core` |
| `maintainer` | capstone candidate (R7) | Semantic-layer maintainer: drift → proposed descriptions/classifications |

**Capstone stance (provisional until the capstone brief is available, adopted 22 Oct):**
- **In:** shared `core`; governed `ask`; frozen evaluation; decision traces; the API with token-derived roles; a one-container deployment.
- **Stretch:** MCP (G9, cut first if late); **one** triage workflow running on `core` (same policy, catalog, trace schema and API), added only after `ask` is deployed and evaluated.
- **Out:** `maintainer`, a Spider 2.0-DBT headline score, multi-agent orchestration, write-back, multiple warehouses, factory F4–F6.
- The story: one foundation, one policy, one trace schema and one API; governed analytics is the spine, triage is the proof that the foundation carries a second agent.

**Why one foundation:** the kernel thesis's swap test. If `ask` needs no changes to `core` beyond additions, the boundary is right.

---

## 2. Locked decisions

| # | Decision | Why |
|---|---|---|
| A1 | Python 3.12 + uv, single package `governor` with subpackages `core`, `eval`, `ask`, `api`. Streamlit app in `apps/streamlit/` as an HTTP client of the API. | One install, clear module boundaries for agents (one module per step); `serve/` from day one (kernel thesis §7). |
| A2 | Data = the Sprint 4 SaaS-billing mart (seed 42), imported by `scripts/import_foundation.ps1` after the Sprint 4 submission. One new mart, `fct_invoices`, added in G1. | One foundation for every module. Analysts query marts only, so invoices need a mart. |
| A3 | Engine DuckDB + dbt-duckdb, as Sprint 4. The warehouse is opened `read_only=True` by every query path. | Same as S4; read-only is enforced by the connection, not only by the validator. |
| A4 | Time is pinned: every relative date ("last quarter") resolves against `artifacts/green/as_of.txt`, never `now()`. The plan turns relative dates into literal bounds; the validator rejects volatile time functions (`VOLATILE_TIME`), so this holds for generated SQL too. The build time itself is pinned in `fixture/AS_OF` (G3; found at the G2b gate: the Sprint 4 build stamped the wall clock). | Workflow rubric Q4; Sol review 22 Oct. |
| A5 | **Python owns** the allowlist, policy decisions, SQL validation, dry-run, execution, row caps, lineage, freshness and every number in the answer. **The model owns** interpreting the question, the plan, the SQL draft and the wording. | Model never has the last word on a fact (Sprint 3 lesson). |
| A6 | Policy is data: `knowledge/policy.yaml` (column → PII tag, from S4) + `knowledge/access.yaml` (allowlist, roles, grants, caps), owned by Amir. Code reads them; prompts never restate them. | Changing policy is a data change with a review, not a prompt edit. |
| A7 | Roles: `analyst` (PII only inside `COUNT`/`COUNT(DISTINCT …)`; never selected, filtered, grouped, joined on) and `finance_admin` (PII output values masked as `'***'` unless a field-level grant exists). Masking is an outer projection around the query, so DISTINCT/GROUP BY/ORDER BY keep their meaning and raw PII never leaves DuckDB; counts of PII are numbers and stay unmasked. | Spec §10; Sol review 22 Oct (in-query masking changed DISTINCT semantics). |
| A8 | SQL validator = sqlglot (duckdb dialect): one statement, SELECT/WITH only, **default-deny relations** (allowlisted models or in-query CTEs only), no table-valued functions at all, no `SELECT *`, no volatile time functions, allowlisted columns, role policy by column lineage, LIMIT injected/capped. | Spec §10; `SELECT *` would hide PII from the column check; read-only DuckDB blocks writes, not file reads. |
| A9 | Models via OpenRouter, Sprint 3/4 client: `openai/gpt-5-nano` (guard flag, plan), `openai/gpt-5-mini` (draft SQL, repair, answer wording); structured output with ≥ 2048 max tokens. Embeddings as Sprint 3. | Model routing lesson; keys from the Windows env. |
| A10 | Graph = one LangGraph v1 `StateGraph`, code owns the edges; `interrupt()` for clarification; SqliteSaver checkpointer (`check_same_thread=False`). | Sprint 4 pattern, proven to resume across processes. |
| A11 | Decision trace = one row per question in `artifacts/traces.duckdb` (fields §5). Inspired by EU AI Act Art. 12, not a compliance claim. | Auditable answers are the governance headline. |
| A12 | Golden set (40 questions) and split (25 tune / 15 holdout) are frozen at G2b, before any agent prompt exists, and reviewed by Amir. Never relabelled from model output. Later steps cannot touch `evaluation/golden/` (scope guard). | Workflow rubric Q6. |
| A13 | The holdout is run once per system, logged in `evaluation/holdout_runs.log`; the harness refuses a second run without `--force-holdout`. | Honest numbers. |
| A14 | Every test and every acceptance check runs offline with fake/scripted LLMs. Only G10a/G10b call models (eval budget ≤ $3 in total). | Acceptance must be deterministic (factory §4). |
| A15 | Roles are derived on the server from a bearer token (`GOVERNOR_API_TOKENS`); request bodies cannot carry a role; threads and traces are scoped to the role. MCP's role is fixed per process by env. | A client-side role picker is a privilege escalation (Sol review). |

---

## 3. Layout

```
governor/
  PLAN.md AGENTS.md NOTES.md STATUS.md README.md PROVENANCE.md plan.yaml
  plan/prompts/G*.md   plan/accept/accept_g*.py  _common.py  _g5_cases.py   # locked by `factory lock`
  scripts/import_foundation.ps1                                          # HUMAN, after the S4 submission
  fixture/            generate_raw.py load_raw.py build_green.py billing_mart/   (from S4, + fct_invoices)
  knowledge/          owners.yaml policy.yaml (S4)  access.yaml (Amir)  metrics.yaml (G2a)
  src/governor/
    core/             paths.py warehouse.py llm.py security.py trace.py harvest.py lineage.py retrieval.py
    eval/             checker.py harness.py run.py pii.py                  (G2a–G3; generic, reusable by triage)
    ask/              baseline.py catalog.py retrieval.py validator.py policy.py executor.py
                      schemas.py graph.py run.py service.py mcp_server.py prompts/*.md
  src/governor/api/   app.py                                            (G7: FastAPI, auth)
  apps/streamlit/     client.py app.py pages/                           (G8: thin HTTP client)
  Dockerfile docker-compose.yml .env.example docs/deploy.md             (G7)
  evaluation/         golden/{questions.yaml,split.json,FROZEN.sha256}  reports/  eval_report.md  holdout_runs.log
  artifacts/          (git-ignored) green/ meta.duckdb catalog_cards.jsonl traces.duckdb checkpoints.sqlite
  tests/              core/ eval/ ask/ ui/ mcp/
```

`governor.core.paths` resolves every path from the repo root (override `GOVERNOR_ROOT`). `governor.core.warehouse.connect()` is the only way to open the warehouse: read-only, `search_path` on the marts schema. Nothing hard-codes a Sprint 4 or Windows path.

---

## 4. The graph (G6a/G6b)

```
guard → retrieve_context → plan → [clarify: interrupt()] → draft_sql → validate → dry_run
                                                              ↑            │fail       │fail
                                                              └─ repair ←──┴───────────┘   (≤ 2 repairs, then refuse)
      → execute (read-only, row cap, timeout) → answer → record_trace → END
policy refusal (validate says the role may not see it) → answer(refusal) → record_trace
unanswerable (plan finds no catalog support) → answer("not in this data") → record_trace
```

- `guard`: Sprint 3/4 regex screen + nano flag; refusals never echo input.
- `retrieve_context`: catalog cards (models, columns with PII tags, tests, owners, grain), metric cards (`metrics.yaml`); BM25 + dense, RRF (G4).
- `plan`: structured `QueryPlan{intent: answer|clarify|unanswerable, models, metrics, grain, filters, time_range, missing_slots}`.
- `answer`: the model writes wording with placeholders; Python fills every number from the result rows. Shows SQL, models used, upstream lineage (from `core.lineage`), source freshness (vs `as_of`), cost.

## 5. Decision trace row

`trace_id, ts, role, question_hash, question_len, retrieved_ids, plan_json, sql_attempts[{sql, validator_ok, reasons, dry_run_ok, error}], policy_decisions, executed_sql, row_count, result_hash, answer, outcome (answered|clarified|refused|unanswerable|error), models, tokens_in, tokens_out, cost_usd, latency_s, human_feedback`.

The question text itself is stored only when `GOVERNOR_TRACE_TEXT=1` (default: length + hash, as Sprint 3 logs).

---

## 6. Evaluation (the headline)

- **Golden set** (`evaluation/golden/questions.yaml`, 40 questions over the marts, `as_of` recorded):

  | Category | n | Correct behaviour |
  |---|---|---|
  | simple | 6 | answer |
  | join | 6 | answer |
  | time_grain | 6 | answer (relative dates vs `as_of`) |
  | metric | 6 | answer, using the `metrics.yaml` definition |
  | ambiguous | 5 | clarify (names the missing slot) |
  | policy | 6 | refuse / aggregate / mask, by role (both roles present) |
  | unanswerable | 5 | "not in this data" |

- **Split:** 25 tune / 15 holdout, stratified, frozen with `FROZEN.sha256`.
- **Metrics:** execution accuracy (result sets equal ignoring row order unless `order_matters`, column order ignored, numeric relative tolerance); valid-SQL rate first try vs after repair; clarification precision/recall; policy compliance (**any PII leak fails the whole run**); cost and latency.
- **Systems:** `baseline` (one-shot prompt with the full schema pasted in, no retrieval, no validator, executed read-only) vs `agent` (the graph). Harness self-test systems: `oracle` (gold behaviour → all metrics 1.0), `null` (refuses everything), `leaky` (selects PII → run fails).
- **Honest limit:** the catalog is small (~15 nodes), so retrieval recall is easy here; the real retrieval test is a bigger warehouse (Spider 2.0-DBT subset or a Contoso-scale mart, later, R5).

---

## 7. Steps (factory)

| Step | What | Tier | Gate |
|---|---|---|---|
| G1 | Foundation from the S4 import: package `governor.core`, `warehouse.connect()`, green build, `fct_invoices`, harvester → `meta.duckdb`, tests, provenance | mechanical | — |
| G2a | `metrics.yaml`, golden-set loader, result checker | design | — |
| G2b | 40 golden questions + gold SQL, frozen split, review table | design | **HUMAN (ground truth)** |
| G3 | Eval harness + metrics + self-test systems; baseline | design | — |
| G4 | Catalog + metric cards, hybrid retrieval, recall@k on gold tables | mechanical | — |
| G5a | SQL validator (default-deny, volatile time, PII lineage, outer-projection masking) and role policy | design | — |
| G5b | Dry-run and read-only executor (external access off) | design | **HUMAN (security)** |
| G6a | The graph, in-memory: plan, clarify interrupt, draft, validate, repair, answer from results | design | — |
| G6b | Persistence (SqliteSaver), decision traces, CLI with resume, agent system in the harness | design | — |
| G7 | API: token → role, `/v1/ask`, resume, traces; Dockerfile + compose; deploy doc | design | **HUMAN (security)** |
| G8 | Streamlit as a thin client over the API | mechanical | — |
| G9 | MCP server, 5 read-only tools (**stretch, cut first**) | mechanical | — |
| G10a | Tune on the tune split, freeze prompts | design | — |
| G10b | Holdout once; eval report; README; demo script | design | **HUMAN (release)** |

Default roles come from `%USERPROFILE%\.factory\agents.yaml` (design: claude-tc-opus implements, cursor-grok reviews; mechanical: cursor-composer implements, claude-tc-sonnet reviews). Cut order if late: G9, then the triage stretch, then G4's dense mode; never G2b, G5a/b, G7 auth or G10b.

---

## 8. HUMAN steps outside the factory

1. **After the Sprint 4 submission:** `powershell -ExecutionPolicy Bypass -File scripts\import_foundation.ps1` from this repo. It copies only the listed files, never `.env`, data or `artifacts/`, and writes `PROVENANCE.md`. Paste its summary into NOTES.
2. Review `knowledge/access.yaml` (it is yours) and commit.
3. Factory F3 must be done; then `factory plan validate plan.yaml`, `factory lock`, `factory run --until-gate`.
4. Gates: G2b (read all 40 gold SQLs against `evaluation/golden/REVIEW.md` and the metric definitions), G5b (read the validator's codes on the locked cases and try two attacks of your own), G7 (call the API with two tokens; try a role in the body), G10b (read the report and README).
5. **Walkthrough before every approve** (Sol review 22 Oct): write `docs/walkthroughs/<step>.md`, 10–20 lines in your own words: the design of what changed, one request traced through the code, and one known limitation. This is what makes factory-built code defensible in a mentor review or an interview.

## 9. Open questions

- **The capstone brief** (opens after the agents sprint is submitted): confirm the rubric, deployment surface, auth expectations, permitted reuse of sprint code, mentor checkpoints and submission date, then replace the provisional stance in §1.
- Hosting for G7 (VM, Fly.io, Render, Cloud Run): decided after the brief.

- Does `int_invoices_with_payments` carry everything `fct_invoices` needs? (G1 finds out; the mart may need a join to `dim_accounts` for country.)
- Exact Sprint 4 file names may differ from the S4 spec §2; the import script reports what it found.
- Langfuse or FastAPI `serve/` boundary: not in this plan (capstone).

## Capstone phase (from 2 Nov 2026)

Steps C1 onward implement the capstone design agreed on 2 Nov 2026. Their contracts are in `docs/capstone/design.md`, the vocabulary in `CONTEXT.md` and the decisions with trade-offs in `docs/adr/`. Step prompts name the sections each step needs.
