# Response to the Sol review (22 Oct 2026)

Review: `sol-review-2026-10-22.md` (GPT-5.6 Sol in Cursor, on `review-pack-2026-10-22.md`). Decisions by Amir and Claude, same day.

| # | Sol's change | Decision | Where |
|---|---|---|---|
| 1–3 | Sprint 4: P9d README sections, keep only tested model ids, restart-test P9b + rebuild export | Accepted, for the Sprint 4 chat (Claude does not edit sprint folders). Note: Sol missed the attached README; the four P9d sections are indeed absent from it | Sprint 4 repo |
| 4 | Reject volatile time functions; literal ranges from as_of | Applied | PLAN A4, G5a prompt, `_g5_cases.py` (3 cases), G6a test `test_volatile_time_never_reaches_execute` |
| 5 | Default-deny relations and table functions | Applied | PLAN A8, G5a prompt, `_g5_cases.py` (4 cases), G5b disables external access on the connection |
| 6 | Semantics-preserving masking, no raw PII in traces | Applied: outer-projection masking; COUNT of PII stays a number | PLAN A7, G5a/G5b, `_g5_cases.py` (DISTINCT + COUNT cases), G6b `test_trace_never_stores_raw_pii` |
| 7 | Checker compares column names/types | **Not applied.** Execution accuracy stays name-agnostic (LLM aliases vary; Spider convention); equal column count + permutation matching kept | NOTES open questions |
| 8 | Freeze must precede both holdout reports | Applied | `accept_g10b.py` |
| 9 | access.yaml out of agent scope | Applied | plan.yaml G1, G1 prompt |
| 10 | Split G1, G2, G5, G6, G9 | Applied for G2, G5, G6, G9→G10; G1 kept whole (mostly adapting imported code) | plan.yaml (14 steps) |
| 11 | Walkthrough before every approve | Applied | PLAN §8.5 (`docs/walkthroughs/<step>.md`) |
| 12 | API/auth/deploy step before the UI | Applied: G7 (FastAPI, token → role, Dockerfile, compose), human gate; Streamlit is a thin HTTP client (G8) | PLAN A1, A15, §3, §7; G7/G8 prompts and acceptance |
| 13 | Defer MCP when late | Applied: G9 is a stretch, cut first; MCP role fixed by env, no role argument | PLAN §1, §7; G9 |
| 14 | Metamorphic paraphrases + adversarial policy cases | Partly: adversarial cases are in the locked G5 contract (now 39 + 14); paraphrase slice deferred to after the holdout (it must not touch the frozen set) | — |
| 15 | Capstone scope stance | Applied as provisional | PLAN §1, §9 |
| 16 | Factory: defer F4–F6 | Accepted; set in factory STATUS after the two real toy runs pass | factory repo |
| 17 | Cross-document counts | Sprint 4 side: for the Sprint 4 chat. Governor states "4 queryable marts" as its limit | PLAN §6 |
| 18 | Replace inferred dates after the brief | Accepted | PLAN §9 |

Also from the review: G6a answer text may carry data values only through placeholders (categorical claims too), and G5b's timeout test uses 1 s instead of 0.3 s.
