# STATUS: governor

Updated 22 Oct 2026. Spec written; no steps run.

| Step | Title | Tier | Gate | State |
|---|---|---|---|---|
| G1 | Foundation from the Sprint 4 import | mechanical | — | pending (needs the import) |
| G2 | Metrics, golden set, checker, frozen split | design | HUMAN | pending |
| G3 | Eval harness + baseline | design | — | pending |
| G4 | Catalog cards + hybrid retrieval | mechanical | — | pending |
| G5 | Validator, policy, dry-run, executor | design | HUMAN | pending |
| G6 | The graph + traces + CLI | design | — | pending |
| G7 | Streamlit pages | mechanical | — | pending |
| G8 | MCP server | mechanical | — | pending |
| G9 | Eval (tune, holdout once) + README | design | HUMAN | pending |

Next: after the Sprint 4 submission, run `scripts\import_foundation.ps1`; when factory F3 is done, `factory plan validate plan.yaml` and `factory lock`.
