# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
- 22 Oct 2026: spec written, then revised after an independent GPT-5.6 Sol review (`docs/review/sol-review-2026-10-22.md`): 14 steps (G2, G5, G6, G10 split; G7 API/auth/deploy added; MCP is a stretch), validator default-deny + `VOLATILE_TIME`, outer-projection masking, access.yaml human-only, walkthrough before every approve. No code yet.
- Checked: `factory plan validate plan.yaml` ok (9 steps, 3 human gates); every acceptance script fails cleanly on the empty repo (exit 1, JSON last line, <= 12 lines). The DuckDB/sqlglot paths inside accept_g1/g2/g5 were exercised against a fake warehouse; the G8 MCP client compiles but is untested until G8.
- Waiting on: Sprint 4 submission → `scripts/import_foundation.ps1` (HUMAN); factory F3; then `factory lock`.

## Open questions
- Capstone brief not yet available; PLAN §1 holds the provisional stance (ask = spine, one triage path = stretch).
- Sol suggested comparing column names/types in the checker; kept name-agnostic on purpose (LLM aliases vary; Spider-style execution accuracy), with equal column counts and permutation matching.
- `fct_invoices`: does `int_invoices_with_payments` have paid amount/date per invoice, or does G1 need to aggregate payments? (G1 decides, notes it.)
- PII tags on marts: S4 `policy.yaml` may tag only source/staging columns; G1 must make mart columns carry the tags (A7 depends on it).

## Additions for G1
- Start from `PROVENANCE.md`: it lists every imported file and its original path. Rename imports `triage.` → `governor.core.`; replace any path built from the S4 folder with `governor.core.paths`.
- Keep changes to imported code minimal and list each one in `PROVENANCE.md` ("changed: …").
