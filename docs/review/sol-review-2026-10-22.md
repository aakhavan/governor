## Verdict
The four initiatives point at the right career story, but they do not fit concurrently before 23 November. *(inference; App. B; App. C §1; App. G §G.1.1; App. H §H.1)*
Finish and submit triage, prove the factory with its two F3 toy runs, then freeze factory development. *(inference; S4 NOTES §P9c and §Additions for P9d; App. H §H.3)*
Make governed analytics the capstone spine; triage is an integration proof, not a second equal product, and `maintainer` is out. *(inference; App. E §2; App. G §G.1.1)*
The single most important change is to add a deployable API/auth boundary to governor before G1–G9 are locked. *(inference; App. D §7; App. G §G.1.9)*

## Q1
Value to Amir's hiring goal per hour, highest first:

1. **Finish Sprint 4.** It is already at P9c, has a clean-copy check and 102 passing tests, and directly demonstrates LangGraph, evaluation, governance and human approval. The remaining P9d work is small and maps to assessor questions. (S4 NOTES §P9c, §P9b/P9c review, §Additions for P9d; App. A, Evaluation criteria)
2. **Build governor-ask.** Governed NL→SQL is closest to Amir's senior data-platform background and supplies the stronger hiring signal: deterministic policy, execution evaluation and decision traces. (App. C §1; App. E §2; App. G §G.1.1 and §G.1.6)
3. **Shape and deploy the capstone.** “One foundation + ask + one integrated triage path” is coherent only after its product boundary, auth and deployment are explicit. *(inference; App. D §2 and §7; App. G §G.1.1)*
4. **Extend the factory.** F3 can reduce repetitive work, but F4/F6 measure the development machinery rather than the data product. *(inference; App. H §H.1, §H.5 F4/F6)*

- **Stop:** F4 reviewer calibration and F6 bake-off until after the course. *(inference; App. H §H.5 F4/F6)*
- **Defer:** `maintainer`, Spider 2.0-DBT, and a full triage migration until ask is deployed and evaluated. *(inference; App. F §4; App. G §G.1.1 and §G.1.6)*
- **Protect:** the G2 ground-truth, G5 security and G9 release gates, plus time for Amir to explain each resulting diff. *(inference; App. G §G.1.7–8)*

## Q2
The brief's core is substantially met, but the evidence available here is indirect because no S4 README was attached. The latest notes record a working UI, clean export, documented use cases, 102 tests, frozen evaluation results, four medium bonuses and two hard bonuses; they also record the remaining documentation gaps. (S4 NOTES §P9, §P9c, §P9b/P9c review, §Additions for P9d; App. A, Task requirements and Bonus points)

Concrete gaps closable in under a day, in order:

1. Add the four P9d README explanations: errors/edge cases, function calling, agent types, and adapting the app to another dbt project. These directly close four assessor prompts rather than adding functionality. (S4 NOTES §Additions for P9d; App. A, Evaluation criteria)
2. Test the two advertised non-OpenAI chat models on a tune incident and remove any model that cannot produce a valid card; do not call this medium bonus unless one works. (S4 NOTES §Additions for P9d; S4 PLAN §11)
3. Restart Streamlit and re-check the P9b “old card while streaming” fix; the live check used a pre-P9b process and therefore did not verify the shipped code. (S4 NOTES §P9b/P9c review)
4. Rebuild the export and run its short `uv sync` plus offline suite after P9d. Do not rerun the holdout or alter prompts. (S4 NOTES §Additions for P9d; §P9c; S4 PLAN §12 and §14 P9)
5. Spend the remaining time rehearsing evidence already built, especially the weak null-regression class, run-to-run variance and the limited rewrite result; adding another optional feature would lower submission reliability. *(inference; S4 NOTES §Current state after P6, §P8b review, §P9; App. A, Reflection and improvement)*

Eight likely defence questions and supported one-line answers:

