# STATUS: governor

Updated 06 Nov 2026 13:35. Run `20261106-132359`.

| step | title | tier | gate | state | loops | reason | implementer | verdicts | updated |
|---|---|---|---|---|---|---|---|---|---|
| G1 | Foundation from the Sprint 4 import (core package, green build, fct_invoices, metadata store) | mechanical | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-22T16:18:54 |
| G2a | Metric definitions, golden-set loader, result checker | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-22T16:36:50 |
| G2b | Golden set with gold SQL, frozen split, review table | design | yes | done | 1/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T15:02:45 |
| G3 | Evaluation harness, metrics, self-test systems, baseline | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T15:41:27 |
| G4 | Catalog and metric cards, hybrid schema retrieval, recall@k on gold tables | mechanical | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T15:56:57 |
| G5a | SQL validator and role policy | design | - | done | 1/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T17:06:30 |
| G5b | Dry-run and read-only executor | design | yes | done | 0/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-10-23T17:33:27 |
| G6a | The governor-ask graph (core, in-memory) | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T17:59:45 |
| G6b | Persistence, decision traces, CLI and the agent system | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T18:22:40 |
| G7 | API, authentication and deployment skeleton | design | yes | done | 1/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-10-23T19:30:56 |
| G8 | Streamlit as a thin client over the API | mechanical | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T19:47:55 |
| G9 | MCP server with 5 read-only tools (stretch: cut first if late) | mechanical | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T19:58:50 |
| G10a | Tune on the tune split, then freeze the prompts | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T20:50:38 |
| G10b | Holdout once, eval report, README, demo script | design | yes | done | 0/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-10-23T21:17:23 |
| C1 | Close the four G-phase follow-ups (checkpoint privacy, OpenAPI, dry-run timeout, Docker check) | design | - | done | 2/2 |  | claude-tc-opus | cursor-grok: pass | 2026-11-02T22:06:52 |
| C2 | Warehouse adapter seam, DuckDB first, no behaviour change | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-11-02T22:25:47 |
| C3 | Postgres test bed with the Olist loader and a synthetic sample | mechanical | - | done | 0/2 |  | claude-tc-sonnet | cursor-grok: pass | 2026-11-02T22:36:33 |
| C4 | Postgres adapter and database roles | design | yes | done | 2/2 |  | claude-tc-opus | cursor-grok: pass | 2026-11-04T11:02:50 |
| C5 | Serving schemas and the validator in the Postgres dialect | design | yes | done | 2/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-11-04T12:43:54 |
| C6 | KPI catalogue, layer blueprint and approved-decisions formats | design | yes | done | 2/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-11-04T17:26:20 |
| D1 | Test-bed isolation, build role reads raw, target dbt workspace | mechanical | - | done | 2/2 |  | claude-tc-sonnet | cursor-grok: pass | 2026-11-04T17:41:14 |
| D2 | Profile the raw schema | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-11-04T18:09:23 |
| D3 | Design proposal, validation, report and the design gate | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-11-04T18:34:10 |
| D4 | Silver writer, dbt build in the dev schema, repair and escalation | design | yes | done | 0/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-11-04T21:54:31 |
| D5 | Gold from catalogue templates, blueprint checks, gap report | design | yes | done | 0/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-11-04T23:03:58 |
| D6 | Mapping pairs, events, pull request and certification | design | yes | done | 0/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-11-05T12:41:29 |
| D7 | Certified answers in ask | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-11-05T13:05:52 |
| D8a | Build evaluation harness (agent vs one-shot baseline) | design | - | done | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-11-05T13:24:01 |
| D8b | Certified-answer evaluation, red team and the capstone report | design | yes | done | 1/2 |  | claude-tc-opus | cursor-grok: pass, claude-tc-fable: pass | 2026-11-05T14:26:32 |
| D12 | Clean-up from the D6 and D8 gate reviews | mechanical | - | passed | 2/2 |  | claude-tc-sonnet | cursor-grok: pass | 2026-11-06T13:35:50 |
| D11 | Red-team findings (first live run, 5 Nov) | design | yes | pending | 0/2 |  | - | - | - |

Cost so far (reported + notional): $88.70 of $150.00 run budget; 109 agent call(s).

Next: D12 is passed: `factory resume`.
