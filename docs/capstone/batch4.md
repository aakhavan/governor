# Batch 4: the run console (sections 33–39)

*Written by Claude on 20 Nov 2026 for the factory (steps V1–V6). Decision: `docs/adr/0005-run-console.md`. Background: `claude/governor-showcase-plan.md` in the Turing project (the Astraeus comparison).*

## 33. Goal and rules

**Goal:** show governor's agents working, live, the way a hiring manager understands in ten seconds. The output is a web console that draws each LangGraph graph (build and ask) as a node canvas. Every node lights up while it runs and shows a one-line result, a duration and a retry count. Below the canvas are result views: lineage, the build funnel, KPI evidence, and the guard path of an ask. A saved run can be replayed with no model calls, so a demo never depends on a live API.

**Rules for the whole batch:**

1. **No behaviour change when the console is unused.** Every graph's outputs and its existing events (`build/events.py`, ask traces) and every existing test stay exactly as they are. Tracing is additive: it writes a separate run log and never raises into the graph.
2. **No data values anywhere new.** Run logs, summaries, the API and the UI carry only counts, names of tables/models/KPIs/nodes, codes, statuses, durations, tokens and cost. Never a cell value, a question's text, an answer's text, SQL text, a person's name or a secret. Tests prove it with a marker string (as in batch 2d).
3. **Package boundaries hold.** `governor.build` and `governor.ask` never import each other or `governor.integrations`. Shared tracing code lives in `governor.core.runtrace`. The API router and the LangGraph Studio entry points live in `governor.integrations`, which may import both.
4. **Code owns every edge.** The graphs' wiring does not change. Wrapping a node must keep its signature and its return value.
5. **`evaluation/`, `knowledge/` and the golden set are untouched.** Tests run offline: fake LLMs, fake dbt runners, no network.
6. **Front end lives in `apps/console/`**: Vite + React 18 + TypeScript (strict). It builds with `npm ci && npm run build` on Windows and Linux with Node 20+. It has no Python-side dependency.

## 34. The run-event contract (V1)

A **run** is one invocation of a graph thread: a build thread (`thread_id`) or an ask thread. A run log is a JSON-lines file: `GOVERNOR_STATE_DIR/runs/<graph>/<run_id>.jsonl` (`graph` is `build` or `ask`). A resumed thread (approve/reject at the design gate, or a clarify answer) appends to the same file.

**Each line is one event:**