1. **Why is this an agent rather than a chain?** The next evidence action depends on prior tool output, while Python fixes the graph edges, budgets and exit conditions. (S4 PLAN §8 and §16)
2. **What does the model decide?** It chooses the next evidence tool and drafts class, culprit and explanation; Python owns lineage, owner, blast radius, PII and validation. (S4 PLAN §0 and §8)
3. **How does function calling work?** Pydantic-validated tools return evidence IDs, one tool is called per turn, and `submit_rca` is the only structured exit. (S4 PLAN §6–8)
4. **How do you know it works?** Eighteen injected incidents, a frozen six-incident holdout, a rule baseline and repeated runs produce the headline 30/36 overall and 9/12 holdout result. (S4 PLAN §4 and §12; S4 NOTES §P9)
5. **What is agentic about the RAG?** The investigator decides when to search; a grader can reject results and rewrite the query, although vague-query recall remains a measured limitation. (S4 PLAN §8; S4 NOTES §Current state after P6 and §P8b result)
6. **How is unsafe data handled?** DuckDB is read-only, profile results suppress PII values, untrusted text is delimited, and human free text is guarded. (S4 PLAN §6 and §10; S4 NOTES §Current state after P6)
7. **How does human approval survive refreshes?** `SqliteSaver` persists the interrupted graph; corrections create human evidence IDs and rejected runs receive a bounded new evidence allowance. (S4 PLAN §0 and §8; S4 NOTES §P9 step 0 and §P9 review)
8. **What failed?** Null regression was weak, one result changed across repeats, and the original human loop could not override an ungrounded card; all are reported rather than hidden. (S4 NOTES §Open questions, §P8b review, §Screenshots and a human-loop finding)

## Q3
### (a) Design

The ownership split, read-only execution, policy-as-data rule, frozen `as_of`, explicit graph and human gates are sound. (App. G §G.1.2 A3–A14 and §G.1.4)

Four changes are needed:

- A4 is not enforced at the SQL security boundary. G5 rejects many constructs but not `CURRENT_DATE`, `CURRENT_TIMESTAMP` or equivalent volatile functions; source-code grep in G6 cannot catch SQL generated at runtime. Reject volatile time functions and pass literal bounds derived from `as_of` in the structured plan. *(inference; App. G §G.1.2 A4, §G.5 G5, §G.6 `accept_g6.py`)*
- Replacing a selected PII expression with `'***'` can change `DISTINCT`, grouping, ordering or set-operation semantics. Mask after execution, or in a semantics-preserving outer projection, and ensure raw values never enter traces. *(inference; App. G §G.1.2 A7–A8; §G.5 G5)*
- DuckDB read-only mode blocks writes, not reads from local files or extensions. The validator should default-deny every non-catalog relation and every table-valued function, not rely on a named blacklist. *(inference; App. G §G.5 G5 and `accept_g5.py`)*
- “Python fills every number” still permits invented categorical claims. Return a deterministic result table and test that narrative placeholders resolve only to result cells or approved metadata. *(inference; App. G §G.1.4 and §G.5 G6)*

Hybrid retrieval over four queryable marts is over-built as a correctness dependency but useful as a demonstrator; MCP is lower priority than deployment. *(inference; App. G §G.3 allowlist, §G.1.6, §G.5 G8)*

### (b) Evaluation

Forty items are meaningful as a regression suite for this fixture, not as evidence of general NL→SQL ability; the holdout contains only 15 items and retrieval sees only four allowlisted model cards plus metric cards. (App. G §G.1.3, §G.1.6)

- A hiring manager will challenge unseen schemas, paraphrase stability, adversarial policy bypasses, baseline fairness and whether exact results survive realistic joins. *(inference; App. E §2; App. G §G.1.6)*
- A mentor will challenge gold-SQL independence, whether the holdout was truly untouched, confidence intervals, and whether deployment behavior matches the offline harness. *(inference; App. A, Reflection and improvement; App. G §G.1.6 and §G.5 G9)*

