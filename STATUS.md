# STATUS: governor

Updated 22 Oct 2026. Spec revised after the Sol review (14 steps, 4 human gates); no steps run.

| Step | Title | Tier | Gate | State |
|---|---|---|---|---|
| G1 | Foundation from the Sprint 4 import | mechanical | — | pending (needs the import) |
| G2a | Metrics, golden loader, result checker | design | — | pending |
| G2b | Golden set, gold SQL, frozen split | design | HUMAN | pending |
| G3 | Eval harness + baseline | design | — | pending |
| G4 | Catalog cards + hybrid retrieval | mechanical | — | pending |
| G5a | SQL validator + role policy | design | — | pending |
| G5b | Dry-run + read-only executor | design | HUMAN | pending |
| G6a | The graph (in-memory) | design | — | pending |
| G6b | Persistence, traces, CLI, agent system | design | — | pending |
| G7 | API, auth, deploy skeleton | design | HUMAN | pending |
| G8 | Streamlit thin client | mechanical | — | pending |
| G9 | MCP server (stretch) | mechanical | — | pending |
| G10a | Tune + freeze prompts | design | — | pending |
| G10b | Holdout once, report, README | design | HUMAN | pending |

Next: after the Sprint 4 submission, run `scripts\import_foundation.ps1`; when the factory's real toy runs pass, `factory plan validate plan.yaml` and `factory lock`.