| Field | Type | Meaning |
|---|---|---|
| `v` | int | contract version, `1` |
| `ts` | str | UTC ISO-8601 with milliseconds |
| `run_id` | str | the thread id |
| `graph` | str | `build` or `ask` |
| `seq` | int | 1, 2, 3 … per run, strictly increasing. A new process reads the last line to continue the count |
| `type` | str | `run_started`, `node_started`, `node_finished`, `node_failed`, `run_paused`, `run_resumed`, `run_finished` |
| `node` | str or null | node id for node events and `run_paused` |
| `attempt` | int or null | how many times this node has started in this run (1 = first time). Drives the ×N badge |
| `duration_ms` | int or null | on `node_finished` and `node_failed` |
| `summary` | str or null | ≤ 80 characters; counts, names and codes only (section 35) |
| `status` | str or null | on `run_paused` (`awaiting_approval`, `awaiting_clarification`) and `run_finished` (the graph's final status, e.g. `built`, `escalated`, `design_invalid`, `up_to_date`, `answered`, `refused`) |
| `metrics` | object or null | flat, numbers only: `llm_calls`, `tokens_in`, `tokens_out`, `cost_usd` (cost may be null when unknown) |
| `error_code` | str or null | on `node_failed`: the exception class name only, never its message |

**Writer (`governor.core.runtrace`):**

- `RunLog(graph, run_id)` with `emit(type, **fields)`. It appends one line, validates the fields against the table above (unknown fields dropped; strings cut to the limits; `metrics` keeps numeric values only) and **never raises**: a write failure is logged once and the run goes on.
- `traced(graph, node_id, fn, summarise)` wraps a node function. It keeps the signature: `(state)` or `(state, config)`, sync. It emits `node_started`, calls `fn`, then emits `node_finished` with `summary = summarise(update, state)` and `metrics` from the LLM calls the update adds (the `calls` list in build; the equivalent in ask). An exception emits `node_failed` and is re-raised unchanged.
- **Interrupts are not failures.** LangGraph's `GraphInterrupt` (raised by `interrupt()`) emits `run_paused` with the node and a status, then is re-raised. On resume the node starts again (attempt +1). A `run_resumed` event comes first, emitted by the resume entry point.
- `run_started` / `run_finished` are emitted by the graph entry points around `invoke`: `build.graph.start` and `_resume` for build, and `ask.checkpoints.invoke` (the one funnel every ask call goes through) for ask. `run_finished` is emitted only when the thread ends, not when it pauses.
- **Turning it off:** `GOVERNOR_RUNTRACE=0` turns all writing off (default on). The run id comes from the LangGraph config (`configurable.thread_id`); the wrapper reads it from `config` when the node takes one, else from a context variable set by the entry point.

**Reader / reducer (`governor.core.runtrace.fold`):** `fold(events) -> RunView`. This is the single source of truth for what the UI shows. The TypeScript reducer in V4 must match it exactly.

- Events are applied in `seq` order; a duplicate `seq` is ignored.
- **Node states:**

  | Event | Node state becomes |
  |---|---|
  | `node_started` | `running`; attempts +1 |
  | `node_finished` | `done`; durations add up; summary kept |
  | `node_failed` | `failed`; error code kept |
  | `run_paused` on the node | `paused` |
  | after `run_finished`, a node that never started | `skipped` |

  The state before any event is `pending`.
- **Run state:** `running`, then `paused` (with the status), then `finished` (with the final status). It is `failed` if a `node_failed` is never followed by a later `node_started`, and the run ends or the log stops.
- **Run totals:** `elapsed_ms` (first to last event), `llm_calls`, `tokens_in`, `tokens_out` and `cost_usd` summed over `node_finished` metrics. Cost is null if any call's cost is null. Also `current_node`, the last node that is `running` or `paused`.
- **Parity:** shared cases live in `tests/fixtures/console/fold_cases.json` (input events → expected view). At least 8 cases:
  1. empty;
  2. straight run;
  3. repair loop with attempt 2;
  4. pause, then resume, then finish;
  5. a failed node;
  6. a duplicate and an out-of-order seq;
  7. an up-to-date run that skips most nodes;
  8. unknown cost.

  Python and TypeScript tests both load this file.

## 35. Node registry and topology (V1 build, V2 ask)

**`governor.core.runtrace.registry`:** one `NodeSpec` per graph node.

| Field | Content |
|---|---|
| `id` | the graph's node id |
| `label` | a short title |
| `kind` | `guard`, `llm`, `check`, `dbt`, `gate`, `io`, `summary` (the UI colours by kind) |
| `description` | ≤ 100 characters of plain English for the hover tooltip ("Asks the model to propose silver models and KPI mappings.") |
| `group` | build: `design`, `silver`, `gold`; ask: `understand`, `sql`, `answer` |
| `order` | int |
| `planned` | default false. A planned node is drawn dashed ("coming soon") and never appears in a run |

Each graph also has **edge labels**: `{(source, target): label}` for every conditional edge, in plain words. Build examples: `compare→END` "up to date", `validate→propose` "findings: repair", `design_gate→propose` "rejected", `dbt_build_silver→repair_silver` "test failed", `silver_done→END` "escalated". Ask: `guard→record_trace` "blocked", `validate→repair` "refused: repair", `plan→clarify` "unclear".

**`topology(graph) -> dict`:** `{graph, nodes: [registry fields + start/end], edges: [{source, target, label, conditional}]}`. It is built from the compiled graph's `get_graph()` using stub dependencies: a fake LLM and no checkpointer, no network, no database. Edge labels come from the registry. The `__start__`/`__end__` nodes are mapped to `start`/`end` with kind `io`.

**Tests:**

- every compiled node has a registry entry, and every registry entry (except planned ones) is a compiled node;
- every conditional edge has a label.

**Summaries** (`summarise(update, state)` per node): ≤ 80 characters, counts, names and codes only. What each build node must say, in short form; the exact wording is free:

| Node | Says | Node | Says |
|---|---|---|---|
| profile | tables · columns · PII columns | silver steps | models written / tests passed of total / repair N for <model> |
| compare | no fingerprint / changed: N / up to date | silver_done | silver built / escalated |
| propose | KPIs · models proposed | write_gold | KPIs built · gaps |
| validate | ok / N findings: CODES | dbt_build_gold | tests passed |
| design_gate | approved / rejected (never the person) | summarise | final status · cost |

Ask nodes:

| Node | Says |
|---|---|
| guard | ok / blocked: CODE |
| retrieve_context | tables · metrics found |
| plan | intent label |
| clarify | asked |
| draft_sql | drafted |
| validate | ok / refused: CODES |
| dry_run | ok / CODE |
| execute | N rows |
| repair | repair N |
| answer | answered |
| record_trace | saved |

**No SQL text, question text or values.**

## 36. Console API and LangGraph Studio (V3)

**A router in `governor.integrations.console`**, mounted by `governor.api.app.create_app` under `/v1/console`. Every route is read-only.

- **Auth:** any role from the existing bearer token. `GOVERNOR_CONSOLE_OPEN=1` allows the routes without a token, for local dev and the public replay demo. It is off by default, and the existing `/v1/ask` routes stay protected either way.
- **CORS:** only the origins in `GOVERNOR_CONSOLE_ORIGINS` (comma-separated). Default `http://localhost:5173,http://127.0.0.1:5173`.

| Route | Returns |
|---|---|
| `GET /graphs/{graph}` | `topology(graph)`; 404 for an unknown graph |
| `GET /runs?graph=&limit=50` | newest first: `{run_id, graph, started, last_event, status, elapsed_ms, cost_usd, llm_calls, source}`, where `source` is `live` (state dir) or `demo` (shipped fixtures) |
| `GET /runs/{run_id}` | `fold()` of the log: run totals + `nodes: {id: {state, attempts, duration_ms, summary, error_code}}` |
| `GET /runs/{run_id}/events?replay=0&speed=4` | `text/event-stream`. Each event is sent as `id: <seq>`, `event: <type>`, `data: <json>`. Live mode sends what exists, then tails the file (poll ≤ 0.5 s) until `run_finished` or 30 min of no events. `replay=1` re-sends a finished run paced by the original gaps ÷ `speed` (each gap capped at 2 s, `speed` 1–32). Honours `Last-Event-ID`. A comment heartbeat every 15 s |
| `GET /runs/{run_id}/artifacts` | build runs only, names and counts from the target's `governor/build.json` and `governor/design.json` plus the dbt `target/manifest.json` when present: `{kpis: [{id, status: built\|gap\|declined, models}], models: [{name, layer: staging\|silver\|gold}], tests_passed, repairs, finding_codes: {code: count}, funnel: {requested, computable, proposed, validated, built}, lineage: {nodes: [{id, layer: raw\|silver\|gold\|kpi}], edges: [{source, target}]}}`. Missing sources give empty lists and nulls, not errors. A demo run serves its shipped artifacts file |

**Demo runs:**

- `src/governor/integrations/console/demo/` holds `<graph>/<run_id>.jsonl`, plus `<run_id>.artifacts.json` for build runs.
- They are produced by `scripts/make_console_demo.py`, which drives the **real traced graphs** with the fake LLM and fake dbt runner from the tests, on the synthetic sample. They are not hand-written.
- **At least four demo runs:**
  1. a full build with one validate repair (×2), a design-gate pause and approve, and one silver repair;
  2. an up-to-date build (most nodes skipped);
  3. an ask answered after one SQL repair;
  4. an ask blocked by the guard.
- The script is deterministic: the same output on every run, timestamps from a fixed clock.

**LangGraph Studio:**

- `langgraph.json` at the repo root: `{"dependencies": ["."], "graphs": {"build": "./src/governor/integrations/studio.py:build", "ask": "./src/governor/integrations/studio.py:ask"}}`. No `env` key: the server reads keys from the shell environment.
- Each function returns the compiled graph **without a checkpointer** (Studio adds its own). It uses the real OpenRouter LLM when `OPENROUTER_API_KEY` is set, else the fake one, and never touches the network at import.
- `docs/console.md` says how to run it (`uvx --from "langgraph-cli[inmem]" langgraph dev`), that it needs a LangSmith account, and that it is a developer view, not the product UI.

## 37. The console: live run canvas (V4)

**Stack (`apps/console/`):**

- Vite, React 18, TypeScript strict.
- `@xyflow/react` (v12), `@dagrejs/dagre`, `recharts`, `react-router-dom`.
- ESLint, Vitest + Testing Library (jsdom).
- npm scripts: `dev`, `build`, `preview`, `lint`, `typecheck`, `test`.
- Config by env: `VITE_API_BASE` (default `/` with a Vite dev proxy to `http://localhost:8000`) and `VITE_API_TOKEN` (optional).
- Plain CSS with variables, no UI kit.

**Look:** dark by default (background near `#0b0d12`, panels near `#12151c`, a dotted canvas background), with a light theme toggle. A sans font for text and a mono font for status lines. Original icons only: inline SVG, a small robot-like glyph per node kind. No third-party logos.

**Code structure:**

- `src/api/`: a typed client and `useRunEvents(runId, {replay, speed})`, an `EventSource` hook with reconnect and `Last-Event-ID`.
- `src/run/fold.ts`: the reducer, matching section 34 exactly.
- `src/graph/`: `RunCanvas`, `GovernorNode` (custom node), `layout.ts` (dagre, left-to-right default, top-down toggle), edges.
- `src/pages/`: `RunsPage`, `RunPage`, `GraphPage`.
- `src/copy.ts`: every user-facing string in one place.

**Node (`GovernorNode`):**

- A rounded card about 230×68: icon, label, a status line in mono, the duration right-aligned, and an `×N` badge when attempts > 1. The border colour is set by kind.
- **States:**

  | State | Look |
  |---|---|
  | pending | dim, "Not started" |
  | running | glowing pulse, "Working…" |
  | done | solid border, small check, the summary |
  | failed | red, the error code |
  | paused | amber, "Waiting for approval" / "Waiting for an answer" |
  | skipped | dashed and dim, "Skipped" |
  | planned | dashed, "Coming soon" |

- The description shows as a tooltip on hover.

**Canvas:**

- `smoothstep` edges with pill labels on conditional edges.
- **Edge states:**
  - traversed edges are brighter;
  - the edge into the running node is `animated` and highlighted;
  - untraversed edges are dim.
- `<Controls>` bottom-left (no lock button) and `<Background variant="dots">`.
- A **Follow live** toggle keeps the viewport centred on the current node with a smooth animation.
- **Show steps as a list** switches to an accessible ordered list of the same states.

**Run page:**

- **Header chips:** graph name, status chip, elapsed time, LLM calls, tokens, cost, and a Live dot (or "Replay" with 1× / 4× / 16× buttons and a restart).
- **Right panel:** a **Steps** tab (timeline of events, newest last) and a **Node** tab (the selected node's summary, attempts, durations, description).
- Replay is the default for demo runs; live is the default for running runs.

**Runs page:** a table with graph, started, status chip, elapsed, cost and a `demo` badge. Clicking a row opens its run page.

**Graph page:** the static topology with planned nodes. It is linked from the nav.

**Tests (Vitest):**

- `fold.ts` passes every case in `tests/fixtures/console/fold_cases.json`;
- `GovernorNode` renders each state (class and text);
- `useRunEvents` ignores duplicates and reconnects with `Last-Event-ID` (mocked `EventSource`);
- `RunPage` renders a demo run from a fixture without crashing.

## 38. The console: result views (V5)

Under the canvas on a run page, there is a tab bar. Every view has a caption: one sentence on what it shows, one on why it matters, in plain English (from `copy.ts`). Every view has an empty state that says what to do.

**Build runs:**

- **Summary:** tiles for elapsed, tables profiled, models, tests passed, KPIs built, gaps, LLM calls and cost.
- **Lineage:** a React Flow graph raw → silver → gold → KPI from `artifacts.lineage`. Columns by layer, colours by layer, a gap KPI drawn dashed. Click a node to highlight its upstream and downstream.
- **Build funnel:** Recharts horizontal bars for `requested → computable → proposed → validated → built`, plus a bar chart of `finding_codes` captioned "what the guard rails stopped".
- **KPI evidence:** a donut of built / gap / declined, plus a card per KPI (id, status, models feeding it, tests).

**Ask runs:**

- **Guard path:** a vertical waterfall of the checks (guard → validate → dry run → execute → answer), each pass / refused with its code and the repairs between them. Captioned "every query passes these checks before it touches the warehouse".

**Tests:**

- each view renders from a demo artifacts fixture;
- each view shows its empty state when data is missing;
- every caption string comes from `copy.ts`.

## 39. Packaging and showcase (V6, human gate)

**Docker:**

- `apps/console/Dockerfile`: Node 20 build stage → `nginx:alpine`, with an nginx config that serves the SPA and proxies `/v1/` to the API service.
- `docker-compose.yml` gains a `console` service on host port 8080. The API service gets `GOVERNOR_CONSOLE_OPEN` and `GOVERNOR_CONSOLE_ORIGINS` passed through from the environment, unset by default.

**Screenshots:** `apps/console/scripts/screenshots.mjs` (Playwright, Chromium).

- **Inputs:** the URL of a running console (API in `GOVERNOR_CONSOLE_OPEN=1` mode, serving demo runs) and an output folder.
- **Four PNGs at 1440×900** into `docs/showcase/`:
  - `console-runs.png`;
  - `console-build-live.png` (a replay paused mid-run, with at least one node running and one with ×2);
  - `console-build-lineage.png`;
  - `console-ask-guard.png`.
- **It fails when:**
  - the page logs a console error;
  - the page overflows horizontally;
  - the canvas has fewer than 10 rendered nodes.

**Docs and README:**

- `docs/console.md`:
  - what it is;
  - how to run it in dev (API with `uv run uvicorn governor.api.app:app` or the existing entry point, plus `npm run dev`);
  - replay and demo mode;
  - the event contract in short (link to this file);
  - LangGraph Studio;
  - the screenshots.
- `README.md`: a "Run console" section near the top with the build screenshot and two lines.

**Human gate:** Amir looks at the screenshots and the live console before merge.