Keep 40 hand-reviewed items, then add cheap metamorphic variants and a small adversarial security suite; report counts and failures, not a broad benchmark claim. *(inference; App. G §G.1.6)*

### (c) Acceptance gates

A naive or wrong implementation can pass several gates:

- G2 verifies shape, execution and non-empty rows, not that a question and gold SQL mean the same thing; the human gate is indispensable. (App. G §G.6 `accept_g2.py`)
- G4 requires BM25 recall but only requires hybrid mode to run, so dense retrieval may be useless; text hashes or indirect lookup could also evade the overlap check. (App. G §G.6 `accept_g4.py`)
- G6 checks node names, required test names and completion of 25 fake items, but no minimum behavioral score; stubs plus weak self-authored tests can pass. (App. G §G.6 `accept_g6.py`)
- G7 checks page structure and self-authored tests, not the actual role-policy behavior. (App. G §G.6 `accept_g7.py`)
- G9 deliberately has no accuracy floor, which is defensible for honest reporting, but its prompt-freeze timestamp check uses the latest holdout report; it should prove the freeze predates both reports. (App. G §G.6 `accept_g9.py`)

There is no pair of acceptance checks that is literally impossible together. There is a policy contradiction: `access.yaml` is human-owned, yet G1 lets the implementer rename it; human ownership should win. (App. G §G.4, Hard rules; §G.2 G1; §G.5 G1)

Windows risks are G5's 0.3-second timeout test, filesystem timestamp ordering in G9, SQLite/DuckDB locks in AppTests, and MCP stdio shutdown; they are flaky, not impossible. *(inference; App. G §G.6 `accept_g5.py`, `accept_g7.py`, `accept_g8.py`, `accept_g9.py`)*

### (d) Step sizing

G4, G7 and G8 fit one bounded session. Split G1 (import/build, then package/metadata), G2 (checker/metrics, then 40-item ground truth), G5 (validator/policy, then executor/adversarial tests), G6 (graph, then persistence/traces/harness) and G9 (tune/freeze, then holdout/report/release). G3 can remain one session only if leak detection is already specified by locked cases. Merge none; defer G8 before compressing a security or ground-truth step. *(inference; App. G §G.1.7 and §G.5 G1–G9)*

## Q4
Finish the two real F3 toy runs, inspect their commits and ledger, then use the factory on G1 in supervised mode. F4 and F5 are not prerequisites; F6 is explicitly optional. *(inference; App. H §H.1, §H.3, §H.5 F4–F6)*

Likely failures on governor-ask are Windows DuckDB/SQLite locks, subscription/profile exhaustion, oversized G1/G2/G5/G6 steps, weak reviewers accepting self-authored tests, and scope stops when generated artifacts or lockfiles change unexpectedly. (App. H §H.2 Open questions; App. H §H.4 §5.5; App. G §G.2)

For the portfolio, the factory is useful only as measured provenance for how governor was built. For the course, more factory features are a meta-work trap because the assessed artifact is the deployed AI application. *(inference; App. A; App. H §H.5 F4/F6)* Add a mandatory knowledge-transfer note at every human gate: Amir explains the design, traces one request, and records one limitation before approval. *(inference; App. G §G.1.8)*

## Q5
**In:** shared `core`; governed ask; frozen evaluation; decision traces; a thin FastAPI boundary; authenticated roles; one-container deployment; and, only after ask is stable, one triage workflow reusing core policy/metadata. *(inference; App. D §2 and §7; App. G §G.1.1)*

**Stretch:** MCP, a fuller triage migration and one external-schema robustness slice. **Out:** `maintainer`, Spider 2.0-DBT headline scoring, multi-agent orchestration, writeback, multiple warehouses and factory F4/F6. *(inference; App. E §2; App. F §4; App. G §G.1.6; App. H §H.5)*

