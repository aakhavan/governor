# STATUS: governor

Updated 23 Oct 2026 20:50. Run `20261023-193056`.

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
| G10a | Tune on the tune split, then freeze the prompts | design | - | passed | 0/2 |  | claude-tc-opus | cursor-grok: pass | 2026-10-23T20:50:38 |
| G10b | Holdout once, eval report, README, demo script | design | yes | pending | 0/2 |  | - | - | - |

Cost so far (reported + notional): $27.08 of $80.00 run budget; 38 agent call(s).

Next: G10a is passed: `factory resume`.