“One foundation + ask + triage” is coherent if one policy, catalog, trace schema, auth model and API serve both workflows. Otherwise it is the “two shallow demos” problem the portfolio strategy warns against. *(inference; App. E §2; App. G §G.1.1)*

Resolve the API conflict by defining `/v1/ask`, `/v1/threads/{id}/resume`, `/v1/traces` and `/health` before G1, then implementing them after G6 and making Streamlit a thin client. Roles must come from a server-validated session/token, not a trusted picker. Use platform-managed secrets, TLS, a single replica, bundled read-only DuckDB, and persistent storage for checkpoints/traces; document that this is a portfolio deployment, not a multi-tenant service. *(inference; App. D §7; App. G §G.1.9)*

Before locking scope, confirm the real brief's rubric, required deployment surface, auth expectations, permitted code reuse, required mentor checkpoints, submission date, hosting constraints and evaluation evidence. The pack explicitly lacks those facts. (App. B; App. E §1)

## Q6
`[Class]` means 09:00–16:30 course time; weekend work is deliberately bounded. The defence date is unknown, so 26 October is reserved provisionally. (App. B; App. C §1)

- **Fri 23 Oct [Class]:** P9d, export check, submit Sprint 4.
- **Sat 24:** submission contingency and one defence rehearsal.
- **Sun 25:** deadline buffer; no new feature.
- **Mon 26 [Class]:** defence prep; factory F3 default-role toy run.
- **Tue 27 [Class]:** F3 swap toy run; freeze factory; read capstone brief.
- **Wed 28 [Class]:** lock capstone scope and API/auth contract.
- **Thu 29 [Class]:** G1 import/green build.
- **Fri 30 [Class]:** G1 package, mart and metadata.
- **Sat 31:** two-hour G1 buffer.
- **Sun 1 Nov:** rest or G2 ground-truth preparation.
- **Mon 2 [Class]:** G2 metrics/checker and first gold cases.
- **Tue 3 [Class, G2 HUMAN]:** finish and manually review all gold SQL.
- **Wed 4 [Class]:** G3 harness and self-test systems.
- **Thu 5 [Class]:** G3 leak detector and baseline.
- **Fri 6 [Class]:** G4 cards/retrieval; document its small-catalog limit.
- **Sat 7:** two-hour retrieval/security buffer.
- **Sun 8:** rest.
- **Mon 9 [Class]:** G5 validator and default-deny relation policy.
- **Tue 10 [Class, G5 HUMAN]:** executor, masking tests and security review.
- **Wed 11 [Class]:** G6 graph core; checkpoint account access before the expected Claude expiry. (App. H §H.1)
- **Thu 12 [Class]:** G6 clarification, repair and persistence.
- **Fri 13 [Class]:** G6 traces/harness integration and walkthrough.
- **Sat 14:** two-hour G6 buffer.
- **Sun 15:** rest.
- **Mon 16 [Class]:** FastAPI/auth boundary and deployment skeleton.
- **Tue 17 [Class]:** G7 Streamlit thin client.
- **Wed 18 [Teaching-free]:** deployment soak/buffer; G8 MCP only if green. (App. B)
- **Thu 19 [Class]:** G9 tune runs, fixes and prompt freeze.
- **Fri 20 [Class, G9 HUMAN]:** holdout once, report and release review.
- **Sat 21:** optional thin triage integration; otherwise release buffer.
- **Sun 22:** final docs, demo rehearsal and immutable export.
- **Mon 23 [Class]:** submit, mentor hand-off and contingency. (App. B)

This schedule treats G8 and triage integration as cuts if any gate slips; it does not spend buffer on F4/F6. *(inference; App. G §G.1.7; App. H §H.5)*

## Q7
1. **Scope collision — H/H.** Signal: a G-step takes over two class days. Mitigation: cut G8 and triage integration first; never cut G2/G5/G9. *(inference; App. G §G.1.7)*
2. **Factory-built code Amir cannot defend — H/H.** Signal: he cannot trace one request or explain a changed module. Mitigation: walkthrough and written limitation at each gate. *(inference; App. G §G.1.8)*
3. **PII/file-read bypass — M/H.** Signal: an adversarial table function or CTE passes G5. Mitigation: default-deny relations/functions and maintain locked attack cases. *(inference; App. G §G.5 G5)*
4. **Invalid holdout claim — M/H.** Signal: prompt hash/timestamp changes or a second log row. Mitigation: immutable hashes, one command path and human G9 review. (App. G §G.1.2 A12–A13)
5. **Small-fixture overclaim — H/M.** Signal: high score collapses on paraphrases or a new schema. Mitigation: call it a regression suite and add metamorphic/adversarial slices. *(inference; App. G §G.1.6)*
6. **LLM variance — H/M.** Signal: the same incident/question changes class or SQL across repeats. Mitigation: report spread and preserve deterministic validation/refusal. (S4 NOTES §P8b review; App. G §G.1.6)
7. **Deployment state/auth failure — M/H.** Signal: roles are client-controlled or traces vanish after restart. Mitigation: server-derived role, persistent store and single-replica runbook. *(inference; App. D §7; App. G §G.1.9)*
8. **Factory/Windows failure — M/M.** Signal: toy run stops on locks, scope or profile exhaustion. Mitigation: complete F3 toys and retain a manual execution path. (App. H §H.2–3)
9. **Claude access expires mid-build — H/H.** Signal: 11 November approaches without G5 complete. Mitigation: finish design-heavy gates first and verify personal/Cursor fallbacks. (App. H §H.1–2)
10. **Core/triage drift — M/M.** Signal: duplicate policy, paths or trace models. Mitigation: integrate one vertical path only; otherwise label triage as a separate predecessor. *(inference; App. G §G.1.1)*

## Q8
- **Capstone dates:** App. D §9 and App. F §8 say Jan–Feb; App. B ends the course on 23 Nov. App. B wins until the real brief says otherwise.
- **Capstone scope:** App. E §2 warns against multiple shallow products, while App. G §G.1.1 tells a three-agent story. App. E's one-spine rule wins; ask is primary, triage is proof, maintainer is out. *(inference)*
- **Serving:** App. D §7 requires FastAPI from day one; App. G §G.1.9 explicitly excludes it. App. D wins for capstone deployment, with an amended governor plan. *(inference)*
- **Sprint status:** pack §2 says P7–P9 are in progress; S4 NOTES §P9c records a clean export and 102 tests. The dated S4 notes win.
- **Sprint topology:** S4 PLAN §3 specifies 10 models and one exposure; S4 NOTES §Current state after P6 records 11 models and two exposures. Generated/current state wins; update documentation.
- **Model support:** S4 PLAN §0 locks GPT mini/nano, while S4 NOTES §Additions for P9d describes unverified Anthropic/Google UI choices. The evaluated GPT configuration remains the claim; remove any unverified option. *(inference)*
- **Policy ownership:** App. G §G.4 says `access.yaml` is human-owned; G1 permits agent edits. Human ownership wins; changes require a human gate.
- **Factory phase order:** App. H §H.1 lists F4, F5, F6, but App. H §H.5 specifies F4, F6, F5. Neither should consume capstone time; after F3, STATUS should mark all three deferred. *(inference)*
- **Numbering:** App. B and App. C §1 use three identifiers for the same sprint. The platform's title should win externally, with the mapping stated once in README.

## Comparison with Claude's concerns (§6)
- **Agree:** timeline drift, factory over-investment, missing API, shallow evaluation, defensibility, account expiry, migration ambiguity, numbering and G2 review cost are all supported by the appendices. (Pack §6; App. B; App. G; App. H)
- **Disagree:** triage migration is not load-bearing for a coherent capstone; making it stretch is safer than forcing two equal products. *(inference; Pack §6.8; App. E §2)*
- **Missed:** volatile time SQL is not blocked, SQL-level masking can change semantics, and G9's freeze-order check can accept one pre-freeze holdout report. *(inference; App. G §G.5 G5; §G.6 `accept_g9.py`)*

## Changes to make
1. **S4 README, assessor explanations:** add the four P9d sections; they close documented rubric gaps. (S4 NOTES §Additions for P9d)
2. **S4 model settings:** retain only tune-tested model IDs and label GPT mini as the evaluated model. (S4 NOTES §Additions for P9d)
3. **S4 release:** restart-test P9b, rebuild the export and run its offline suite; do not rerun holdout. (S4 NOTES §P9b/P9c review and §Additions for P9d)
4. **Governor PLAN A4/G5:** reject volatile date/time functions and derive literal ranges from `as_of`; prompts alone do not enforce time. (App. G §G.1.2 A4; §G.5 G5)
5. **Governor G5:** make relation/table-function checks default-deny and add external-scan attack cases. (App. G §G.5 G5)
6. **Governor G5:** replace semantics-changing SQL masking with post-result or outer-projection masking, with no raw PII in traces. (App. G §G.1.2 A7; §G.5 G5)
7. **Governor G2 checker:** compare expected output names/types as well as rows; arbitrary column permutation is too permissive. *(inference; App. G §G.5 G2)*
8. **Governor `accept_g9.py`:** prove prompt freeze precedes both holdout reports, not only the later one. (App. G §G.6 `accept_g9.py`)
9. **Governor G1:** remove `knowledge/access.yaml` from agent-editable scope; make any rename a human action. (App. G §G.2 G1; §G.4)
10. **Governor plan sizing:** split G1, G2, G5, G6 and G9 at the boundaries listed in Q3(d). *(inference; App. G §G.1.7)*
11. **Governor human gates:** require an Amir walkthrough and limitation note before G2/G5/G9 approval. *(inference; App. G §G.1.8)*
12. **Governor architecture:** add a FastAPI/auth/deployment step before G7 and make Streamlit a thin client. *(inference; App. D §7; App. G §G.5 G7)*
13. **Governor G8:** defer MCP whenever API, security or evaluation is late. *(inference; App. G §G.5 G8)*
14. **Governor evaluation:** add metamorphic paraphrases and adversarial policy cases without enlarging the frozen holdout. *(inference; App. G §G.1.6)*
15. **Capstone scope document:** state ask=in, one triage path=stretch, maintainer/Spider/multi-agent=out. *(inference; App. E §2; App. F §4)*
16. **Factory STATUS:** after both real F3 toys pass, mark F4/F5/F6 deferred until after 23 Nov. *(inference; App. H §H.1 and §H.3)*
17. **Cross-document status:** update the S4 model/exposure counts and governor's “four queryable marts” limitation wherever broader node counts are presented. (S4 NOTES §Current state after P6; App. G §G.3 and §G.1.6)
18. **Capstone lock:** replace all inferred dates and deployment assumptions immediately after the real brief and mentor checkpoint are available. (App. B; App. E §1)

## Assumptions
- The capstone occupies roughly 27 Oct–23 Nov and expects a deployed artifact; both are assumptions because its brief is absent. (Pack §1; App. B; App. E §1)
- No S4 README was present, so documentation/UI claims rely on the latest S4 notes rather than direct inspection. (Pack §7; S4 NOTES §P9c)
- P9c is complete and P9d is not yet complete; the notes contain P9d instructions but no P9d result. (S4 NOTES §P9c and §Additions for P9d)
- G1–G9 remain a specification, and factory F3 remains incomplete until both human toy runs pass. (App. G preface; App. H §H.1 and §H.3)
- Weekday class hours are usable capstone build time, weekends are limited, the defence date is unknown, and the 11 Nov Claude expiry is unconfirmed. (App. B; App. C §1; App. H §H.1–2)
