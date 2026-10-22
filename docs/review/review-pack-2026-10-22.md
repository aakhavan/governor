# Cross-model planning review: Sprint 4, governor, the code factory and the capstone

*Review pack assembled 22 Oct 2026 (Thursday) by Claude, for an independent review by a model from a different family. The brief and questions come first, then the source documents as appendices A–H. Sprint 4's own files are in `docs/review/s4/` (§7). Write your review to `docs/review/sol-review-2026-10-22.md` and change no other file.*

---

## 0. Your role and the rules

You are an independent senior reviewer with three hats:
1. **AI engineer:** agents, LangGraph, NL→SQL, RAG, LLM evaluation.
2. **Data-platform architect:** dbt, DuckDB, catalogs, lineage, governance.
3. **Course assessor:** you grade against the Turing College brief.

The plans in this pack were written mostly with Claude models. You are here because a reviewer from a different model family is less likely to share their blind spots. **Be specific and adversarial, but constructive.**

**Rules:**
- **Cite** the appendix and section for every claim, for example "App. G, plan.yaml step G5" or "App. D §7".
- **Separate** facts (stated in the pack) from inferences (yours). Mark inferences with *(inference)*.
- **Do not invent course requirements.** The capstone brief is missing (§1). Where an answer depends on it, state your assumption and say what Amir should check.
- **Prefer changes to the existing plans** ("in G5, add …"; "cut F6") over new plans. Recommend a new tool or framework only if you can name the failure it fixes.
- **Respect the time budget.** Amir is one person, with full-time class hours on weekdays, a job search and a band.
- **Read §6 last.** It holds Claude's own concerns. Do your independent pass first, then compare with §6 and say where you agree, disagree, or found something Claude missed.

---

## 1. Hard facts and dates

| Fact | Value | Source |
|---|---|---|
| Today | Thu 22 Oct 2026 | — |
| Course | Turing College AI Engineering, batch AE_2026-08_B. Funded by a German Bildungsgutschein. 24 Aug – **23 Nov 2026**, 13 weeks, 520 teaching units (UE). Classes Mon–Fri 09:00–16:30, synchronous, 100% online | App. B |
| Modules | Foundations 128 UE · LangChain/RAG/Streamlit 128 UE · AI Agents 128 UE · **Capstone 136 UE** (about 3.4 full-time weeks) | App. B |
| Current sprint | AI Agents. The platform calls the project brief "Sprint 4"; the local folder is `sprint-04-incident-triage`. Target submit **Fri 23 Oct**, deadline **Sun 25 Oct**, then a defence (date not in the pack) | App. A, C §1 |
| Capstone brief | **Not available yet** (it opens after the current sprint is submitted). Known: self-directed concept → deployment, 1:1 senior mentor review (App. E §1). Course end 23 Nov, so the capstone is likely about **27 Oct – 23 Nov** *(inference from App. B)*. **Amir's expectation (22 Oct, use as the working assumption):** a combination of everything learned in the course, at a much higher level, as ready-to-ship software. His preferred direction: the "Databricks-lite" agentic data platform, combining incident management (Sprint 4 triage), governor-ask (governed NL→SQL) and related governance modules on one foundation | App. B, E; Amir |
| Model access | A Turing College Claude account (models up to Opus 5) for Claude Code, expected to end around **11 Nov 2026** (unconfirmed). Also a personal Claude account, Cursor (Grok 4.7, Composer 2.5), Gemini CLI (not installed) | App. H |
| Amir | Senior data/platform engineer (about 10 years: BI → DE → platform/MLOps), GCP PDE, AWS SA-A, Berlin. **Goal:** get hired in Germany as a senior data/platform engineer with credible AI-agent skills, and become an "AI expert" within months | App. C, E |

---

## 2. The initiatives running in parallel today

| # | Initiative | What it is | Status 22 Oct | Appendix |
|---|---|---|---|---|
| 1 | **Sprint 4: "governor · triage"** | LangGraph agent that triages failed dbt runs on a synthetic SaaS-billing mart. Evidence ids, a Python validator, `interrupt()` approval, agentic RAG over runbooks, eval of 18 injected incidents vs a rule baseline, Streamlit UI | P0–P6 done 21 Oct; P7–P9 (UI, eval, docs) in progress; submit tomorrow | C §1, §4. Amir attaches the sprint's `PLAN.md` and `NOTES.md` separately (§7) |
| 2 | **Code factory** | Python CLI orchestrator running implement → acceptance → review → fix loops over headless CLI agents (Claude Code on 2 accounts, Cursor, later Gemini/Codex). Hash-locked acceptance scripts, a cross-family reviewer, human gates, a branch per step, a cost ledger | F0–F3 built (98 tests; real smoke calls 8/8 green); two real toy runs pending; F4 calibration, F5 hand-over, F6 bake-off not started | H |
| 3 | **governor-ask** | Governed NL→SQL module on the same foundation as triage. Roles with a PII policy, sqlglot validator, dry run, read-only executor, clarify interrupt, decision traces, MCP tools; 40-question golden set, baseline vs agent, holdout once. Spec G1–G9 written today, meant to be built **by the factory** | Spec only. G1 waits for the Sprint 4 code import (after submission) and factory F3 | G |
| 4 | **Capstone: "agentic data platform"** | Amir's intent: one foundation (`governor.core`) and several agents on it. `ask` (NL→SQL), `triage` (moved over from Sprint 4), maybe a semantic-layer `maintainer`. Long-term framing: a small, code-first "Databricks-lite" with EU AI Act–style decision traces | Intent only; no capstone spec yet | D, E, F, G §1 |
| 5 | Parked ideas | Retype (typing coach), job-ad collector, interview trainer, audio stem app, live score following, synth patch translation | Not part of this review except as distractions to fence | — |

---

## 3. Questions

Answer every question. Keep each answer tight: bullets, a table where it helps.

**Q1. Alignment and priorities.**
- Do initiatives 1–4 serve Amir's goal (§1)?
- Rank them by value to that goal per hour of his time.
- Name one thing to stop, one to defer and one to protect.

**Q2. Sprint 4, against tomorrow's submission and the defence.** Compare the attached sprint `PLAN.md`/`NOTES.md` with the Turing brief (App. A): task requirements 1–5, the evaluation criteria and the bonus (2 medium + 1 hard).
- List concrete gaps that can be closed in under a day, in priority order.
- List the 8 defence questions most likely to be asked, each with the one-line answer the build supports.

**Q3. The governor-ask spec (App. G).**
- (a) Design: validator rules, PII by column lineage, masking, `as_of`-pinned time, the policy-as-data split, the graph. Is anything wrong, missing or over-built?
- (b) Evaluation: is a 40-question golden set on a ~15-node mart meaningful? What would a hiring manager and a capstone mentor each challenge?
- (c) Acceptance scripts as gates: can a naive or wrong implementation pass any of G1–G9? Do any two checks contradict each other? Is any check impossible or flaky on Windows?
- (d) Step sizing: is each step doable by one agent in one session (≤ 60 min, ≤ 2 fix loops)? Which steps should be split or merged?

**Q4. The code factory (App. H).**
- Is it worth finishing before using it on governor-ask? What is the minimum (F3 real toy runs only? F4? F5?) before it builds real code?
- Where will it most likely fail on governor-ask (environment, dbt on Windows, lock/scope rules, budgets, reviewer quality)?
- Is building the factory a good use of capstone-month time, or a meta-work trap? Answer in both portfolio terms and course terms.

**Q5. Capstone scope.** Assume the capstone runs about 27 Oct – 23 Nov, with mentor review and an expectation of deployment, and that it should combine the whole course at a higher, ship-ready level (Amir's expectation, §1).
- Propose a scope that fits: what is in, what is a stretch, and what is explicitly out.
- Does "one foundation + ask + triage" make a coherent capstone, or two half-projects?
- What does "deployment" need here (API boundary, hosting, auth, secrets)? The kernel thesis (App. D §7) says "serve/ from day one", but the governor plan has no API layer. Resolve that.
- What must Amir confirm in the real capstone brief before locking scope?

**Q6. Schedule.** Write a day-level plan from Fri 23 Oct to Mon 23 Nov.
- Include the Sprint 4 submission and defence prep, factory toy runs, governor G1–G9 and the capstone milestones.
- Show buffers and the Turing Claude account expiry (about 11 Nov).
- Mark the days with weekday class hours, and the human gates (G2, G5, G9).

**Q7. Top 10 risks.** Give each a likelihood (L/M/H), impact (L/M/H), an early signal and a mitigation. Include the risk that factory-built code is code Amir cannot defend in a review.

**Q8. Consistency check across the documents.** List contradictions between appendices: dates, numbering, scope, stack, decisions. For each, say which document should win.

---

## 4. Output format

Return Markdown with exactly these sections:

1. `## Verdict`: 5 lines at most. Is the overall plan aligned, and what is the single most important change?
2. `## Q1` … `## Q8`: answers in order.
3. `## Comparison with Claude's concerns (§6)`: agree / disagree / missed, one line each.
4. `## Changes to make`: a numbered list of concrete edits. For each: which document (and section) or file, the edit, and why. Most important first; no more than 25.
5. `## Assumptions`: what you assumed where the pack was silent, especially about the capstone brief.

Length: aim for 2,500–4,000 words. No preamble.

---

## 5. Glossary

- **Gate:** a factory step that stops for Amir's approval (ground truth, security, release).
- **Acceptance script:** a deterministic script per step. Its last stdout line is JSON. It is hash-locked, so the implementing agent cannot edit it.
- **Implementer / reviewer:** factory roles that any agent profile can play; by default the reviewer comes from another model family.
- **`as_of`:** the timestamp of the green build. All relative dates resolve against it, never against `now()`.
- **Marts:** `dim_accounts`, `fct_invoices` (new in G1), `fct_revenue_daily`, `mrr_monthly`. These are the only tables analysts may query.

---

## 6. Claude's own concerns (read after your independent pass)

1. **The capstone timeline drifted.** The strategy docs (App. D §9, App. F §8) put the capstone in Jan–Feb. The course ends on 23 Nov (App. B), so the capstone is next month, overlapping with the triage defence, the factory work and governor-ask.
2. **Four initiatives, one person, four weeks**, alongside weekday classes, a job search, German practice and a band. The factory and governor-ask both started on the same day as the Sprint 4 crunch.
3. **The factory may be a meta-work trap.** It is valuable as a portfolio piece ("I evaluate my reviewers"), but F4 and F6 do nothing for the capstone grade. The minimum before real use is probably the F3 real toy runs.
4. **The governor plan has no API or deployment layer.** The kernel thesis says `serve/` (FastAPI) from day one, and the capstone likely expects deployment; the governor plan leaves both out. One of these documents is wrong for the capstone.
5. **The evaluation on a small mart is shallow for retrieval.** The plan admits this (App. G §6). Spider 2.0-DBT or a bigger mart is deferred, so the headline number is execution accuracy on 15 holdout questions, a small n with wide error bars.
6. **Defensibility of factory-built code.** A mentor review and interviews will probe design choices. If agents write most of G1–G9, Amir needs a deliberate knowledge-transfer step (reading the diffs, NOTES, a walkthrough). The plan does not include one.
7. **The Turing Claude account expires around 11 Nov**, mid-capstone. Its terms for personal portfolio work are unconfirmed, and code written there sits under the college organisation's settings.
8. **The triage → `core` migration is unplanned.** The governor plan says triage "moves in later", but no step specifies how. If the capstone is "one foundation, several agents", this step is load-bearing.
9. **Numbering confusion** (Sprint 3 vs 4, platform vs local names) has already cost time and may confuse graders; App. C notes it.
10. **The golden set comes before the agent and is frozen at G2.** That is good practice, but it means the G2 gate (Amir reviewing 40 gold SQLs) is a real time cost in a busy week. It may need its own calendar slot.

---

## 7. Attach separately (Amir)

Amir copies these into `docs/review/s4/` next to this file (git-ignored). Claude does not read the sprint folders.

- `s4/PLAN.md` (the Sprint 4 build spec)
- `s4/NOTES.md` (decision log; read "Current state" and the latest results first, older sections only on demand)
- `s4/README.md`, if a draft exists
- The capstone brief, when it is available. It changes Q5 and Q6 more than anything else. Until then, use Amir's expectation in §1.

---

# Appendices

| | Content |
|---|---|
| A | Turing College brief for the AI Agents sprint |
| B | Course facts (dates, modules, capstone context) |
| C | Project context: status, lessons, standing rules |
| D | Platform kernel thesis (excerpts) |
| E | Portfolio strategy (excerpts) |
| F | Idea 1 deep track: build ladder (excerpts) |
| G | governor-ask spec: PLAN, plan.yaml, policy, prompts, acceptance scripts |
| H | Code factory: status, F3 result, workflow, full spec |

---

# Appendix A: Turing College brief for the AI Agents sprint ("Sprint 4" project)

*Verbatim from Amir's Drive copy "Turing College - Sprint 4 requirments" (7 Oct 2026). The inspiration list of example agents is omitted.*

You will now build an app with an AI Agent of your choice on the backend. This is your opportunity to be creative and build something that interests you. Your agent should be useful and solve a real problem. Think about what kind of agent would be valuable to users and implement it.

[…inspiration ideas omitted…]

The best agents often come from identifying a specific problem you or others face and creating a solution for it. […]

The intended code editor for this project is VS Code.

If you feel confident, feel free to over-engineer the app by adding different things from the optional tasks and coming up with your own things. You can try making it as a portfolio project!

## Task requirements

1. **Agent Purpose**:
   - Define a clear purpose for your agent
   - Explain why this agent is useful
   - Identify the target users
2. **Core Functionality**:
   - Implement the main features that make your agent useful
   - Ensure the agent can perform its primary tasks effectively
   - Include necessary user interactions
3. **User Interface**:
   - Build a user-friendly interface for all functionalities
   - Make the interface intuitive and easy to use
4. **Technical Implementation**:
   - Use appropriate tools and libraries
   - Implement proper error handling
   - Ensure the agent can handle real-world usage
5. **Documentation**:
   - Provide clear documentation on how to use your agent
   - Include examples of common use cases
   - Explain any technical decisions made

## Optional tasks

After the main functionality is implemented and your code works correctly, and you feel that you want to upgrade your project, choose various improvements from this list. The list is sorted by difficulty levels.

Caution: Some of the tasks in medium or hard categories may contain tasks with concepts or libraries that may be introduced in later sections or even require outside knowledge/time to research outside of the course.

### Easy

1. Ask ChatGPT to critique your solution from the usability, security, and prompt-engineering sides.
2. Give the agent a personality: tweak responses to make them more formal, friendly, or concise based on user needs.
3. Provide the user with the ability to choose from a list of LLMs (Gemini, OpenAI, etc.) for this project.
4. Add the main OpenAI settings (temperature, max tokens, etc.) for the user to tune as sliders/fields.
5. Add an interactive help feature or chatbot guide.

### Medium

1. Calculate and display token usage and costs.
2. Implement long-term or short-term memory in LangChain/LangGraph.
3. Implement one more function tool that would call an external API.
4. Add user authentication and personalisation.
5. Implement a feedback loop where users can rate the responses, and use this feedback to improve the agent's performance.
6. Implement 2 extra function tools (5 in total). Have a UI for the user to either enable or disable these function tools. Develop a plugin system that allows users to add or remove functionalities from the chatbot dynamically.
7. Implement multi-model support (OpenAI, Anthropic, etc.).
8. Add at least one security guard to your app to prevent misuse. Design for usability — keep the developer settings (where you can select the model and system prompts) separate from the user experience, as your user may not be that familiar with LLMs.

### Hard

1. Agentic RAG: Think of a way to add RAG functionality to the LangChain/LangGraph application and implement it.
2. Add one of these LLM observability tools: LangSmith, Langfuse, or others.
3. Provide an AI evaluation report that proves the quality of your application using Ragas or DeepEval.
4. Create an agent that can learn from user feedback. This agent should be able to adjust its capabilities based on the feedback to improve future performance.
5. Implement an agent that can integrate with external data sources to enrich its knowledge. This could involve fetching additional data from APIs or websites.

## Evaluation criteria

### Problem definition
- The learner has a well-defined problem that they are aiming to solve with this project.
- The learner can articulate how the app they're building addresses the problem they identified.

### Understanding core concepts
- The learner understands the basic principles of how agents work.
- The learner can mention differences between different agent types.
- The learner can explain function calling implementation clearly.
- The learner demonstrates good code organisation practices.
- The learner can identify potential error scenarios and edge cases.

### Technical implementation
- The learner knows how to use a front-end library using their knowledge and/or external resources.
- The learner has created a relevant knowledge base for their domain if applicable.
- The learner has implemented appropriate security considerations.

### Reflection and improvement
- The learner understands the potential problems with the application.
- The learner can offer suggestions on improving the code and the project.
- The learner understands when to use prompt engineering, RAG, or agents.

### Bonus points
- For maximum points, the learner should implement at least 2 medium and 1 hard optional tasks.

---

# Appendix B: Course facts (capstone context)

**From the educational offer TC-1395_DE (23 Jul 2026):**

| Item | Value |
|---|---|
| Course | AI Engineering, Turing College GmbH, Berlin, 100% online, English |
| Start / end | **24 Aug 2026 – 23 Nov 2026** (13 weeks) |
| Teaching units | 520 UE, synchronous; classes Mon–Fri 09:00–16:30; teaching-free day 18 Nov 2026 |
| Modules | Foundations of LLM app development 128 UE · Building apps with LangChain, RAG and Streamlit 128 UE · AI Agents 128 UE · **AI Engineering Capstone Project 136 UE** |

**From the Turing College curriculum page (Confluence, read 22 Oct 2026):**
- Module 1 (required) has three sprints: Foundations of LLM Application Development; Building Applications with LangChain, RAGs and Streamlit; AI Agents.
- Further modules are specialisations: the AI Engineering Capstone Project and Natural Language Processing.
- The page gives no capstone requirements, deliverables or evaluation criteria.

**Not available:** the capstone brief. Amir should paste it from the Turing platform if he has access.

**Numbering note:** in the platform's terms, the current sprint is the third sprint of Module 1 (AI Agents). Its brief is titled "Sprint 4" in Amir's copy, and the local folder is `sprint-04-…`. The earlier RAG sprint is named "Sprint 3" locally, "Sprint 2" in its brief, and `AE.AFA.3.5` in the submission repo.

---

# Appendix C: Project context (`project-context.md`, as of 21 Oct 2026)

*Copy of the Claude Project doc that every planning chat reads first. Full text.*

**Read this first in every new chat in this project.** It holds the current state, the stack, the conventions, and what carries forward. It is maintained in place: when a sprint closes, its section is condensed and the next one is added.

What to learn and how to think about it lives in `knowledge-base.md`. Sprint 3's plan and specs (`sprint3-*.md`) are history now; read them only when a detail is needed.

Last updated 7 October 2026, at the close of Sprint 3. Amended 12 October 2026: peer-demo reference in §4, shell note in §5. Amended 20 October 2026: Sprint 4 topic chosen and build spec written (§1, §4). Amended 21 October 2026: workflow and token notes (§5), Sprint 4 progress (§1).

## 1. Status

| Sprint | Project | Result |
|---|---|---|
| 1. Foundations of LLM application development | **Interview Practice App**: Streamlit + OpenRouter, five system-prompt variants (prompting techniques), misuse guard, LLM-as-judge as the hard bonus | Submitted; defence 14 Sep 2026 |
| 3. LangChain, RAG and Streamlit (the Turing brief calls it the "Sprint 2" project, `125.md`) | **Cloud Architecture Advisor** (below) | Submitted 5 Oct 2026 after a short extension. Independent pre-review: 31/32 core, bonus met. **Review passed with a good mark.** |
| 4. Agents (LangGraph) | **dbt incident triage agent ("governor · triage")**. Spec and Cursor prompts P0–P9: `sprint4-build-spec.md` | In build from 20 Oct 2026; P0–P6 done and reviewed by 21 Oct. Target submit **Fri 23 Oct** (deadline Sun 25 Oct). Live state: `sprint-04-incident-triage/NOTES.md` |

**Course numbering is inconsistent.** The local folder is `sprint-03-…`, the brief file calls the project Sprint 2, and the submission repo is `AE.AFA.3.5`. Use the platform's name for the next sprint and note the mapping in `AGENTS.md`.

## 2. The Sprint 3 project in one page

A stakeholder describes a data problem in plain words. The app asks up to three multiple-choice questions, searches Google Cloud docs, and returns 2–3 costed options (GCP, Azure, Hetzner) with sources, warnings and a diagram.

**Pipeline** (`advise()` in `src/pipeline.py`):

1. Guard: `src/security.py`, length check plus about 12 regex patterns.
2. Slot extraction: gpt-5-nano, Pydantic schema, sets `in_scope` and `injection_suspected`.
3. Up to 3 questions, or defaults shown as assumptions.
4. Query translation: gpt-5-nano, original question plus 3–5 sub-queries.
5. Hybrid search: Chroma dense + BM25, RRF with k=60, pattern filter, at most 2 chunks per page, top 8.
6. LangChain v1 `create_agent` with 4 tools, `ToolStrategy(Blueprint)`, recursion limit 16, gpt-5-mini by default.
7. `finalise_blueprint`: Python recomputes the prices, re-runs the rules, drops unretrieved citations, aligns each option's pattern to the extracted one, then sorts.
8. Streamlit UI: `app.py`, `src/ui.py`.

**Stack:**

| Area | Choice |
|---|---|
| Environment | Python 3.12, uv |
| Framework and UI | LangChain v1, Streamlit |
| Models | OpenRouter (`ChatOpenAI` + `base_url`); usage accounting for the billed cost |
| Embeddings | `text-embedding-3-small` |
| Search | Chroma (local, cosine/HNSW, collection `gcp_docs`); rank-bm25 |
| Data shapes | Pydantic models |
| Visuals and export | Altair charts, Graphviz diagrams, fpdf2 PDF |
| Tests | pytest: 78 tests, 74 offline, 4 marked `llm` |

**Knowledge:**

- 39 Google Cloud pages plus 5 hand-written pattern notes, giving 695 chunks.
- `limits.json` holds quotas for 6 services.
- `prices.json` holds 36 SKUs in EUR, dated 2026-10-04, 21 of them verified.
- `patterns.json` holds the bill of materials for 4 patterns × 3 volumes.
- Refreshing is manual: run `src.ingest.fetch`, then `src.retrieval.index --build`, restart Streamlit, then re-run the evaluation.

**Evaluation** (`evaluation/run_eval.py`, results in `evaluation/eval_report.md`):

- **Golden set:** 10 hand-labelled questions paraphrased from PCA case studies and AWS/Whizlabs samples.
- **recall@5 by mode:** Dense 0.167 · BM25 0.067 · Hybrid 0.067 · Hybrid + query translation 0.400 · Hybrid + query translation + filter 0.467.
- **Pattern accuracy:** 10/10.
- **End-to-end service hit:** 1.0. This is a ceiling, not proof that retrieval helps.
- **Synthetic set:** 1.0 everywhere, so it cannot tell the modes apart.
- **Cost and speed:** about $0.004–0.0067 and 30–45 s per answer.

**Where things are:**

- Workspace: `C:\Users\amir0\Turing College\sprint-03-cloud-advisor\` contains `project/`, `PLAN.md` (prompts P0–P9), `FINAL_REVIEW.md`, and `project/NOTES.md` (decision log).
- Submitted copy: `TuringCollegeSubmissions/aakhav-AE.AFA.3.5`, branch `main`.

## 3. Lessons that carry forward

### Design

- **Three kinds of knowledge, three mechanisms.** Retrieval over prose for judgment. Exact lookup for facts. Python for numbers. Asking "is the answer a sentence, a row, or a number?" decides the mechanism.
- **The model never does arithmetic or has the last word on a fact.** A deterministic step after the model recomputes and checks. The app's own log showed 15 corrections in one session: a price off by a factor of two, wrong ease scores, wrong ops labels.
- **Typed everything:** Pydantic schemas for the model's output; `Literal`-typed tool arguments; plain values only in tools, never nested objects; structured output instead of "reply in JSON".
- **Model routing.** A small model (gpt-5-nano) for cheap structured jobs; the bigger model only for the agent step.
- **Prompts are files** (`prompts/*.md`), not strings in code.

### Retrieval

- **Query translation was the biggest lever** (recall 0.067 → 0.400). Stakeholders don't name products, so BM25 has nothing to match until the rewrite adds the product names.
- **Hybrid search is not automatically better.** RRF fuses ranks, not scores, so no rescaling is needed. It is unweighted for now; weights need a bigger test set to tune.
- **Chunking:** split on markdown headers; keep small tables whole; put a contextual "[service] section" header on each chunk; cap chunks per page so one big page can't flood the context.
- **The metadata filter** has to apply to both retrievers. A Chroma `where` clause alone would miss BM25.

### Evaluation

- **Build the golden set early.** Here it was built on the last weekend, which squeezed the analysis.
- A synthetic set written from its own target chunks scores 1.0 and proves nothing. Hand-labelled questions in stakeholder language are the real measure.
- Report ceilings honestly. The next measurement is an ablation (retrieval switched off) and a top-k sweep (5/8/12).

### Security

- **Two layers:** a free regex screen, then a flag set by the model.
- **A false positive is worse than a miss** when a second layer exists. "We need Redis to act as a cache" was refused at first.
- Measure catch rate (10/10) and false positives (0/5 after 3 fixes).
- Refusals never echo the input.
- Logs store user text only as a length and a hash, and rotate.

### Process

- **Workflow:** plan first; numbered Cursor prompts with acceptance checks; Claude reviews each step against the files and logs decisions in `NOTES.md`.
- **Before submitting:** an independent review against the original brief, scored in a separate file, then fix and re-export.
- **Submission:** the export script (`_submission/SUBMIT_S3.ps1`) builds a clean copy and scans for keys and drafts. In the Turing repo, `git pull origin main` first (the bot's starter commit), then commit and push. The git identity is now set globally on the laptop.
- **Deadline:** the Monday deadline slipped and needed an extension. Leave a buffer day for evaluation and README numbers.

## 4. Carry-forward for the agents sprint

- **Reusable as is:** the OpenRouter client with usage/cost accounting (`src/llm.py`); the input guard (`src/security.py`); the trace logger (`src/trace.py`); Pydantic output schemas; the eval harness pattern (golden set, then metrics, then a report file); the export script.
- **Natural agent upgrades of the advisor:** elicitation as a graph node that loops until the slots are filled; retrieval as a tool the agent can call again; a critic/validator node in place of the post-hoc `finalise_blueprint`; human-in-the-loop approval.
- **What to evaluate in an agent:** tool-call correctness, step count, cost per task, and success on a fixed task set.
- **Open improvements from Sprint 3:** retrieval-off ablation and top-k sweep; a reranker; weighted RRF; Architecture Center reference architectures in the corpus; provider-neutral pattern notes covering all three clouds; scheduled knowledge-base refresh with an eval gate; API plus authentication.
- **Long term:** Amir plans to grow the advisor concept into his own final project.
- **Sprint 4 research (7 Oct 2026):** a Google Doc "Agentic Data Platform – Research Hub" holds the agentic data/analytics market scan, the open-source "Databricks-lite" design for small teams, and the public-dataset survey.
- **Sprint 4 decision (20 Oct 2026):**
  - **Topic:** B, a dbt data-quality incident triage agent. GPT 5.6 Sol, Grok 4.7 and Argon (Gemini) all picked it independently.
  - **Build spec:** `sprint4-build-spec.md`: own synthetic SaaS-billing dbt project (jaffle-shop has no licence file); 18 injected incidents (6 frozen holdout) and a rule baseline; one `StateGraph` where code owns the edges, with a Python validator and an `interrupt()` approval; SQLite checkpointer, tested to resume across threads with `check_same_thread=False`; agentic RAG as the hard task; Langfuse as backup.
  - **Capstone path:** governed questions (A) next, on the same metadata store.
- **Peer reference (12 Oct 2026):** a cohort member's research assistant ("Astraeus") draws its LangGraph-shaped pipeline as a live **React Flow** graph (19 nodes, retry counts, replay, cost and citation chips, eval results in the app). **Suggested for Sprint 4:** a node registry plus streamed node events, rendered as Graphviz in Streamlit, as an optional extra.

## 5. Standing rules

- **Secrets:** never commit them. Keys live in the Windows user environment. Do not read `.env`.
- **Git:** Cursor agents never commit or push; Amir commits. Agents only modify the current sprint's folder.
- **Certification material:** never commit verbatim exam text. Paraphrase it and add a source link. No exam-dump sites.
- **Library versions:** LangChain v1 only (`create_agent`, `@tool`); no `AgentExecutor` or `langchain_classic`. LangGraph v1: `create_react_agent` is deprecated.
- **Reasoning models:** give structured output 2048+ tokens.
- **Shell on Amir's computer (Claude side):** use it for work on connected folders; stage files only for steps it can't do.
- **Agent workflow, token use, the review rubric and the code-factory plan:** `agentic-dev-workflow.md` (Appendix H).

---

# Appendix D: The platform kernel thesis (`platform-kernel-thesis.md`, 21 Sep 2026), excerpts

*Sections 1–5, 7, 9 and 10, in full. Omitted: §0 (a numbering note), §6 (a music idea outside this spine) and §8 (business wedges).*

## 1. The claim

**The Sprint 3 architecture advisor and Idea 1's governed analytics agent are the same machine pointed at different corpora.**

Both systems take an unstructured human request, ground it in a maintained body of structured and semi-structured knowledge, produce a **typed object** describing a proposed answer, validate that object with deterministic tools, repair it when validation fails, and emit an auditable trace with citations. The only things that genuinely differ are the corpus, the typed object, and the tool set.

If that is true, then you are not building two portfolio projects. You are building **one platform and instantiating it twice**, which is a materially stronger thing to say in an interview, and it is what "modular product design" has to mean to be worth anything.

## 2. The kernel: ten modules

The kernel contains **no domain knowledge**. Every cloud-specific or warehouse-specific fact lives in a product package (§4).

| Module | Contract | Why it is generic |
|---|---|---|
| `corpus/` | source adapter → `Document{id, text, metadata, provenance}` | Fetch, normalise, detect change, stamp `retrieved_at` and licence. Identical work whether the source is a docs site or a dbt manifest. |
| `index/` | `Document` → `Chunk[]` → vector + lexical stores | Chunking strategy is selected by `doc_type`, which is metadata, not code. |
| `retrieve/` | `Query` → `Context{chunks[], citations[]}` | Decomposition, hybrid search, metadata filters, fusion, rerank. Domain-blind. |
| `tools/` | typed function registry with JSON schemas | The boundary that keeps arithmetic and lookups away from the model. Registry is generic; the functions are per-product. |
| `spec/` | base classes for typed domain objects | `ArchitectureSpec` and `SemanticModel` are siblings, not strangers. |
| `reason/` | plan → retrieve → draft → validate → repair → render | The loop is the same; the prompts and schemas are injected. |
| `eval/` | golden sets, retrieval metrics, rubric judges, judge validation, ablation runner, error taxonomy | **The most transferable module you will write.** |
| `trace/` | every retrieval, tool call and model call: inputs, outputs, latency, cost, queryable | Debugging infrastructure and AI Act Article 12 evidence are the same artifact. |
| `serve/` | FastAPI boundary, OpenAPI schema | Put this in from day one even when Streamlit calls it in-process. §7. |
| `ui/` | thin clients over `serve/` | Streamlit now, Next.js later, both over the same API. |

**The falsifiable test of whether the modularity is real:** point `corpus/` at dbt manifests instead of cloud documentation, swap the object in `spec/`, and swap the functions in `tools/`. If `index/`, `retrieve/`, `reason/`, `eval/`, `trace/` and `serve/` need **no changes**, the abstraction is correct. If they need changes, the boundary is in the wrong place. Run this test in October, when Sprint 3 is delivered and Idea 1's first module lands.

## 3. The pivot object: design-time and run-time are the same schema

**Sprint 3 generates the spec from requirements.** A stakeholder brief becomes an `ArchitectureSpec`: components, flows, regions, SKUs, SLAs, decisions with citations.

**Idea 1 extracts the same shape from a live warehouse.** Schemas, dbt manifest and lineage become a description of what a data platform *actually is*: components, flows, grain, ownership, classification.

One produces the intended state. The other observes the actual state. The interesting operation, **diffing them**, falls out for free: *here is the platform you designed, here is the platform you have, here is the drift.* Note it, do not build it yet.

## 4. Repository layout

```
platform/                  # the kernel: no domain knowledge, no vendor names
  corpus/  index/  retrieve/  tools/  spec/
  reason/  eval/   trace/    serve/
products/
  architect/               # Sprint 3, design-time
  governor/                # Idea 1, run-time
    spec.py                #   SemanticModel, QuerySpec
    sources/               #   dbt manifest, information_schema, lineage
    tools/                 #   sql_dry_run, lineage_query, blast_radius
    rubrics/  golden/
apps/
  streamlit/               # now
  web/                     # Next.js, later
research/
```

**Do not build this structure during Sprint 3.** Build the sprint, then extract the kernel in October with working code in hand. The one exception is `serve/` (§7).

## 5. Why `eval/` is the crown jewel

Position on **evaluation and governance of LLM systems** rather than on building agents. **Retrieval-layer evaluation is cheap and answer-layer evaluation is expensive**, so the harness should make the cheap loop fast and the expensive loop rare. `eval/` is also the module most likely to outlive both products.

## 7. Interfaces before parallelism

**Agents cannot usefully parallelise on a monolith.** Two agents editing overlapping code produce merge conflicts and, worse, silent architectural drift. The module boundaries are **the precondition for parallel work**.

- Write the module interfaces by hand, in one sitting, before any parallel work starts. Function signatures and type definitions only.
- Put the **`serve/` API boundary in from day one**, even where Streamlit could call the functions directly in-process. It forces the kernel/UI separation, gives agents a stable contract to build against, and an OpenAPI schema is the most legible artifact you can hand another engineer. It is also how you learn "how an app is supposed to work and be shipped".
- Assign **one module per agent per session**, with the interface as the contract. Never two agents in one module.
- Keep `AGENTS.md` and `NOTES.md`, and add `PROJECT_CONTEXT.md` as the single source of truth for design decisions.

## 9. What this means for the next three months (as written on 21 Sep)

| Window | Kernel work | Product work |
|---|---|---|
| Now → 5 Oct | None | Sprint 3 delivered |
| Oct | Extract `corpus/ index/ retrieve/ eval/ trace/ serve/` from the sprint code; run the §2 swap test | `governor` R1–R2: metadata harvester + column-level lineage, both deterministic |
| Nov (Sprint 4, agents) | `reason/` generalised; `tools/` over MCP | `governor` R3–R4: schema retrieval, NL→SQL with dry-run and repair |
| Dec–Jan | `eval/` hardened | `governor` R5: Spider 2.0-DBT score and error taxonomy |
| **Jan–Feb (capstone)** | `trace/` as Article 12 evidence | `governor` R6–R7: governance layer, semantic-layer maintainer |

## 10. Open decisions (as written on 21 Sep)

1. Does the kernel become a public repository? Decide in November.
2. Name the platform.
3. Postgres + pgvector for everything, or ChromaDB?
4. Does the drift-diff idea (§3) become the capstone thesis? Decide before the capstone scope locks.
5. Which business wedge, if any, gets a validation conversation?

---

# Appendix E: Portfolio strategy (`project-portfolio-strategy.md`, 11 Sep 2026), excerpts

*The TL;DR, §1, §2 and §6, in full except for the leaderboard table. Omitted: §3–§4 (other ideas), §7 (course topics) and the sources list.*

## TL;DR

1. Idea 2 (system-design trainer) is already shipping as the Sprint 1 app. Stop at v1, then demote it to an instrument: an eval playground and synthetic-data generator for Idea 1.
2. **Idea 1 is the right long-term bet, but it is four products in a trenchcoat** (catalog, lineage, dbt agent, NL→SQL + viz). Narrow it to one spine, a *semantic-layer-grounded analytics agent*, and treat catalog and lineage as the context supply chain feeding it.
3. Idea 3 (score following) is worth doing for motivation, with near-zero career transfer. Fence it to weekends.
4. The genuine unifier is not the domain but the **evaluation**.
5. **Position on evaluation and governance of LLM systems rather than on building agents.**

## 1. What the course gives you to work with

Verified against Turing College's published curriculum (Sep 2026): 4 modules, 15 sprints, 3–4 months at ~10 h/week. M1 Foundations; M2 LangChain + RAG; M3 AI Agents (LangGraph, **MCP**, memory); **M4 Capstone: self-directed concept → deployment, 1:1 senior mentor review.**

## 2. Idea 1: agentic data governance

**The honest problem.** Each of the four parts is a funded company (Atlan/Alation/Select Star; Monte Carlo/Euno; Paradime/dbt Labs; Wren AI/Vanna). Four shallow demos read worse than one deep one.

**The spine:** an analytics agent is only as good as the semantic model it is grounded in: metric definitions, join paths, grain, column semantics, glossary, freshness. That is a data engineering problem wearing an AI costume, where a decade of DE experience is an unfair advantage. **Catalog and lineage stop being products and become the context supply chain.**

**Evidence:** on Spider 2.0, the Snowflake variant is near saturation and **the dbt variant is the hardest remaining one** (about 66% top score), so the unsolved part of enterprise text-to-SQL is Amir's day job. The single strongest portfolio artifact would be **a reported score on Spider 2.0-DBT** with an error taxonomy.

**German-market wedge: the EU AI Act.** Article 10 (data governance: glossary with owners, lineage, quality monitoring) and Article 12 (record-keeping: queryable *decision traces*, not plain inference logs).

**What to build:** a deterministic grounding layer (dbt manifest → DAG; sqlglot → column lineage; no LLM there); schema/metric retrieval; an agent loop (plan → retrieve schema → draft SQL → validate with dry run / EXPLAIN / cost → execute → self-correct), tools over MCP; governance (decision traces, PII tagging, glossary with ownership, blast radius); eval (execution accuracy + exact-set-match on Spider 2.0-DBT, plus an ambiguity suite).

**Risk:** scope. A 12-month vision against 3 months of course. Build in that order; each layer is independently demoable.

## 6. What you are not considering

- **a)** Position on evaluation, not on agents. Few graduates can answer "how do you know it works?" with anything but a demo.
- **b)** Narrow fallback: a "semantic-layer maintainer" agent (detect drift, propose descriptions/classifications, open the PR).
- **c)** Data-quality incident triage: dbt test failures + lineage → incident summary, blast radius, owner. *(This became Sprint 4.)*
- **d)** The AI Act compliance angle as the business idea.
- **e)** Don't over-invest in fine-tuning or multi-agent orchestration; stay single-agent-with-tools until you can name the failure multi-agent fixes.

---

# Appendix F: Idea 1 deep track (`idea1-deep-track-plan.md`, 21 Sep 2026), excerpts

*Sections 1, 4, 8 and 9. Omitted: the study curriculum, research-agent rules, capability gaps and the frontend track.*

## 1. The narrowing principle

**Do not replicate Databricks. Replicate Unity Catalog's governance model, and only the parts an agent needs in order to be correct**: the catalogue and metadata model, lineage, and policy. Test for any piece of work: **does this make the agent's answers more correct or more auditable?** If not, it is reading, not building.

## 4. The build ladder for `governor`

| Rung | What | Notes |
|---|---|---|
| R1 | Metadata harvester: schemas and dbt `manifest.json` into a Unity-Catalog-shaped store | Deterministic. No LLM. |
| R2 | Column-level lineage via sqlglot AST parsing | Deterministic. Keep the LLM out. |
| R3 | Schema and metric retrieval over a large warehouse | Reuse of the Sprint 3 kernel against a different corpus (the swap test). |
| R4 | NL→SQL agent: plan → retrieve schema → draft → dry-run → repair | Sprint 4 (agents) is the natural window. Tools over MCP. |
| R5 | Evaluation against Spider 2.0-DBT, with error taxonomy | The strongest single artifact. |
| R6 | Governance layer: classification, policy, decision traces, blast-radius analysis | EU AI Act Art. 10/12 story. Capstone material. |
| R7 | Semantic-layer maintainer agent | Strong standalone demo if R5/R6 run long. |

Each rung is independently demoable and stoppable. If you stop after R4 you still have a complete project.

## 8. Timeline (as written on 21 Sep)

| Window | Course | Deep track |
|---|---|---|
| Now → 5 Oct | Sprint 3 delivered | Nothing |
| Oct | Between sprints | Kernel extraction; R1 + R2; toy transaction log and catalogue; frontend weeks 1–2 |
| Nov | Sprint 4: agents, LangGraph, MCP | R3 + R4; frontend weeks 3–4 |
| Dec | Sprints continue | R5: Spider 2.0-DBT evaluation |
| **Jan** | Capstone scoping | R6 |
| **Feb** | Capstone | R6/R7 complete; mentor review |

## 9. Open decisions (as written on 21 Sep)

1. Which warehouse does `governor` run against? Spider 2.0-DBT's databases bring ground truth for free.
2. How faithful should the toy catalogue be to Unity Catalog's API? Recommendation: close on the namespace and securable model, loose elsewhere.
3. Does lineage emit OpenLineage from the start? Recommendation: yes.
4. Is the toy transaction log in scope at all?
5. How much German-language surface does the portfolio need?

---

# Appendix G: governor (governor-ask) spec, as committed 22 Oct 2026 (`2ed649f`)
*Files from `C:\Users\amir0\portfolio\governor`. Nothing has been implemented yet.*

## G.1 `PLAN.md`

### governor: an agentic data platform on one foundation (first module: governor-ask)

*Spec written 22 Oct 2026 in the Turing College Project. Built by the code factory (`..\factory`). This file is the source of truth for this repo; step prompts never point here, they name files.*

**Seed:** factory `PLAN.md` §10 (governor-ask brief), `platform-kernel-thesis.md` (kernel/product split), `idea1-deep-track-plan.md` §4 (build ladder R1–R7), Sprint 4 build spec §3–§6 (fixture, metadata store, tools, PII rule).

---

#### 1. What this repo is

A small, code-first "Databricks-lite" for a small data team: **one foundation** (warehouse fixture, catalog/metadata store, lineage, ownership, PII policy, LLM client, traces) and **modules** that put agents on top of it.

| Module | Status | What it does |
|---|---|---|
| `core` | G1 (imported from Sprint 4) | Billing mart fixture (dbt + DuckDB), harvester → `meta.duckdb`, lineage, owners, PII tags, OpenRouter client with cost, trace, input guard |
| `ask` (**governor-ask**) | G2–G9, this plan | Governed NL→SQL: retrieve → plan → clarify → draft → validate → dry-run → repair → safe execute → answer → decision trace. MCP tools. |
| `triage` | later (after the Sprint 4 defence) | The Sprint 4 incident-triage agent moved onto `core` |
| `maintainer` | capstone candidate (R7) | Semantic-layer maintainer: drift → proposed descriptions/classifications |

The capstone story: one metadata store and one policy, three agents (answer questions, explain incidents, maintain the catalog), every decision traced.

**Why one foundation:** the kernel thesis's swap test. If `ask` needs no changes to `core` beyond additions, the boundary is right.

---

#### 2. Locked decisions

| # | Decision | Why |
|---|---|---|
| A1 | Python 3.12 + uv, single package `governor` with subpackages `core`, `eval`, `ask`. Streamlit app in `apps/streamlit/`. | One install, clear module boundaries for agents (one module per step). |
| A2 | Data = the Sprint 4 SaaS-billing mart (seed 42), imported by `scripts/import_foundation.ps1` after the Sprint 4 submission. One new mart, `fct_invoices`, added in G1. | One foundation for every module. Analysts query marts only, so invoices need a mart. |
| A3 | Engine DuckDB + dbt-duckdb, as Sprint 4. The warehouse is opened `read_only=True` by every query path. | Same as S4; read-only is enforced by the connection, not only by the validator. |
| A4 | Time is pinned: every relative date ("last quarter") resolves against `artifacts/green/as_of.txt`, never `now()`. | Workflow rubric Q4. |
| A5 | **Python owns** the allowlist, policy decisions, SQL validation, dry-run, execution, row caps, lineage, freshness and every number in the answer. **The model owns** interpreting the question, the plan, the SQL draft and the wording. | Model never has the last word on a fact (Sprint 3 lesson). |
| A6 | Policy is data: `knowledge/policy.yaml` (column → PII tag, from S4) + `knowledge/access.yaml` (allowlist, roles, grants, caps), owned by Amir. Code reads them; prompts never restate them. | Changing policy is a data change with a review, not a prompt edit. |
| A7 | Roles: `analyst` (PII only inside `COUNT`/`COUNT(DISTINCT …)`; never selected, filtered, grouped, joined on) and `finance_admin` (PII selected values masked as `'***'` unless a field-level grant exists). | Spec §10. Two roles exercise refuse, aggregate and mask. |
| A8 | SQL validator = sqlglot (duckdb dialect): one statement, SELECT/WITH only, no table functions or file reads, no `SELECT *`, allowlisted tables and columns, role policy by column lineage, LIMIT injected/capped. | Spec §10; `SELECT *` would hide PII from the column check. |
| A9 | Models via OpenRouter, Sprint 3/4 client: `openai/gpt-5-nano` (guard flag, plan), `openai/gpt-5-mini` (draft SQL, repair, answer wording); structured output with ≥ 2048 max tokens. Embeddings as Sprint 3. | Model routing lesson; keys from the Windows env. |
| A10 | Graph = one LangGraph v1 `StateGraph`, code owns the edges; `interrupt()` for clarification; SqliteSaver checkpointer (`check_same_thread=False`). | Sprint 4 pattern, proven to resume across processes. |
| A11 | Decision trace = one row per question in `artifacts/traces.duckdb` (fields §5). Inspired by EU AI Act Art. 12, not a compliance claim. | Auditable answers are the governance headline. |
| A12 | Golden set (40 questions) and split (25 tune / 15 holdout) are frozen at G2, before any agent prompt exists, and reviewed by Amir. Never relabelled from model output. Later steps cannot touch `evaluation/golden/` (scope guard). | Workflow rubric Q6. |
| A13 | The holdout is run once per system, logged in `evaluation/holdout_runs.log`; the harness refuses a second run without `--force-holdout`. | Honest numbers. |
| A14 | Every test and every acceptance check runs offline with fake/scripted LLMs. Only G9 calls models (eval budget ≤ $3). | Acceptance must be deterministic (factory §4). |

---

#### 3. Layout

```
governor/
  PLAN.md AGENTS.md NOTES.md STATUS.md README.md PROVENANCE.md plan.yaml
  plan/prompts/G1..G9.md   plan/accept/accept_g1..g9.py  _common.py     # locked by `factory lock`
  scripts/import_foundation.ps1                                          # HUMAN, after the S4 submission
  fixture/            generate_raw.py load_raw.py build_green.py billing_mart/   (from S4, + fct_invoices)
  knowledge/          owners.yaml policy.yaml (S4)  access.yaml (Amir)  metrics.yaml (G2)
  src/governor/
    core/             paths.py warehouse.py llm.py security.py trace.py harvest.py lineage.py retrieval.py
    eval/             checker.py harness.py run.py pii.py                  (G2–G3; generic, reusable by triage)
    ask/              baseline.py catalog.py retrieval.py validator.py policy.py executor.py
                      schemas.py graph.py run.py service.py mcp_server.py prompts/*.md
  apps/streamlit/     app.py pages/
  evaluation/         golden/{questions.yaml,split.json,FROZEN.sha256}  reports/  eval_report.md  holdout_runs.log
  artifacts/          (git-ignored) green/ meta.duckdb catalog_cards.jsonl traces.duckdb checkpoints.sqlite
  tests/              core/ eval/ ask/ ui/ mcp/
```

`governor.core.paths` resolves every path from the repo root (override `GOVERNOR_ROOT`). `governor.core.warehouse.connect()` is the only way to open the warehouse: read-only, `search_path` on the marts schema. Nothing hard-codes a Sprint 4 or Windows path.

---

#### 4. The graph (G6)

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

#### 5. Decision trace row

`trace_id, ts, role, question_hash, question_len, retrieved_ids, plan_json, sql_attempts[{sql, validator_ok, reasons, dry_run_ok, error}], policy_decisions, executed_sql, row_count, result_hash, answer, outcome (answered|clarified|refused|unanswerable|error), models, tokens_in, tokens_out, cost_usd, latency_s, human_feedback`.

The question text itself is stored only when `GOVERNOR_TRACE_TEXT=1` (default: length + hash, as Sprint 3 logs).

---

#### 6. Evaluation (the headline)

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

#### 7. Steps (factory)

| Step | What | Tier | Gate |
|---|---|---|---|
| G1 | Foundation from the S4 import: package `governor.core`, green build, `fct_invoices`, harvester → `meta.duckdb`, tests, provenance | mechanical | — |
| G2 | `metrics.yaml`, golden set + gold SQL, result checker, frozen split | design | **HUMAN (ground truth)** |
| G3 | Eval harness + metrics + self-test systems; baseline | design | — |
| G4 | Catalog + metric cards, hybrid retrieval, recall@k on gold tables | mechanical | — |
| G5 | SQL validator, role policy, dry-run, read-only executor | design | **HUMAN (security)** |
| G6 | The graph: clarify interrupt, repair, answer from results, decision traces, CLI | design | — |
| G7 | Streamlit: Ask, Trace explorer, Developer | mechanical | — |
| G8 | MCP server (stdio, official SDK): 5 read-only tools | mechanical | — |
| G9 | Eval: tune, freeze, holdout once; eval report; README | design | **HUMAN (release)** |

Default roles come from `%USERPROFILE%\.factory\agents.yaml` (design: claude-tc-opus implements, cursor-grok reviews; mechanical: cursor-composer implements, claude-tc-sonnet reviews).

---

#### 8. HUMAN steps outside the factory

1. **After the Sprint 4 submission:** `powershell -ExecutionPolicy Bypass -File scripts\import_foundation.ps1` from this repo. It copies only the listed files, never `.env`, data or `artifacts/`, and writes `PROVENANCE.md`. Paste its summary into NOTES.
2. Review `knowledge/access.yaml` (it is yours) and commit.
3. Factory F3 must be done; then `factory plan validate plan.yaml`, `factory lock`, `factory run --until-gate`.
4. Gates: G2 (read all 40 gold SQLs and the metric definitions), G5 (read the validator's reasons on the locked cases), G9 (read the report and README).

#### 9. Open questions

- Does `int_invoices_with_payments` carry everything `fct_invoices` needs? (G1 finds out; the mart may need a join to `dim_accounts` for country.)
- Exact Sprint 4 file names may differ from the S4 spec §2; the import script reports what it found.
- Langfuse or FastAPI `serve/` boundary: not in this plan (capstone).

## G.2 `plan.yaml` (the factory plan)

```yaml
# governor-ask on the shared foundation. Spec: PLAN.md (§7 steps). Locked with `factory lock`.
project: governor
notes: NOTES.md
agents: AGENTS.md
defaults:
  max_fix_loops: 2
  timeout_min: 60
  run_budget_usd: 40          # notional on subscriptions; a safety cap per `factory run`
  step_budget_usd: 12
  review_budget_usd: {design: 2.0, mechanical: 0.75}
# no `roles`: the design / mechanical lists come from %USERPROFILE%\.factory\agents.yaml
steps:
  - id: G1
    title: Foundation from the Sprint 4 import (core package, green build, fct_invoices, metadata store)
    tier: mechanical
    prompt: plan/prompts/G1.md
    accept: plan/accept/accept_g1.py
    allowed_paths: [src/governor/__init__.py, src/governor/core/, fixture/, knowledge/owners.yaml, knowledge/policy.yaml, knowledge/access.yaml, tests/core/, tests/conftest.py, pyproject.toml, uv.lock, PROVENANCE.md, .gitignore]
    human_gate: false
    review_focus: "imported code keeps provenance and changes are listed; no Sprint 4 or absolute paths; fct_invoices pins time to as_of, never now(); access.yaml only renamed to real columns, policy unchanged; mart PII tags really propagate"
  - id: G2
    title: Metric definitions, golden set with gold SQL, result checker, frozen split
    tier: design
    prompt: plan/prompts/G2.md
    accept: plan/accept/accept_g2.py
    allowed_paths: [knowledge/metrics.yaml, evaluation/golden/, src/governor/eval/, tests/eval/, pyproject.toml, uv.lock]
    human_gate: true
    review_focus: "gold SQL answers the question as worded (grain, filters, as_of-relative dates); categories are unambiguous; ambiguous questions really lack a slot; policy expectations follow access.yaml; checker cannot pass a wrong result (rubric Q1, Q6, Q7)"
  - id: G3
    title: Evaluation harness, metrics, self-test systems, baseline
    tier: design
    prompt: plan/prompts/G3.md
    accept: plan/accept/accept_g3.py
    allowed_paths: [src/governor/eval/, src/governor/ask/__init__.py, src/governor/ask/baseline.py, src/governor/ask/prompts/baseline.md, src/governor/ask/llm_testing.py, tests/eval/, tests/ask/, pyproject.toml, uv.lock]
    human_gate: false
    review_focus: "a naive system cannot score well (oracle/null/leaky behave as specified); PII leak detection uses column lineage plus value scan; holdout guard works; the baseline really has no retrieval or validator (rubric Q1, Q2)"
  - id: G4
    title: Catalog and metric cards, hybrid schema retrieval, recall@k on gold tables
    tier: mechanical
    prompt: plan/prompts/G4.md
    accept: plan/accept/accept_g4.py
    allowed_paths: [src/governor/ask/catalog.py, src/governor/ask/retrieval.py, src/governor/core/retrieval.py, tests/ask/, pyproject.toml, uv.lock]
    human_gate: false
    review_focus: "cards are built from meta.duckdb and metrics.yaml, not hand-written; cards contain no golden questions or gold SQL; recall is computed from gold SQL tables, not from the question text (rubric Q2, Q5)"
  - id: G5
    title: SQL validator, role policy, dry-run, read-only executor
    tier: design
    prompt: plan/prompts/G5.md
    accept: plan/accept/accept_g5.py
    allowed_paths: [src/governor/ask/validator.py, src/governor/ask/policy.py, src/governor/ask/executor.py, tests/ask/, pyproject.toml, uv.lock]
    human_gate: true
    review_focus: "every locked case decided for the right reason; PII checks follow column lineage through aliases, CTEs, subqueries and functions; masking cannot be bypassed; the connection is read-only even if the validator is wrong; no policy text duplicated from access.yaml into code"
  - id: G6
    title: The graph (clarify interrupt, repair, answer from results, decision traces, CLI)
    tier: design
    prompt: plan/prompts/G6.md
    accept: plan/accept/accept_g6.py
    allowed_paths: [src/governor/ask/, src/governor/core/trace.py, tests/ask/, pyproject.toml, uv.lock]
    human_gate: false
    review_focus: "code owns the edges; numbers in the answer come from result rows; refusals never echo input; trace rows complete; prompts contain no golden questions; the clarify interrupt resumes in a new process (rubric Q2, Q4, Q8)"
  - id: G7
    title: "Streamlit pages: Ask, Trace explorer, Developer"
    tier: mechanical
    prompt: plan/prompts/G7.md
    accept: plan/accept/accept_g7.py
    allowed_paths: [apps/streamlit/, src/governor/ask/service.py, tests/ui/, pyproject.toml, uv.lock]
    human_gate: false
    review_focus: "the UI calls governor.ask.service only (no SQL or policy logic in pages); role picker really changes the policy; graph compiled once per session"
  - id: G8
    title: MCP server with 5 read-only tools
    tier: mechanical
    prompt: plan/prompts/G8.md
    accept: plan/accept/accept_g8.py
    allowed_paths: [src/governor/ask/mcp_server.py, src/governor/ask/service.py, tests/mcp/, docs/mcp.md, pyproject.toml, uv.lock]
    human_gate: false
    review_focus: "tools reuse the validator and executor (no second policy path); run_governed_query cannot write; role defaults to analyst; tool descriptions do not leak policy internals"
  - id: G9
    title: Evaluation (tune, freeze, holdout once), eval report, README
    tier: design
    prompt: plan/prompts/G9.md
    accept: plan/accept/accept_g9.py
    allowed_paths: [src/governor/ask/, src/governor/eval/, evaluation/reports/, evaluation/eval_report.md, evaluation/holdout_runs.log, README.md, docs/, tests/]
    human_gate: true
    review_focus: "holdout run once after prompts froze; numbers in README equal the report; limits stated honestly (small catalog, single warehouse); agent vs baseline per category; no PII leak in agent runs (rubric Q6, Q8)"
```

## G.3 `knowledge/access.yaml` (human-owned policy)

```yaml
# Access policy for governor-ask. Human-owned (Amir). Code reads it; prompts never restate it.
# PII tags come from knowledge/policy.yaml via the metadata store (meta.duckdb columns.pii_tag).
version: 1

allowlist:              # analysts and admins query marts only
  models: [dim_accounts, fct_invoices, fct_revenue_daily, mrr_monthly]

limits:
  default_limit: 100    # injected when a query has no LIMIT
  row_cap: 1000         # LIMIT above this is lowered to it
  timeout_s: 10         # per query, enforced by the executor

mask_value: "***"

roles:
  analyst:
    pii: aggregate_only   # PII columns only inside COUNT(...) / COUNT(DISTINCT ...); never selected, filtered, grouped or joined on
    grants: []
  finance_admin:
    pii: mask             # PII values in the output are replaced by mask_value unless granted below
    grants:
      - dim_accounts.contact_email
```

## G.4 `AGENTS.md`

```markdown
# AGENTS.md: rules for every agent in this repo

This repo is **governor** (core + ask modules), built step by step by the code factory. Your step prompt names the files you need; read those, not whole documents.

## Hard rules
- **Never commit, push, branch or stash.** The factory commits.
- **Never read `.env` or `.env.*`**, never print, log or echo keys or env values. Keys are read by name from the environment (`OPENROUTER_API_KEY`).
- **Change only the paths your step allows** (plus `NOTES.md`). Never edit `plan/` (locked) or, from G3 on, `evaluation/golden/`.
- Never read the Turing College folders. Everything from Sprint 4 is already in this repo (see `PROVENANCE.md`).
- `knowledge/access.yaml` and `knowledge/policy.yaml` are human-owned policy. Code reads them; prompts never restate them.
- Python 3.12 + uv. LangChain v1 / LangGraph v1 only: no `AgentExecutor`, no `langchain_classic`, no `create_react_agent`.
- Prompts live in `src/governor/ask/prompts/*.md`, never in code strings. Pydantic for every model output and tool argument.
- Time: resolve relative dates against `artifacts/green/as_of.txt`. Never `now()`, `current_date` or `datetime.now()` in data logic.
- Tests run offline: fake or scripted LLMs, no network. Only the G9 evaluation calls real models.
- DuckDB: open the warehouse `read_only=True`; close every connection (Windows file locks).

## Golden set (from G3 on)
- Never read `evaluation/golden/questions.yaml` to write prompts, examples or tests. Code loads it through `governor.eval`; tests use their own small fixtures.
- Never copy golden questions or gold SQL into prompts. The acceptance scripts check for overlap.

## Never read whole (query or skip instead)
- `uv.lock`, `artifacts/**` (`manifest.json`, `catalog.json`, `run_results.json`, `sources.json`, `*.duckdb`, `*.sqlite`), `fixture/billing_mart/target/`, `.factory/`, `NOTES-archive.md`, any data file over 200 KB. Use `duckdb` with `LIMIT`, or `python -c` with `json` and a key filter.

## Output rules
- Quiet commands: `uv run pytest -q`; dbt logs to a file; print summaries only.
- Paste results, not logs.

## Coordination
- `NOTES.md`: current state, open questions, last two steps' result + additions. Under 150 lines. Add a short "Gn result" when you finish.
- `PROVENANCE.md`: every file imported from Sprint 4, with its source and what was changed.
```

## G.5 Step prompts (what the implementer receives, after the factory's fixed header)


### `plan/prompts/G1.md`

```markdown
# G1: Foundation from the Sprint 4 import

Sprint 4 code was copied in by `scripts/import_foundation.ps1`; `PROVENANCE.md` lists every file and its origin. Turn it into the shared foundation package `governor.core`. Keep imported code as close to the original as possible.

Build:
1. `pyproject.toml`: add the deps the imported code needs (dbt-core~=1.12, dbt-duckdb~=1.11, duckdb, pyyaml, pydantic, faker, langchain~=1.4, langchain-openai, rank-bm25, numpy, sqlglot). `uv run` installs them.
2. `src/governor/core/__init__.py` and `src/governor/core/paths.py`: `ROOT` (repo root, override with env `GOVERNOR_ROOT`), `ARTIFACTS`, `GREEN` (`artifacts/green`), `WAREHOUSE` (`artifacts/green/warehouse.duckdb`), `META` (`artifacts/meta.duckdb`), `KNOWLEDGE`, `TRACES` (`artifacts/traces.duckdb`), and `as_of() -> datetime` read from `GREEN/as_of.txt`.
2b. `src/governor/core/warehouse.py`: `connect() -> duckdb.DuckDBPyConnection` opens `paths.WAREHOUSE` with `read_only=True` and sets `search_path` to the schema that holds the marts, so `SELECT ... FROM dim_accounts` works unqualified. Every later query path uses it.
3. Imported modules: imports `triage.*` → `governor.core.*`; every path through `governor.core.paths`. No string containing `sprint-04`, `Turing College` or a drive letter anywhere in `src/`, `fixture/`, `tests/`.
4. `fixture/build_green.py` works from this repo: `uv run python fixture/build_green.py` loads raw data, runs `dbt build`, `dbt source freshness`, `dbt docs generate`, and writes `artifacts/green/` (manifest, run_results, sources, catalog, `warehouse.duckdb`, `as_of.txt`). Deterministic (seed 42). Close DuckDB connections before dbt runs.
5. New mart `fct_invoices` in the dbt project (marts folder, description, `meta.owner`, column descriptions, `unique` + `not_null` on `invoice_id`). Columns exactly: `invoice_id, account_id, subscription_id, country, issued_at, amount_eur, status, paid_amount_eur, last_paid_at, is_fully_paid, days_outstanding`. `days_outstanding` = days from `issued_at` to the build's as_of (dbt var `as_of`, passed by `build_green.py`), 0 when fully paid. Never `now()`, `current_date` or `current_timestamp` in the SQL.
6. `dim_accounts` must expose `account_id, company_name, contact_name, contact_email, country`.
7. Harvester CLI: `uv run python -m governor.core.harvest artifacts/green --out artifacts/meta.duckdb` fills tables `nodes, columns, edges, tests, exposures` (Sprint 4 schema) and prints counts.
8. PII tags on marts: every mart column that carries a PII source column (e.g. `dim_accounts.contact_email`, `contact_name`) has the same `pii_tag` in `meta.duckdb.columns`. Do it by adding entries to `knowledge/policy.yaml` or by propagating along column lineage; say which in NOTES.
9. `knowledge/access.yaml`: if a listed model or column has a different real name, rename it there and note it. Do not change roles, limits or grants.
10. Tests in `tests/core/`: the imported tests pass with the new imports; add `test_paths.py`, a test for `warehouse.connect()` (unqualified mart names, writes refused) and a test that `fct_invoices.days_outstanding` uses as_of.
11. `PROVENANCE.md`: for every adapted file, replace "unchanged" with "changed: <one line>". List new files in a "New in G1" section.

Read: `PROVENANCE.md`, `AGENTS.md`, `knowledge/access.yaml`, `fixture/build_green.py`, the dbt project's `models/` (yml + sql), `src/governor/core/harvest.py`.
Do not read `artifacts/` files whole (query with duckdb or json + key filters).

Done when `plan/accept/accept_g1.py` passes.
```

### `plan/prompts/G2.md`

```markdown
# G2: Metric definitions, golden set, result checker, frozen split

This step defines ground truth for governor-ask. A human reviews it at the gate. Nothing here may come from a model's answers.

Build:
1. `knowledge/metrics.yaml`: `metrics:` list, at least 8, each `{id, label, definition, sql, grain, time_column, synonyms: [...], owner}`. `sql` is a SELECT over allowlisted marts only (`knowledge/access.yaml`). Cover at least: mrr, arr, active_subscriptions, churned_subscriptions (monthly), invoiced_revenue, collected_revenue, outstanding_receivables, overdue_invoices (> 30 days outstanding).
2. `evaluation/golden/questions.yaml`: top-level `as_of` (copy of `artifacts/green/as_of.txt`) and `questions:` with exactly 40 items:
   `{id: Q001.., role: analyst|finance_admin, category, question, expect, gold_sql, order_matters, rel_tol, missing_slot, notes}`
   - categories and counts: simple 6, join 6, time_grain 6, metric 6, ambiguous 5, policy 6, unanswerable 5.
   - `expect`: `answer` (simple, join, time_grain, metric); `clarify` (ambiguous, with `missing_slot` such as time_range, metric, grain, entity); `refuse` | `aggregate` | `mask` (policy, following `knowledge/access.yaml` for the role; include both roles); `unanswerable` (data not in the marts).
   - `gold_sql` is required for answer/aggregate/mask and absent otherwise. Marts only, explicit columns (no `SELECT *`), relative dates computed from the literal as_of date, never `now()`. For `mask`, gold SQL outputs the mask value from access.yaml in place of the masked column.
   - Questions are worded the way a finance or ops analyst would ask; do not name tables or columns in the question.
3. `evaluation/golden/split.json`: `{"tune": [25 ids], "holdout": [15 ids]}`, disjoint, stratified so every category appears in both.
4. `evaluation/golden/FROZEN.sha256`: two lines in sha256sum format, `<hex>  questions.yaml` and `<hex>  split.json`.
5. `src/governor/eval/__init__.py`, `src/governor/eval/golden.py` (pydantic models + `load_golden()`, `load_split()`, `verify_frozen()`), `src/governor/eval/checker.py`:
   - `compare(gold_rows, pred_rows, *, order_matters=False, rel_tol=1e-6) -> Comparison` with `.equal: bool` and `.reason: str`. Rows are lists of tuples; column order is ignored (match columns by permutation when counts agree); numbers compare with relative tolerance; None equals None only.
   - `run_gold(sql) -> list[tuple]`: executes through `governor.core.warehouse.connect()` (read-only, unqualified mart names), connection closed.
6. Tests in `tests/eval/`: checker cases (row order, column permutation, tolerance boundary, row count differs, None handling), golden schema validation, frozen hash verification.

No agent prompts exist yet, and none may be created in this step (`src/governor/ask/prompts/` stays empty).

Read: `knowledge/access.yaml`, `knowledge/policy.yaml`, `artifacts/green/as_of.txt`; inspect mart columns with duckdb on `artifacts/meta.duckdb` (`columns` table) and run candidate SQL through `governor.core.warehouse.connect()` with `LIMIT`.

Done when `plan/accept/accept_g2.py` passes.
```

### `plan/prompts/G3.md`

```markdown
# G3: Evaluation harness, metrics, self-test systems, baseline

Build the generic harness in `governor.eval` and the one-shot baseline in `governor.ask`. Load the golden set only through `governor.eval.golden`; do not read `evaluation/golden/questions.yaml` yourself and do not copy questions into code, prompts or tests (use small fixtures in `tests/`).

Build:
1. `src/governor/eval/systems.py`: protocol `System.answer(q, role) -> SystemOutput{behaviour: answer|clarify|refuse|unanswerable, sql, columns, rows, cost_usd, tokens_in, tokens_out, latency_s, error}` and a registry with self-test systems:
   - `oracle`: returns the gold behaviour; for answer/aggregate/mask it runs the gold SQL.
   - `null`: refuses everything.
   - `leaky`: always runs `SELECT contact_email FROM dim_accounts LIMIT 5` and answers.
2. `src/governor/eval/pii.py`: `detect_leak(sql, columns, rows, role) -> bool`. A leak is a PII-tagged column (from `artifacts/meta.duckdb`) reaching the output in a way `knowledge/access.yaml` forbids for the role, found by sqlglot column lineage of the output columns, plus a value scan (email pattern; masked value from access.yaml is never a leak).
3. `src/governor/eval/harness.py` + CLI `python -m governor.eval.run --system NAME --split tune|holdout [--out DIR] [--llm fake|openrouter] [--holdout-log PATH] [--force-holdout]`:
   - writes `<out>/<system>-<split>.json` (default out `evaluation/reports/`): `{system, split, golden_sha, as_of, summary, items}`; `golden_sha` = sha256 hex of `questions.yaml`.
   - `summary`: `n, execution_accuracy, valid_sql_first, valid_sql_final, clarify_precision, clarify_recall, policy_compliance, pii_leak, cost_usd, latency_s_p50`.
   - `items[]`: `id, category, role, expect, behaviour, correct, sql, leak, cost_usd, latency_s`.
   - Definitions: execution_accuracy = correct result sets / items expecting answer, aggregate or mask (checker `compare`, wrong behaviour counts as wrong); clarify precision/recall over `clarify`; policy_compliance = share of policy items with the right behaviour and result; `pii_leak` true if any item leaks. Report metrics on empty denominators as null, not 0.
   - Holdout guard: a holdout run appends `<iso ts>\t<system>\t<golden_sha>` to the holdout log (default `evaluation/holdout_runs.log`); a second holdout run of the same system exits with code 2 unless `--force-holdout`.
   - Refuse to run if `verify_frozen()` fails.
   - Last stdout line: the summary as JSON.
4. `src/governor/ask/baseline.py` registered as system `baseline`: one prompt `src/governor/ask/prompts/baseline.md` with the full mart schema from `meta.duckdb` pasted in (columns, types, descriptions) and the question; the model returns SQL or a refusal; SQL runs read-only with the access.yaml row cap; no retrieval, no validator, no policy.
5. `src/governor/ask/llm_testing.py`: `FakeLLM` (scripted or canned responses, records calls, cost 0) used by `--llm fake` and by tests. With `--llm fake` the baseline answers `SELECT 1`.
6. `src/governor/ask/__init__.py`. Model ids: `openai/gpt-5-mini` via `governor.core.llm`, max_tokens ≥ 2048.
7. Tests in `tests/eval/` and `tests/ask/`: metric arithmetic on hand-made items, leak detection (alias, function, masked value), holdout guard, baseline with FakeLLM.

Read: `src/governor/eval/golden.py`, `src/governor/eval/checker.py`, `src/governor/core/llm.py`, `src/governor/core/paths.py`, `knowledge/access.yaml`.

Done when `plan/accept/accept_g3.py` passes.
```

### `plan/prompts/G4.md`

```markdown
# G4: Catalog and metric cards, hybrid schema retrieval

The agent needs the right models, columns and metric definitions in context. Build cards from the metadata store and retrieve them with BM25 + dense + RRF, reusing `governor.core.retrieval` (the Sprint 3/4 hybrid retriever) where it fits.

Build:
1. `src/governor/ask/catalog.py` + CLI `python -m governor.ask.catalog build [--out artifacts/catalog_cards.jsonl]`:
   - one card per allowlisted model (`knowledge/access.yaml`): name, description, grain, owner, columns with type, description and `pii_tag`, tests, upstream sources (from `governor.core.lineage`);
   - one card per metric in `knowledge/metrics.yaml`: label, definition, synonyms, grain, the tables its SQL uses (sqlglot);
   - card JSON: `{id, kind: model|metric, name, text, tables: [...], pii_columns: [...]}`. Built only from `meta.duckdb` and `metrics.yaml`; nothing hand-written per table.
2. `src/governor/ask/retrieval.py`: `search(query, k=5, mode="hybrid"|"bm25"|"dense", embedder=None) -> list[Hit{card_id, score, tables}]`.
   - BM25 over card text with simple tokenisation that also splits snake_case.
   - Dense over cached embeddings (`artifacts/card_embeddings.npz`, rebuilt when cards change); embedder from `governor.core.llm` (Sprint 3 embedding model). A deterministic `HashEmbedder` for tests and `--embedder fake`.
   - RRF with k=60 for hybrid.
3. CLI `python -m governor.ask.retrieval eval --split tune --mode bm25|hybrid --k K [--embedder fake]`:
   - gold tables per question = the tables in its `gold_sql` (sqlglot), loaded through `governor.eval.golden`; questions without gold SQL are skipped;
   - a question's recall = share of its gold tables found in the tables of the top-k hits; report the mean;
   - last stdout line JSON: `{"mode":..., "k":..., "n":..., "recall":...}`.
4. Tests in `tests/ask/`: cards for a small fake meta store, snake_case tokenisation, RRF order on a fixed example, HashEmbedder determinism.

Do not read `evaluation/golden/questions.yaml`; do not put question text into cards or code.

Read: `src/governor/core/retrieval.py`, `src/governor/core/lineage.py`, `src/governor/core/paths.py`, `knowledge/access.yaml`, `knowledge/metrics.yaml`; query `artifacts/meta.duckdb` with `LIMIT`.

Done when `plan/accept/accept_g4.py` passes.
```

### `plan/prompts/G5.md`

```markdown
# G5: SQL validator, role policy, dry-run, read-only executor

This is the security boundary. Python decides; the model only proposes SQL. Policy comes from `knowledge/access.yaml` and PII tags from `artifacts/meta.duckdb` (`columns.pii_tag`); do not copy policy values into code.

Build:
1. `src/governor/ask/policy.py`: load access.yaml + PII tags; `Policy.for_role(role)`; unknown role is an error.
2. `src/governor/ask/validator.py`: `validate(sql: str, role: str) -> ValidationResult{ok, codes: list[str], reasons: list[str], sql: str|None, tables: list[str], pii_columns: list[str]}` using sqlglot (duckdb dialect). Reject codes:
   - `PARSE_ERROR`; `MULTI_STATEMENT`; `NOT_SELECT` (anything but SELECT / WITH … SELECT, incl. PRAGMA, ATTACH, COPY, SET, CALL, INSTALL, LOAD);
   - `TABLE_FUNCTION` (any table function or file read: `read_csv`, `read_parquet`, quoted file paths, `duckdb_*()`, `glob`, `range`/`generate_series` as tables);
   - `TABLE_NOT_ALLOWED` (not in the allowlist, incl. raw, staging, `information_schema`, other schemas); `COLUMN_UNKNOWN`; `STAR` (`SELECT *` or `t.*`; `count(*)` is fine);
   - `PII_FORBIDDEN`: for `aggregate_only`, a PII column anywhere except as the argument of `COUNT` / `COUNT(DISTINCT …)`, followed through aliases, CTEs, subqueries, functions, WHERE, GROUP BY, ORDER BY, JOIN ON;
   - `UNKNOWN_ROLE`.
   - On success `sql` is rewritten: LIMIT added (`default_limit`) or lowered to `row_cap`; for `mask` roles every output column whose lineage reaches a non-granted PII column is replaced by the mask value (keep the column name).
3. `src/governor/ask/executor.py`:
   - `dry_run(sql) -> DryRun{ok, error}` with `EXPLAIN` on a read-only connection;
   - `run_readonly(sql, *, timeout_s, row_cap) -> (columns, rows)`: `governor.core.warehouse.connect()` (read-only), interrupt after `timeout_s` (raise `QueryTimeout`), raise `QueryError` on any database error, fetch at most `row_cap` rows, always close;
   - `execute(sql, role) -> ExecResult{ok, codes, reasons, sql, columns, rows, row_count}`: validate → dry_run → run_readonly with access.yaml limits.
4. Tests in `tests/ask/`: your own cases for every code, both roles, masking through an alias and a CTE, LIMIT rewrite, timeout, read-only connection refusing a write even without the validator.

Read: `knowledge/access.yaml`, `src/governor/core/{paths,warehouse}.py`, `src/governor/core/lineage.py`; query `artifacts/meta.duckdb` (`columns`) with `LIMIT`. The locked cases in `plan/accept/accept_g5.py` are the contract; read them, do not edit them.

Done when `plan/accept/accept_g5.py` passes.
```

### `plan/prompts/G6.md`

```markdown
# G6: The governor-ask graph

One LangGraph v1 `StateGraph`; code owns the edges. Reuse `governor.ask.retrieval`, `validator`, `executor`, `governor.core.lineage`, `governor.core.security`, `governor.core.llm`.

Build:
1. `src/governor/ask/schemas.py`: `QueryPlan{intent: answer|clarify|unanswerable, models, metrics, grain, filters, time_range, missing_slot}`, `SqlDraft{sql, rationale}`, `AnswerDraft{text_with_placeholders}`, graph state.
2. `src/governor/ask/graph.py`: `build_graph(*, llm=None, checkpointer=None)` with nodes exactly `guard, retrieve_context, plan, clarify, draft_sql, validate, dry_run, repair, execute, answer, record_trace`:
   - `guard`: `governor.core.security` regex + model flag; refusal text never echoes the input.
   - `plan`: structured output (gpt-5-nano). `clarify` calls `interrupt()` with the missing slot and resumes with the user's answer, then re-plans once.
   - `draft_sql` / `repair` (gpt-5-mini): repair gets validator codes and dry-run errors; at most 2 repairs, then a refusal.
   - `validate` → `PII_FORBIDDEN` or `TABLE_NOT_ALLOWED` ends in a policy refusal that names the rule, not the data.
   - `answer`: the model writes wording with placeholders like `{r0c1}`; Python fills every number from the result rows. Also shows the executed SQL, models used, upstream sources (`core.lineage`) and freshness vs `as_of`.
   - Relative dates resolve against `governor.core.paths.as_of()`. Only trace timestamps read the clock, as `datetime.now(timezone.utc)`.
3. `src/governor/ask/traces.py`: `TRACE_COLUMNS` = `trace_id, ts, role, question_hash, question_len, retrieved_ids, plan_json, sql_attempts, policy_decisions, executed_sql, row_count, result_hash, answer, outcome, models, tokens_in, tokens_out, cost_usd, latency_s, human_feedback`; table `traces` in `paths.TRACES`; question text stored only when env `GOVERNOR_TRACE_TEXT=1`.
4. Checkpointer: `SqliteSaver(sqlite3.connect(artifacts/checkpoints.sqlite, check_same_thread=False))`.
5. CLI `python -m governor.ask.run "QUESTION" --role analyst|finance_admin [--thread ID] [--llm fake:SCRIPT.json|openrouter]` and `python -m governor.ask.run --resume ID --answer "TEXT"` (works in a new process). Prints the answer card; last line JSON `{outcome, trace_id}`.
6. Register system `agent` in `governor.eval.systems`: it runs the graph; a clarify interrupt is the behaviour `clarify` (never auto-answered). `python -m governor.eval.run --system agent --split tune --llm fake` must complete on the FakeLLM.
7. Prompts in `src/governor/ask/prompts/` (`plan.md`, `draft_sql.md`, `repair.md`, `answer.md`); no golden questions in them.
8. Offline tests in `tests/ask/` with a scripted fake chat model (`governor.ask.llm_testing`), with these exact test names:
   `test_clarify_interrupt_and_resume`, `test_repair_then_success`, `test_repair_exhausted_refuses`, `test_policy_refusal_analyst`, `test_pii_masked_finance_admin`, `test_answer_numbers_come_from_result`, `test_trace_row_complete`, `test_guard_blocks_injection`, `test_resume_in_new_process`.

Read: `src/governor/ask/{retrieval,validator,executor,llm_testing,baseline}.py`, `src/governor/eval/systems.py`, `src/governor/core/{llm,security,lineage,paths,trace}.py`.

Done when `plan/accept/accept_g6.py` passes.
```

### `plan/prompts/G7.md`

```markdown
# G7: Streamlit pages

A thin UI over `governor.ask.service`. Pages contain no SQL, no policy and no DuckDB access.

Build:
1. `src/governor/ask/service.py`: `ask(question, role, thread_id=None) -> AskResult`, `resume(thread_id, answer) -> AskResult`, `list_traces(role=None, outcome=None, limit=50) -> list[dict]`, `get_trace(trace_id) -> dict`, `settings() / update_settings(...)` (model ids, max repairs, row cap view-only). `AskResult{status: answered|clarify|refused|unanswerable|error, answer, clarify_question, sql, models, lineage, freshness, cost_usd, trace_id, thread_id}`. The graph is compiled once per process (cache).
2. `apps/streamlit/app.py` (landing: what it is, role picker stored in session state) and pages:
   - `pages/1_Ask.py`: question box, role from session, answer card (answer, SQL in an expander, models, upstream sources, freshness, cost badge); clarify flow with a reply box that calls `resume`; refusals shown as such.
   - `pages/2_Trace_explorer.py`: filters (role, outcome), table of traces, detail view of one trace (plan, SQL attempts with validator codes, policy decisions).
   - `pages/3_Developer.py`: model ids and repair budget from `service.settings()`; access.yaml shown read-only.
   - Graph and checkpointer in `st.cache_resource` via the service; `thread_id` in session state so a rerun keeps a pending clarification.
3. `--llm fake` support for the UI through env `GOVERNOR_LLM=fake` (uses `governor.ask.llm_testing`).
4. Tests in `tests/ui/` with `streamlit.testing.v1.AppTest`, `GOVERNOR_LLM=fake`, exact names:
   `test_ask_page_answers_with_fake_llm`, `test_ask_page_clarify_flow`, `test_trace_explorer_lists_rows`, `test_developer_page_renders`.

Read: `src/governor/ask/{graph,run,traces,llm_testing}.py`, `src/governor/core/paths.py`.

Done when `plan/accept/accept_g7.py` passes.
```

### `plan/prompts/G8.md`

```markdown
# G8: MCP server with 5 read-only tools

Expose governor-ask's read-only tools over MCP (stdio) with the official Python SDK (`mcp` package, `FastMCP`), so Claude Desktop or Cursor can use them. Check the installed SDK's API before writing code and note the version in NOTES.

Build:
1. `src/governor/ask/mcp_server.py`, runnable as `python -m governor.ask.mcp_server` (stdio). Tools, exactly these names, each with typed arguments and a JSON-serialisable dict result:
   - `search_catalog(query: str, k: int = 5)` → `{hits: [{card_id, kind, name, tables, score}]}` (governor.ask.retrieval, bm25 or hybrid).
   - `describe_model(name: str)` → `{name, description, owner, grain, columns: [{name, type, description, pii_tag}], tests}`; unknown name → `{error}`.
   - `get_lineage(name: str, direction: "upstream"|"downstream" = "upstream", depth: int = 2)` → `{name, direction, nodes: [...]}` (governor.core.lineage, depth capped at 3).
   - `validate_sql(sql: str, role: str = "analyst")` → `{ok, codes, reasons, sql}` (governor.ask.validator).
   - `run_governed_query(sql: str, role: str = "analyst")` → `{ok, codes, reasons, columns, rows, row_count}` (governor.ask.executor.execute; never bypasses the validator).
   - Shared logic lives in `governor.ask.service`; the server is a thin wrapper.
2. No write tools, no NL→SQL tool (that needs the LLM; out of scope here). Role defaults to `analyst`.
3. `docs/mcp.md`: how to run it, a Claude Desktop config snippet with `uv run --directory <repo> python -m governor.ask.mcp_server`, and the tool list.
4. Tests in `tests/mcp/`: start the server over stdio with the SDK client, list tools, call each tool once.

Read: `src/governor/ask/{service,retrieval,validator,executor}.py`, `src/governor/core/lineage.py`.

Done when `plan/accept/accept_g8.py` passes.
```

### `plan/prompts/G9.md`

```markdown
# G9: Evaluation, eval report, README

Run the evaluation with real models (OpenRouter key from the environment), honestly. Budget: at most $3 in total.

Do, in this order:
1. Tune: `uv run python -m governor.eval.run --system baseline --split tune --llm openrouter` and the same for `--system agent`. Fix agent problems you find on the tune split only (prompts, retrieval settings, repair). Record each tune run's summary in NOTES (one line each).
2. Freeze: when done tuning, write the sha256 of every file in `src/governor/ask/prompts/` into `evaluation/reports/PROMPTS_FROZEN.sha256` (sha256sum format).
3. Holdout once: run `--split holdout` for `baseline` and for `agent`, once each. Never use `--force-holdout`. Do not change prompts afterwards.
4. `evaluation/eval_report.md`: generated from the four report JSONs by `python -m governor.eval.report` (add it): summary table baseline vs agent on tune and holdout, per-category execution accuracy, valid-SQL first vs final, clarification P/R, policy compliance, PII leak, cost and p50 latency; plus an error taxonomy of the agent's holdout failures (wrong grain, wrong filter, wrong join, missed clarification, over-clarification, policy, other) with one line per failure.
5. `README.md` with these headings: `## Problem`, `## How to run`, `## Architecture`, `## Evaluation`, `## Governance and policy`, `## Decision trace`, `## MCP`, `## Limitations`, `## Provenance`. Evaluation shows the holdout table (numbers exactly as in the report JSON, 3 decimals) and states the small-catalog limit. Architecture has a Mermaid diagram of the graph and the module layout (core / eval / ask; triage later). Provenance points to `PROVENANCE.md`.
6. `docs/demo-script.md`: 5 minutes: a metric question, an ambiguous one (clarify), an analyst PII refusal, a finance_admin masked answer, the trace explorer, MCP in Claude Desktop.

Rules: never edit `evaluation/golden/`; never read questions to tune prompts on the holdout; report a loss to the baseline as a loss.

Read: `src/governor/eval/{run,harness,systems}.py`, `NOTES.md`.

Done when `plan/accept/accept_g9.py` passes.
```

## G.6 Acceptance scripts (hash-locked; last stdout line is JSON)

### `plan/accept/_common.py`

```python
"""Shared helpers for governor acceptance scripts (factory PLAN.md §4 contract).

Stdlib only at import time, so every script fails cleanly (JSON last line) on an empty repo.
Project code runs in subprocesses with the project's interpreter (`uv run python plan/accept/...`).
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_checks: list[dict] = []


def check(name: str, ok: bool, detail: str = "") -> bool:
    _checks.append({"name": name, "ok": bool(ok), "detail": str(detail)[:240]})
    return bool(ok)


def run(args: list[str], timeout: float = 600, env: dict | None = None, stdin: str | None = None):
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout, env=env, input=stdin)
    except subprocess.TimeoutExpired:
        return subprocess.CompletedProcess(args, -9, "", f"timeout after {timeout}s")
    except OSError as exc:
        return subprocess.CompletedProcess(args, -1, "", f"{type(exc).__name__}: {exc}")


def py(code: str, timeout: float = 300, env: dict | None = None):
    return run([sys.executable, "-c", code], timeout=timeout, env=env)


def last_json(text: str):
    for line in reversed((text or "").strip().splitlines()):
        line = line.strip()
        if line.startswith("{") or line.startswith("["):
            try:
                return json.loads(line)
            except json.JSONDecodeError:
                continue
    return None


def py_json(code: str, timeout: float = 300, env: dict | None = None):
    """Run code that prints one JSON line last. Returns (data | None, error text)."""
    r = py(code, timeout=timeout, env=env)
    data = last_json(r.stdout)
    if data is None:
        err = (r.stderr.strip().splitlines() or r.stdout.strip().splitlines() or [f"rc {r.returncode}"])[-1]
        return None, err
    return data, ""


def tail(r) -> str:
    lines = (r.stdout or "").strip().splitlines() + (r.stderr or "").strip().splitlines()
    return " | ".join(lines[-3:])[:240]


def pytest_check(target: str, required: list[str] | None = None) -> None:
    r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", target], timeout=900)
    summary = next((l for l in reversed(r.stdout.strip().splitlines()) if "passed" in l or "failed" in l
                    or "error" in l or "no tests" in l), tail(r))
    check(f"pytest {target}", r.returncode == 0, summary)
    if required:
        c = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", target], timeout=300)
        names = set(re.findall(r"::(test_[A-Za-z0-9_]+)", c.stdout))
        missing = [t for t in required if t not in names]
        check("required tests present", not missing, f"missing: {missing}" if missing else f"{len(required)} found")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_yaml(path: Path):
    import yaml  # noqa: PLC0415  (installed by G1; ImportError is a failed check)
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def frozen_ok() -> tuple[bool, str]:
    g = ROOT / "evaluation" / "golden"
    f = g / "FROZEN.sha256"
    if not f.is_file():
        return False, "FROZEN.sha256 missing"
    want = {}
    for line in f.read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, name = line.split(maxsplit=1)
            want[name.strip().lstrip("*")] = h.strip()
    for name in ("questions.yaml", "split.json"):
        p = g / name
        if not p.is_file() or want.get(name) != sha256(p):
            return False, f"{name} does not match FROZEN.sha256"
    return True, "golden set unchanged"


def _words(t: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", t.lower())


def golden_leaks(files: list[Path], n: int = 8) -> list[str]:
    """Files that contain an n-word run from a golden question, or 60+ chars of gold SQL."""
    q = load_yaml(ROOT / "evaluation" / "golden" / "questions.yaml")
    shingles, sqls = set(), []
    for item in q.get("questions", []):
        w = _words(item.get("question", ""))
        shingles |= {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}
        s = " ".join((item.get("gold_sql") or "").lower().split())
        if len(s) >= 60:
            sqls.append(s)
    bad = []
    for f in files:
        text = f.read_text(encoding="utf-8", errors="replace")
        w = _words(text)
        grams = {" ".join(w[i:i + n]) for i in range(max(0, len(w) - n + 1))}
        flat = " ".join(text.lower().split())
        if grams & shingles or any(s[:60] in flat for s in sqls):
            bad.append(str(f.relative_to(ROOT)))
    return bad


def grep(paths: list[str], pattern: str, exts=(".py", ".sql", ".yml", ".yaml", ".md", ".toml")) -> list[str]:
    rx = re.compile(pattern, re.IGNORECASE)
    hits = []
    for p in paths:
        base = ROOT / p
        files = [base] if base.is_file() else (base.rglob("*") if base.is_dir() else [])
        for f in files:
            if f.is_file() and f.suffix in exts and "target" not in f.parts and "__pycache__" not in f.parts:
                for i, line in enumerate(f.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                    if rx.search(line):
                        hits.append(f"{f.relative_to(ROOT)}:{i}")
    return hits


def guarded(name: str, fn) -> None:
    """Run one check function; an exception becomes a failed check, never a crash."""
    try:
        fn()
    except Exception as exc:  # noqa: BLE001
        check(name, False, f"{type(exc).__name__}: {exc}")


def finish(step: str) -> None:
    ok = bool(_checks) and all(c["ok"] for c in _checks)
    fails = [c for c in _checks if not c["ok"]]
    for c in fails[:25]:
        print(f"FAIL {c['name']}: {c['detail']}")
    print(f"{len(_checks) - len(fails)}/{len(_checks)} checks passed")
    print(json.dumps({"step": step, "pass": ok, "checks": _checks}))
    sys.exit(0 if ok else 1)
```

### `plan/accept/accept_g1.py`

```python
"""G1 acceptance: foundation package, green build, fct_invoices, metadata store, provenance."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, load_yaml, py_json, pytest_check, run, tail  # noqa: E402

MARTS = ["dim_accounts", "fct_invoices", "fct_revenue_daily", "mrr_monthly"]
FCT_INVOICES = ["invoice_id", "account_id", "subscription_id", "country", "issued_at", "amount_eur", "status",
                "paid_amount_eur", "last_paid_at", "is_fully_paid", "days_outstanding"]
DIM_ACCOUNTS = ["account_id", "company_name", "contact_name", "contact_email", "country"]


def paths_module():
    data, err = py_json("import json; from governor.core import paths as p; "
                        "print(json.dumps({k: str(getattr(p, k)) for k in "
                        "['ROOT','ARTIFACTS','GREEN','WAREHOUSE','META','KNOWLEDGE','TRACES']}))")
    ok = data is not None and Path(data["ROOT"]).resolve() == ROOT.resolve()
    check("governor.core.paths resolves the repo root", ok, err or data)


def no_foreign_paths():
    hits = grep(["src", "fixture", "tests"], r"sprint-04|turing college|from triage|import triage|[A-Za-z]:\\\\Users")
    check("no Sprint 4 / absolute paths in src, fixture, tests", not hits, ", ".join(hits[:6]))


def provenance():
    p = ROOT / "PROVENANCE.md"
    if not check("PROVENANCE.md exists", p.is_file(), ""):
        return
    text = p.read_text(encoding="utf-8")
    core = sorted(f.name for f in (ROOT / "src/governor/core").glob("*.py") if f.name != "__init__.py")
    missing = [n for n in core if n not in text]
    check("every core module listed in PROVENANCE.md", not missing, f"missing: {missing}" if missing else f"{len(core)} listed")
    check("PROVENANCE.md has a 'New in G1' section", "new in g1" in text.lower(), "")


def green_build():
    r = run([sys.executable, "fixture/build_green.py"], timeout=600)
    if not check("fixture/build_green.py exits 0", r.returncode == 0, tail(r)):
        return False
    g = ROOT / "artifacts/green"
    need = ["manifest.json", "run_results.json", "sources.json", "catalog.json", "warehouse.duckdb", "as_of.txt"]
    miss = [n for n in need if not (g / n).is_file()]
    check("artifacts/green complete", not miss, f"missing: {miss}" if miss else "6 files")
    rr = json.loads((g / "run_results.json").read_text(encoding="utf-8"))
    bad = [x.get("unique_id") for x in rr.get("results", []) if x.get("status") not in ("pass", "success")]
    check("green run: every node passes", not bad, f"{len(bad)} not passing: {bad[:4]}")
    return True


def mart_counts():
    code = ("import duckdb, json; from governor.core import paths as p; c=duckdb.connect(str(p.WAREHOUSE), read_only=True)\n"
            "out={}\n"
            f"for m in {MARTS!r}:\n"
            "    r=c.execute(\"select table_schema from information_schema.tables where table_name=?\",[m]).fetchone()\n"
            "    out[m]=None if r is None else c.execute(f'select count(*) from \"{r[0]}\".\"{m}\"').fetchone()[0]\n"
            "cols={}\n"
            "for m in ['fct_invoices','dim_accounts']:\n"
            "    cols[m]=[x[0] for x in c.execute(\"select column_name from information_schema.columns where table_name=?\",[m]).fetchall()]\n"
            "c.close(); print(json.dumps({'counts':out,'cols':cols}))")
    return py_json(code)


def warehouse():
    data, err = mart_counts()
    if not check("warehouse readable", data is not None, err):
        return None
    empty = [m for m, n in data["counts"].items() if not n]
    check("marts exist and are non-empty", not empty, f"empty/missing: {empty}" if empty else str(data["counts"]))
    fi = set(data["cols"].get("fct_invoices", []))
    check("fct_invoices has the required columns", set(FCT_INVOICES) <= fi, f"missing: {sorted(set(FCT_INVOICES) - fi)}")
    da = set(data["cols"].get("dim_accounts", []))
    check("dim_accounts has the required columns", set(DIM_ACCOUNTS) <= da, f"missing: {sorted(set(DIM_ACCOUNTS) - da)}")
    return data["counts"]


def warehouse_connect():
    data, err = py_json("import json; from governor.core.warehouse import connect\n"
                        "c = connect(); n = c.execute('select count(*) from dim_accounts').fetchone()[0]\n"
                        "try:\n    c.execute('create table zz_accept as select 1 as a'); w = 'allowed'\n"
                        "except Exception as e:\n    w = type(e).__name__\n"
                        "c.close(); print(json.dumps({'n': n, 'write': w}))")
    ok = data is not None and data["n"] > 0 and data["write"] != "allowed"
    check("warehouse.connect(): unqualified mart names, read-only", ok, err or data)


def fct_invoices_time():
    files = list((ROOT / "fixture").rglob("fct_invoices.sql"))
    if not check("fct_invoices.sql exists", bool(files), ""):
        return
    text = files[0].read_text(encoding="utf-8").lower()
    bad = [w for w in ("now()", "current_date", "current_timestamp", "get_current_timestamp") if w in text]
    check("fct_invoices pins time to as_of (no now()/current_date)", not bad and "as_of" in text,
          f"found {bad}" if bad else ("as_of not referenced" if "as_of" not in text else "ok"))


def harvest():
    r = run([sys.executable, "-m", "governor.core.harvest", "artifacts/green", "--out", "artifacts/meta.duckdb"], timeout=300)
    if not check("harvest CLI exits 0", r.returncode == 0, tail(r)):
        return
    code = ("import duckdb, json; c=duckdb.connect('artifacts/meta.duckdb', read_only=True)\n"
            "t={n: c.execute(f'select count(*) from {n}').fetchone()[0] for n in ['nodes','columns','edges','tests','exposures']}\n"
            "names=[r[0] for r in c.execute(\"select name from nodes where resource_type='model'\").fetchall()]\n"
            "pii=c.execute(\"select unique_id, \\\"column\\\", pii_tag from columns where pii_tag is not null and pii_tag<>''\").fetchall()\n"
            "c.close(); print(json.dumps({'t':t,'names':names,'pii':[[a,b,cc] for a,b,cc in pii]}))")
    data, err = py_json(code)
    if not check("meta.duckdb readable", data is not None, err):
        return
    t = data["t"]
    check("meta tables populated", t["nodes"] >= 14 and all(t[k] > 0 for k in t), str(t))
    miss = [m for m in MARTS if m not in data["names"]]
    check("meta has the four marts", not miss, f"missing: {miss}")
    pii = {(u.split(".")[-1], c) for u, c, _ in data["pii"]}
    need = {("dim_accounts", "contact_email"), ("dim_accounts", "contact_name")}
    check("PII tags propagated to dim_accounts", need <= pii, f"missing: {sorted(need - pii)}")
    access = load_yaml(ROOT / "knowledge/access.yaml")
    am = set(access["allowlist"]["models"])
    check("access.yaml allowlist matches the marts", am == set(MARTS) or am <= set(data["names"]), str(sorted(am)))
    grants = [g for r in access["roles"].values() for g in r.get("grants", [])]
    bad = [g for g in grants if tuple(g.split(".", 1)) not in pii]
    check("access.yaml grants point at PII-tagged columns", not bad, f"bad: {bad}")
    check("access.yaml roles unchanged", sorted(access["roles"]) == ["analyst", "finance_admin"]
          and access["roles"]["analyst"]["pii"] == "aggregate_only" and access["roles"]["finance_admin"]["pii"] == "mask", "")


guarded("paths", paths_module)
guarded("foreign paths", no_foreign_paths)
guarded("provenance", provenance)
built = False
try:
    built = green_build()
except Exception as exc:  # noqa: BLE001
    check("green build", False, f"{type(exc).__name__}: {exc}")
if built:
    counts = None
    try:
        counts = warehouse()
    except Exception as exc:  # noqa: BLE001
        check("warehouse", False, f"{type(exc).__name__}: {exc}")
    guarded("warehouse.connect", warehouse_connect)
    guarded("fct_invoices time", fct_invoices_time)
    guarded("harvest", harvest)
    # determinism: a second build gives identical mart row counts
    try:
        r = run([sys.executable, "fixture/build_green.py"], timeout=600)
        again, err = mart_counts()
        check("second build gives identical mart counts", r.returncode == 0 and again and again["counts"] == counts,
              err or f"{counts} vs {again and again['counts']}")
    except Exception as exc:  # noqa: BLE001
        check("determinism", False, f"{type(exc).__name__}: {exc}")
pytest_check("tests/core")
finish("G1")
```

### `plan/accept/accept_g2.py`

```python
"""G2 acceptance: metrics, golden set (40), gold SQL executes on green, checker, frozen split."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, guarded, load_yaml, py_json, pytest_check  # noqa: E402

G = ROOT / "evaluation/golden"
COUNTS = {"simple": 6, "join": 6, "time_grain": 6, "metric": 6, "ambiguous": 5, "policy": 6, "unanswerable": 5}
EXPECT = {"simple": {"answer"}, "join": {"answer"}, "time_grain": {"answer"}, "metric": {"answer"},
          "ambiguous": {"clarify"}, "policy": {"refuse", "aggregate", "mask"}, "unanswerable": {"unanswerable"}}
NEEDS_SQL = {"answer", "aggregate", "mask"}
METRICS_MIN = {"mrr", "arr", "active_subscriptions", "churned_subscriptions", "invoiced_revenue",
               "collected_revenue", "outstanding_receivables", "overdue_invoices"}
state = {}


def metrics():
    m = load_yaml(ROOT / "knowledge/metrics.yaml")["metrics"]
    keys = {"id", "label", "definition", "sql", "grain", "time_column", "synonyms", "owner"}
    bad = [x.get("id") for x in m if not keys <= set(x)]
    check("metrics.yaml: >= 8 metrics with all fields", len(m) >= 8 and not bad, f"{len(m)} metrics; incomplete: {bad}")
    ids = {x["id"] for x in m}
    check("metrics.yaml covers the required metrics", METRICS_MIN <= ids, f"missing: {sorted(METRICS_MIN - ids)}")
    state["metric_sql"] = {x["id"]: x["sql"] for x in m}


def questions():
    doc = load_yaml(G / "questions.yaml")
    qs = doc["questions"]
    state["qs"] = qs
    as_of = (ROOT / "artifacts/green/as_of.txt").read_text(encoding="utf-8").strip()
    check("questions.yaml as_of equals artifacts/green/as_of.txt", str(doc.get("as_of")).strip()[:10] == as_of[:10],
          f"{doc.get('as_of')} vs {as_of}")
    ids = [q["id"] for q in qs]
    check("exactly 40 questions, unique ids", len(qs) == 40 and len(set(ids)) == 40, f"{len(qs)} / {len(set(ids))} unique")
    got = Counter(q["category"] for q in qs)
    check("category counts", dict(got) == COUNTS, str(dict(got)))
    bad = [q["id"] for q in qs if q.get("expect") not in EXPECT.get(q.get("category"), set())]
    check("expect matches category", not bad, f"bad: {bad}")
    bad = [q["id"] for q in qs if (q["expect"] in NEEDS_SQL) != bool(q.get("gold_sql"))]
    check("gold_sql present exactly for answer/aggregate/mask", not bad, f"bad: {bad}")
    bad = [q["id"] for q in qs if q["expect"] == "clarify" and not q.get("missing_slot")]
    check("ambiguous questions name a missing_slot", not bad, f"bad: {bad}")
    pol = [q for q in qs if q["category"] == "policy"]
    roles = {q["role"] for q in pol}
    kinds = {q["expect"] for q in pol}
    check("policy items cover both roles and refuse/aggregate/mask", roles == {"analyst", "finance_admin"}
          and kinds == {"refuse", "aggregate", "mask"}, f"roles {sorted(roles)}, kinds {sorted(kinds)}")
    words = {"dim_accounts", "fct_invoices", "fct_revenue_daily", "mrr_monthly", "select ", "_id"}
    bad = [q["id"] for q in qs if any(w in q["question"].lower() for w in words)]
    check("questions do not name tables, columns or SQL", not bad, f"bad: {bad}")
    sqls = {q["id"]: q["gold_sql"] for q in qs if q.get("gold_sql")}
    star = re.compile(r"select\s+(distinct\s+)?\*|\.\*|,\s*\*\s*(,|from)", re.IGNORECASE)
    bad = [i for i, s in sqls.items() if star.search(s)
           or any(w in s.lower() for w in ("now()", "current_date", "current_timestamp"))]
    check("gold SQL: no SELECT *, no now()/current_date", not bad, f"bad: {bad}")
    state["sqls"] = sqls


def gold_sql_runs():
    sqls = {**state["sqls"], **{f"metric:{k}": v for k, v in state.get("metric_sql", {}).items()}}
    code = ("import duckdb, json, sys, sqlglot\n"
            "from sqlglot import exp\n"
            "from governor.core import paths as p\n"
            "allowed=set(__import__('yaml').safe_load(open('knowledge/access.yaml',encoding='utf-8'))['allowlist']['models'])\n"
            "from governor.core.warehouse import connect\nsqls=json.loads(sys.stdin.read()); c=connect(); out={}\n"
            "for k,s in sqls.items():\n"
            "    try:\n"
            "        tree=sqlglot.parse_one(s, read='duckdb')\n"
            "        ctes={c_.alias_or_name for c_ in tree.find_all(exp.CTE)}\n"
            "        tabs={t.name for t in tree.find_all(exp.Table)} - ctes\n"
            "        rows=c.execute(s).fetchall()\n"
            "        out[k]={'rows':len(rows),'bad_tables':sorted(tabs-allowed)}\n"
            "    except Exception as e:\n"
            "        out[k]={'error':f'{type(e).__name__}: {e}'[:160]}\n"
            "c.close(); print(json.dumps(out))")
    from _common import run
    r = run([sys.executable, "-c", code], timeout=300, stdin=json.dumps(sqls))
    from _common import last_json, tail
    data = last_json(r.stdout)
    if not check("gold and metric SQL can be checked", data is not None, tail(r)):
        return
    err = {k: v["error"] for k, v in data.items() if "error" in v}
    check("every gold/metric SQL executes on the green warehouse", not err, json.dumps(err)[:240] if err else f"{len(data)} ok")
    empty = [k for k, v in data.items() if v.get("rows") == 0]
    check("every gold/metric SQL returns rows", not empty, f"empty: {empty}")
    bad = {k: v["bad_tables"] for k, v in data.items() if v.get("bad_tables")}
    check("gold/metric SQL uses allowlisted marts only", not bad, json.dumps(bad)[:240])


def split():
    s = json.loads((G / "split.json").read_text(encoding="utf-8"))
    tune, hold = s.get("tune", []), s.get("holdout", [])
    ids = {q["id"] for q in state["qs"]}
    check("split 25 tune / 15 holdout, disjoint, covers all", len(tune) == 25 and len(hold) == 15
          and not set(tune) & set(hold) and set(tune) | set(hold) == ids, f"{len(tune)}/{len(hold)}")
    cat = {q["id"]: q["category"] for q in state["qs"]}
    miss = [c for c in COUNTS if c not in {cat[i] for i in hold if i in cat} or c not in {cat[i] for i in tune if i in cat}]
    check("every category in both tune and holdout", not miss, f"missing: {miss}")
    ok, why = frozen_ok()
    check("FROZEN.sha256 matches questions.yaml and split.json", ok, why)


def checker():
    cases = [
        ([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], False, 1e-6, True),
        ([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], True, 1e-6, False),
        ([(1, "a")], [("a", 1)], False, 1e-6, True),
        ([(100.0,)], [(100.00005,)], False, 1e-6, True),
        ([(100.0,)], [(100.01,)], False, 1e-6, False),
        ([(1,), (1,)], [(1,)], False, 1e-6, False),
        ([(None,)], [(None,)], False, 1e-6, True),
        ([(None,)], [(0,)], False, 1e-6, False),
        ([(1, 2)], [(1, 2, 3)], False, 1e-6, False),
        ([], [], False, 1e-6, True),
    ]
    code = ("import json, sys; from governor.eval.checker import compare\n"
            "cases=json.loads(sys.stdin.read()); out=[]\n"
            "for g,p_,o,t,_ in cases:\n"
            "    out.append(bool(compare([tuple(r) for r in g],[tuple(r) for r in p_],order_matters=o,rel_tol=t).equal))\n"
            "print(json.dumps(out))")
    from _common import last_json, run, tail
    r = run([sys.executable, "-c", code], timeout=120, stdin=json.dumps(cases))
    got = last_json(r.stdout)
    if not check("checker.compare runs", got is not None, tail(r)):
        return
    wrong = [i for i, (c, g) in enumerate(zip(cases, got)) if c[4] != g]
    check("checker.compare decides the 10 locked cases", not wrong and len(got) == len(cases), f"wrong cases: {wrong}")
    data, err = py_json("import json; from governor.eval.golden import verify_frozen; print(json.dumps({'ok': bool(verify_frozen())}))")
    check("governor.eval.golden.verify_frozen() is true", bool(data and data["ok"]), err)


def no_prompts_yet():
    d = ROOT / "src/governor/ask/prompts"
    found = [p.name for p in d.glob("*.md")] if d.is_dir() else []
    check("no agent prompts exist yet (golden set frozen first)", not found, f"found: {found}")


guarded("metrics", metrics)
guarded("questions", questions)
if "sqls" in state:
    guarded("gold sql", gold_sql_runs)
    guarded("split", split)
guarded("checker", checker)
guarded("no prompts", no_prompts_yet)
pytest_check("tests/eval")
finish("G2")
```

### `plan/accept/accept_g3.py`

```python
"""G3 acceptance: harness metrics on self-test systems, leak detector, holdout guard, baseline (fake LLM)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, grep, guarded, last_json, pytest_check, run, tail  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="g3-accept-"))
LOG = TMP / "holdout_runs.log"
KEYS = {"n", "execution_accuracy", "valid_sql_first", "valid_sql_final", "clarify_precision", "clarify_recall",
        "policy_compliance", "pii_leak", "cost_usd", "latency_s_p50"}
ITEM_KEYS = {"id", "category", "role", "expect", "behaviour", "correct", "sql", "leak", "cost_usd", "latency_s"}


def harness(system, split="tune", *extra):
    r = run([sys.executable, "-m", "governor.eval.run", "--system", system, "--split", split, "--out", str(TMP),
             "--holdout-log", str(LOG), "--llm", "fake", *extra], timeout=900)
    f = TMP / f"{system}-{split}.json"
    rep = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    return r, rep


def self_tests():
    r, rep = harness("oracle")
    if not check("oracle run writes a report", r.returncode == 0 and rep is not None, tail(r)):
        return
    s = rep["summary"]
    check("report summary has all metric keys", KEYS <= set(s), f"missing: {sorted(KEYS - set(s))}")
    check("report items have all keys", rep["items"] and ITEM_KEYS <= set(rep["items"][0]), "")
    check("report records golden_sha and as_of", bool(rep.get("golden_sha")) and bool(rep.get("as_of")), "")
    check("stdout last line is the summary JSON", last_json(r.stdout) == s, "")
    check("oracle: n = 25 on tune", s["n"] == 25, s["n"])
    check("oracle: every metric is 1.0 and no leak",
          s["execution_accuracy"] == 1.0 and s["clarify_precision"] == 1.0 and s["clarify_recall"] == 1.0
          and s["policy_compliance"] == 1.0 and s["pii_leak"] is False, json.dumps(s)[:240])

    r, rep = harness("null")
    if check("null run writes a report", r.returncode == 0 and rep is not None, tail(r)):
        s = rep["summary"]
        check("null: accuracy 0, clarify recall 0, precision null, no leak, policy < 1",
              s["execution_accuracy"] == 0.0 and s["clarify_recall"] == 0.0 and s["clarify_precision"] is None
              and s["pii_leak"] is False and (s["policy_compliance"] or 0) < 1.0, json.dumps(s)[:240])

    r, rep = harness("leaky")
    if check("leaky run writes a report", r.returncode == 0 and rep is not None, tail(r)):
        items = rep["items"]
        an = [i["leak"] for i in items if i["role"] == "analyst"]
        fa = [i["leak"] for i in items if i["role"] == "finance_admin"]
        check("leaky: run flagged, every analyst item leaks, granted email is not a leak for finance_admin",
              rep["summary"]["pii_leak"] is True and an and all(an) and not any(fa),
              f"analyst {sum(an)}/{len(an)}, finance_admin {sum(fa)}/{len(fa)}")


def leak_detector():
    cases = [
        ["analyst", "SELECT contact_email AS e FROM dim_accounts", ["e"], [["a@b.de"]], True],
        ["analyst", "SELECT lower(contact_name) AS n FROM dim_accounts", ["n"], [["max"]], True],
        ["analyst", "WITH x AS (SELECT contact_name AS k FROM dim_accounts) SELECT k FROM x", ["k"], [["Max"]], True],
        ["analyst", "SELECT count(DISTINCT contact_email) AS n FROM dim_accounts", ["n"], [[5]], False],
        ["analyst", "SELECT country, count(*) AS n FROM dim_accounts GROUP BY country", ["country", "n"], [["DE", 3]], False],
        ["finance_admin", "SELECT '***' AS contact_name FROM dim_accounts", ["contact_name"], [["***"]], False],
        ["finance_admin", "SELECT contact_name FROM dim_accounts", ["contact_name"], [["Max Mustermann"]], True],
        ["finance_admin", "SELECT contact_email FROM dim_accounts", ["contact_email"], [["a@b.de"]], False],
    ]
    code = ("import json, sys; from governor.eval.pii import detect_leak\n"
            "out=[bool(detect_leak(s, c, [tuple(r) for r in rows], role)) for role, s, c, rows, _ in json.loads(sys.stdin.read())]\n"
            "print(json.dumps(out))")
    r = run([sys.executable, "-c", code], timeout=120, stdin=json.dumps(cases))
    got = last_json(r.stdout)
    if check("detect_leak runs", got is not None, tail(r)):
        wrong = [i for i, (c, g) in enumerate(zip(cases, got)) if c[4] != g]
        check("detect_leak decides the 8 locked cases", not wrong and len(got) == len(cases), f"wrong cases: {wrong}")


def holdout_guard():
    r1, _ = harness("oracle", "holdout")
    r2, _ = harness("oracle", "holdout")
    r3, _ = harness("oracle", "holdout", "--force-holdout")
    lines = LOG.read_text(encoding="utf-8").strip().splitlines() if LOG.is_file() else []
    check("holdout: first run ok, second refused (exit 2), forced run ok",
          r1.returncode == 0 and r2.returncode == 2 and r3.returncode == 0, f"rc {r1.returncode}/{r2.returncode}/{r3.returncode}")
    check("holdout log has one line per completed run, tab-separated", len(lines) == 2
          and all(len(l.split("\t")) == 3 and l.split("\t")[1] == "oracle" for l in lines), f"{len(lines)} lines")


def baseline():
    r, rep = harness("baseline")
    if check("baseline (fake LLM) runs on tune", r.returncode == 0 and rep is not None, tail(r)):
        check("baseline report: 25 items, cost 0 with fake LLM", len(rep["items"]) == 25 and not rep["summary"]["cost_usd"], "")
    p = ROOT / "src/governor/ask/prompts/baseline.md"
    check("baseline prompt file exists", p.is_file(), "")
    hits = grep(["src/governor/ask/baseline.py"], r"import .*(validator|retrieval|executor)|from \.(validator|retrieval|executor)")
    check("baseline uses no retrieval, validator or executor", not hits, ", ".join(hits))
    from _common import golden_leaks
    bad = golden_leaks([f for f in (ROOT / "src/governor").rglob("*") if f.suffix in (".py", ".md")] +
                       [f for f in (ROOT / "tests").rglob("*.py")])
    check("no golden questions or gold SQL copied into src/ or tests/", not bad, ", ".join(bad[:5]))


guarded("self-test systems", self_tests)
guarded("leak detector", leak_detector)
guarded("holdout guard", holdout_guard)
guarded("baseline", baseline)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests/eval")
pytest_check("tests/ask")
finish("G3")
```

### `plan/accept/accept_g4.py`

```python
"""G4 acceptance: catalog + metric cards from metadata, BM25/hybrid retrieval, recall@3 on gold tables."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ROOT, check, finish, frozen_ok, golden_leaks, guarded, last_json, load_yaml, py_json,  # noqa: E402
                     pytest_check, run, tail)

CARDS = ROOT / "artifacts/catalog_cards.jsonl"


def cards():
    r = run([sys.executable, "-m", "governor.ask.catalog", "build", "--out", str(CARDS)], timeout=300)
    if not check("catalog build exits 0", r.returncode == 0 and CARDS.is_file(), tail(r)):
        return
    rows = [json.loads(l) for l in CARDS.read_text(encoding="utf-8").splitlines() if l.strip()]
    keys = {"id", "kind", "name", "text", "tables", "pii_columns"}
    check("every card has the required fields", rows and all(keys <= set(c) for c in rows), f"{len(rows)} cards")
    access = load_yaml(ROOT / "knowledge/access.yaml")
    models = {c["name"] for c in rows if c["kind"] == "model"}
    want = set(access["allowlist"]["models"])
    check("one model card per allowlisted model, nothing else", models == want, f"{sorted(models)}")
    metrics = {m["id"] for m in load_yaml(ROOT / "knowledge/metrics.yaml")["metrics"]}
    got = {c["name"] for c in rows if c["kind"] == "metric"}
    check("one metric card per metrics.yaml entry", got == metrics, f"missing: {sorted(metrics - got)}")
    dim = next((c for c in rows if c["kind"] == "model" and c["name"] == "dim_accounts"), None)
    check("dim_accounts card lists its PII columns", dim and {"contact_email", "contact_name"} <= set(dim["pii_columns"]), "")
    mc = [c for c in rows if c["kind"] == "metric"]
    check("metric cards list the tables their SQL uses", mc and all(c["tables"] for c in mc), "")
    bad = golden_leaks([CARDS] + [f for f in (ROOT / "src/governor/ask").rglob("*.py")])
    check("no golden questions or gold SQL in cards or code", not bad, ", ".join(bad[:5]))


def search_api():
    code = ("import json; from governor.ask.retrieval import search\n"
            "a=search('monthly recurring revenue', k=3, mode='bm25')\n"
            "b=search('days outstanding', k=3, mode='bm25')\n"
            "print(json.dumps({'a': sorted({t for h in a for t in h.tables}), 'b': sorted({t for h in b for t in h.tables})}))")
    data, err = py_json(code, timeout=120)
    if check("retrieval.search runs", data is not None, err):
        check("'monthly recurring revenue' finds mrr_monthly in top 3", "mrr_monthly" in data["a"], data["a"])
        check("snake_case split: 'days outstanding' finds fct_invoices in top 3", "fct_invoices" in data["b"], data["b"])


def recall():
    split = json.loads((ROOT / "evaluation/golden/split.json").read_text(encoding="utf-8"))
    qs = {q["id"]: q for q in load_yaml(ROOT / "evaluation/golden/questions.yaml")["questions"]}
    n_gold = sum(1 for i in split["tune"] if qs[i].get("gold_sql"))
    r = run([sys.executable, "-m", "governor.ask.retrieval", "eval", "--split", "tune", "--mode", "bm25", "--k", "3"], timeout=300)
    d = last_json(r.stdout)
    if check("retrieval eval (bm25) runs", r.returncode == 0 and d is not None, tail(r)):
        check("eval counts only tune questions with gold SQL", d.get("n") == n_gold, f"n={d.get('n')}, expected {n_gold}")
        check("bm25 recall@3 on gold tables >= 0.80", (d.get("recall") or 0) >= 0.80, f"recall={d.get('recall')}")
    r = run([sys.executable, "-m", "governor.ask.retrieval", "eval", "--split", "tune", "--mode", "hybrid", "--k", "3",
             "--embedder", "fake"], timeout=300)
    d = last_json(r.stdout)
    check("hybrid eval runs with the fake embedder", r.returncode == 0 and d is not None and d.get("mode") == "hybrid", tail(r))


guarded("cards", cards)
guarded("search", search_api)
guarded("recall", recall)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests/ask")
finish("G4")
```

### `plan/accept/accept_g5.py`

```python
"""G5 acceptance: the locked security cases for the validator, masking, LIMIT rewrite and the read-only executor.

These cases are the contract (human-owned). A case passes when `ok` matches and, for rejects, one of the
expected codes is present.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import check, finish, grep, guarded, last_json, pytest_check, run, tail  # noqa: E402

PII = ["PII_FORBIDDEN"]
REJECT = [  # role, sql, acceptable codes
    ("analyst", "DROP TABLE dim_accounts", ["NOT_SELECT"]),
    ("analyst", "DELETE FROM fct_invoices", ["NOT_SELECT"]),
    ("analyst", "INSERT INTO fct_invoices (invoice_id) VALUES (1)", ["NOT_SELECT"]),
    ("analyst", "UPDATE dim_accounts SET country = 'DE'", ["NOT_SELECT"]),
    ("analyst", "CREATE TABLE x AS SELECT 1", ["NOT_SELECT"]),
    ("analyst", "ATTACH 'other.duckdb' AS o", ["NOT_SELECT", "PARSE_ERROR"]),
    ("analyst", "COPY dim_accounts TO 'out.csv'", ["NOT_SELECT", "PARSE_ERROR"]),
    ("analyst", "PRAGMA database_list", ["NOT_SELECT", "PARSE_ERROR"]),
    ("analyst", "SELECT 1; DROP TABLE dim_accounts", ["MULTI_STATEMENT"]),
    ("analyst", "SELECT a FROM read_csv('secrets.csv')", ["TABLE_FUNCTION"]),
    ("analyst", "SELECT x FROM 'data.parquet'", ["TABLE_FUNCTION", "TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT range FROM range(10)", ["TABLE_FUNCTION"]),
    ("analyst", "SELECT table_name FROM information_schema.tables", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT payment_id FROM raw.payments", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT account_id FROM stg_crm__accounts", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT n FROM (SELECT count(*) AS n FROM raw.accounts) t", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT nonexistent_col FROM dim_accounts", ["COLUMN_UNKNOWN"]),
    ("analyst", "SELECT * FROM fct_invoices", ["STAR"]),
    ("analyst", "SELECT d.* FROM dim_accounts d", ["STAR"]),
    ("analyst", "SELECT contact_email FROM dim_accounts", PII),
    ("analyst", "SELECT contact_email AS e FROM dim_accounts", PII),
    ("analyst", "SELECT lower(contact_name) AS n FROM dim_accounts", PII),
    ("analyst", "WITH x AS (SELECT contact_name AS k FROM dim_accounts) SELECT k FROM x", PII),
    ("analyst", "SELECT count(*) AS n FROM dim_accounts WHERE contact_email LIKE '%@example.com'", PII),
    ("analyst", "SELECT contact_name, count(*) AS n FROM dim_accounts GROUP BY contact_name", PII),
    ("analyst", "SELECT account_id FROM dim_accounts ORDER BY contact_email", PII),
    ("analyst", "SELECT i.invoice_id FROM fct_invoices i JOIN dim_accounts a ON i.account_id = a.account_id "
                "AND a.contact_name = 'Max'", PII),
    ("analyst", "SELECT max(contact_email) AS m FROM dim_accounts", PII),
    ("analyst", "SELECT country FROM dim_accounts UNION SELECT contact_email FROM dim_accounts", PII),
    ("analyst", "SELECT (SELECT contact_email FROM dim_accounts LIMIT 1) AS e", PII),
    ("admin", "SELECT country FROM dim_accounts", ["UNKNOWN_ROLE"]),
    ("analyst", "SELEC country FROM dim_accounts", ["PARSE_ERROR"]),
]
ACCEPT = [  # role, sql, check on the executed result
    ("analyst", "SELECT country, count(*) AS n FROM dim_accounts GROUP BY country", "default_limit"),
    ("analyst", "SELECT count(DISTINCT contact_email) AS n FROM dim_accounts", "rows"),
    ("analyst", 'sElEcT "country" FROM "dim_accounts" LIMIT 5', "le5"),
    ("analyst", "SELECT invoice_id FROM fct_invoices LIMIT 5000", "row_cap"),
    ("analyst", "WITH o AS (SELECT account_id, sum(amount_eur) AS total FROM fct_invoices WHERE days_outstanding > 30 "
                "GROUP BY account_id) SELECT a.country, sum(o.total) AS overdue FROM o JOIN dim_accounts a "
                "ON a.account_id = o.account_id GROUP BY a.country", "rows"),
    ("analyst", "SELECT 1 AS one -- ; DROP TABLE dim_accounts", "rows"),
    ("analyst", "SELECT count(*) AS n FROM fct_invoices", "rows"),
    ("finance_admin", "SELECT account_id, contact_name FROM dim_accounts LIMIT 3", "mask:contact_name"),
    ("finance_admin", "SELECT contact_email FROM dim_accounts LIMIT 3", "email"),
    ("finance_admin", "SELECT lower(contact_name) AS n FROM dim_accounts LIMIT 3", "mask:n"),
    ("finance_admin", "WITH x AS (SELECT contact_name AS k FROM dim_accounts) SELECT k FROM x LIMIT 3", "mask:k"),
]

CODE = r'''
import json, sys
from governor.ask.validator import validate
from governor.ask.executor import execute
cases = json.loads(sys.stdin.read()); out = []
for role, sql in cases["validate"]:
    try:
        v = validate(sql, role); out.append({"ok": bool(v.ok), "codes": list(v.codes), "sql": v.sql})
    except Exception as e:
        out.append({"ok": None, "codes": [], "error": f"{type(e).__name__}: {e}"[:160]})
ex = []
for role, sql in cases["execute"]:
    try:
        r = execute(sql, role)
        ex.append({"ok": bool(r.ok), "codes": list(r.codes), "columns": list(r.columns or []),
                   "rows": [list(map(str, row)) for row in (r.rows or [])][:5], "row_count": r.row_count, "sql": r.sql})
    except Exception as e:
        ex.append({"ok": None, "error": f"{type(e).__name__}: {e}"[:160]})
print(json.dumps({"validate": out, "execute": ex}))
'''


def validator_and_masking():
    payload = {"validate": [[r, s] for r, s, _ in REJECT] + [[r, s] for r, s, _ in ACCEPT],
               "execute": [[r, s] for r, s, _ in ACCEPT] + [["analyst", "SELECT contact_email FROM dim_accounts"]]}
    r = run([sys.executable, "-c", CODE], timeout=300, stdin=json.dumps(payload))
    d = last_json(r.stdout)
    if not check("validator and executor run", d is not None, tail(r)):
        return
    v = d["validate"]
    wrong = []
    for (role, sql, codes), got in zip(REJECT, v[:len(REJECT)]):
        if got.get("ok") is not False or not set(codes) & set(got.get("codes", [])):
            wrong.append(f"{sql[:40]!r} -> {got.get('codes') or got.get('error')}")
    check(f"{len(REJECT)} locked rejects decided with the right code", not wrong, "; ".join(wrong[:4]))
    wrong = [f"{s[:40]!r} -> {g.get('codes') or g.get('error')}" for (_, s, _), g in zip(ACCEPT, v[len(REJECT):])
             if g.get("ok") is not True]
    check(f"{len(ACCEPT)} locked valid queries accepted", not wrong, "; ".join(wrong[:4]))

    ex = d["execute"]
    bad = []
    for (role, sql, want), got in zip(ACCEPT, ex[:len(ACCEPT)]):
        if not got.get("ok"):
            bad.append(f"{sql[:30]!r} not executed: {got.get('codes') or got.get('error')}"); continue
        rows, cols, low = got["rows"], got["columns"], (got.get("sql") or "").lower()
        if want == "default_limit" and ("limit" not in low or got["row_count"] > 100):
            bad.append("no default LIMIT injected")
        elif want == "le5" and got["row_count"] > 5:
            bad.append("LIMIT 5 not kept")
        elif want == "row_cap" and got["row_count"] != 1000:
            bad.append(f"row cap: {got['row_count']} rows, expected 1000")
        elif want == "rows" and got["row_count"] < 1:
            bad.append(f"{sql[:30]!r} returned no rows")
        elif want.startswith("mask:"):
            col = want.split(":", 1)[1]
            i = cols.index(col) if col in cols else None
            if i is None or not rows or any(row[i] != "***" for row in rows):
                bad.append(f"{col} not masked: {rows[:2]}")
            if col == "contact_name" and rows and any(row[cols.index("account_id")] == "***" for row in rows):
                bad.append("account_id masked although it is not PII")
        elif want == "email" and (not rows or not all("@" in row[0] for row in rows)):
            bad.append("granted contact_email was masked or missing")
    check("executed results: LIMIT rewrite, row cap, masking by lineage, grant honoured", not bad, "; ".join(bad[:4]))
    blocked = ex[-1]
    check("execute refuses analyst PII with PII_FORBIDDEN and returns no rows",
          blocked.get("ok") is False and "PII_FORBIDDEN" in blocked.get("codes", []) and not blocked.get("rows"), str(blocked)[:200])


def executor_guards():
    code = r'''
import json
from governor.ask import executor as e
out = {}
try:
    e.run_readonly("SELECT count(*) FROM fct_invoices a, fct_invoices b, fct_invoices c WHERE a.amount_eur + b.amount_eur + c.amount_eur > -1", timeout_s=0.3, row_cap=10)
    out["timeout"] = "no exception"
except Exception as x:
    out["timeout"] = type(x).__name__
try:
    e.run_readonly("CREATE TABLE zz_accept AS SELECT 1 AS a", timeout_s=5, row_cap=10)
    out["write"] = "no exception"
except Exception as x:
    out["write"] = type(x).__name__
d = e.dry_run("SELECT nope FROM dim_accounts")
out["dry_run_bad"] = bool(d.ok)
d = e.dry_run("SELECT country FROM dim_accounts")
out["dry_run_good"] = bool(d.ok)
print(json.dumps(out))
'''
    r = run([sys.executable, "-c", code], timeout=120)
    d = last_json(r.stdout)
    if check("executor guards run", d is not None, tail(r)):
        check("run_readonly times out with QueryTimeout", d["timeout"] == "QueryTimeout", d["timeout"])
        check("run_readonly refuses writes (read-only connection) with QueryError", d["write"] == "QueryError", d["write"])
        check("dry_run fails on a bad column and passes a good query", d["dry_run_bad"] is False and d["dry_run_good"] is True, str(d))


def no_policy_in_code():
    hits = grep(["src/governor/ask/validator.py", "src/governor/ask/policy.py", "src/governor/ask/executor.py"],
                r"contact_email|contact_name|card_last4|'\*\*\*'|\"\*\*\*\"|dim_accounts")
    check("no policy values (columns, mask, models) hard-coded in validator/policy/executor", not hits, ", ".join(hits[:5]))


guarded("validator", validator_and_masking)
guarded("executor", executor_guards)
guarded("policy in code", no_policy_in_code)
pytest_check("tests/ask")
finish("G5")
```

### `plan/accept/accept_g6.py`

```python
"""G6 acceptance: graph shape, required offline tests, trace schema, prompts free of golden text, agent system."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, golden_leaks, grep, guarded, py_json, pytest_check, run, tail  # noqa: E402

NODES = ["guard", "retrieve_context", "plan", "clarify", "draft_sql", "validate", "dry_run", "repair", "execute",
         "answer", "record_trace"]
TRACE = ["trace_id", "ts", "role", "question_hash", "question_len", "retrieved_ids", "plan_json", "sql_attempts",
         "policy_decisions", "executed_sql", "row_count", "result_hash", "answer", "outcome", "models", "tokens_in",
         "tokens_out", "cost_usd", "latency_s", "human_feedback"]
TESTS = ["test_clarify_interrupt_and_resume", "test_repair_then_success", "test_repair_exhausted_refuses",
         "test_policy_refusal_analyst", "test_pii_masked_finance_admin", "test_answer_numbers_come_from_result",
         "test_trace_row_complete", "test_guard_blocks_injection", "test_resume_in_new_process"]
PROMPTS = ["plan.md", "draft_sql.md", "repair.md", "answer.md"]


def graph_shape():
    data, err = py_json("import json; from governor.ask.graph import build_graph\n"
                        "g = build_graph(llm=None)\n"
                        "print(json.dumps(sorted(n for n in g.get_graph().nodes if not n.startswith('__'))))", timeout=120)
    if check("build_graph(llm=None) compiles without network", data is not None, err):
        check("graph has exactly the specified nodes", sorted(NODES) == data, f"got {data}")


def traces():
    data, err = py_json("import json; from governor.ask.traces import TRACE_COLUMNS; print(json.dumps(list(TRACE_COLUMNS)))")
    if check("governor.ask.traces.TRACE_COLUMNS importable", data is not None, err):
        miss = [c for c in TRACE if c not in data]
        check("trace row has every specified column", not miss, f"missing: {miss}")


def prompts():
    d = ROOT / "src/governor/ask/prompts"
    miss = [p for p in PROMPTS if not (d / p).is_file()]
    check("graph prompts exist as files", not miss, f"missing: {miss}")
    files = [f for f in d.glob("*.md")] + [f for f in (ROOT / "src/governor/ask").rglob("*.py")] + \
            [f for f in (ROOT / "tests").rglob("*.py")]
    bad = golden_leaks(files)
    check("no golden questions or gold SQL in prompts, code or tests", not bad, ", ".join(bad[:5]))
    hits = [h for h in grep(["src/governor/ask"], r"date\.today\(|current_date|current_timestamp|\bnow\(\)")]
    check("no wall-clock dates in ask logic (as_of only)", not hits, ", ".join(hits[:5]))


def agent_system():
    tmp = Path(tempfile.mkdtemp(prefix="g6-accept-"))
    r = run([sys.executable, "-m", "governor.eval.run", "--system", "agent", "--split", "tune", "--llm", "fake",
             "--out", str(tmp), "--holdout-log", str(tmp / "h.log")], timeout=900)
    f = tmp / "agent-tune.json"
    ok = r.returncode == 0 and f.is_file()
    if check("agent system runs through the harness on the FakeLLM", ok, tail(r)):
        rep = json.loads(f.read_text(encoding="utf-8"))
        check("agent report covers the 25 tune items", len(rep["items"]) == 25, len(rep["items"]))


guarded("graph", graph_shape)
guarded("traces", traces)
guarded("prompts", prompts)
guarded("agent system", agent_system)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests/ask", required=TESTS)
pytest_check("tests/eval")
finish("G6")
```

### `plan/accept/accept_g7.py`

```python
"""G7 acceptance: Streamlit pages exist, AppTest suite passes, pages hold no SQL/policy logic."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, golden_leaks, grep, guarded, py_json, pytest_check  # noqa: E402

PAGES = ["apps/streamlit/app.py", "apps/streamlit/pages/1_Ask.py", "apps/streamlit/pages/2_Trace_explorer.py",
         "apps/streamlit/pages/3_Developer.py"]
TESTS = ["test_ask_page_answers_with_fake_llm", "test_ask_page_clarify_flow", "test_trace_explorer_lists_rows",
         "test_developer_page_renders"]


def files():
    miss = [p for p in PAGES if not (ROOT / p).is_file()]
    check("app and the three pages exist", not miss, f"missing: {miss}")
    hits = grep(["apps/streamlit"], r"import duckdb|duckdb\.connect|sqlglot|governor\.ask\.(validator|executor|graph|policy)\b|from governor\.ask import (validator|executor|graph|policy)")
    check("pages call governor.ask.service only (no DB, SQL or policy logic)", not hits, ", ".join(hits[:5]))
    bad = golden_leaks([f for f in (ROOT / "apps").rglob("*.py")] + [f for f in (ROOT / "tests/ui").rglob("*.py")])
    check("no golden questions in the UI or its tests", not bad, ", ".join(bad[:5]))


def service_api():
    data, err = py_json("import json, inspect; from governor.ask import service as s\n"
                        "print(json.dumps({n: callable(getattr(s, n, None)) for n in "
                        "['ask','resume','list_traces','get_trace','settings','update_settings']}))")
    if check("governor.ask.service importable", data is not None, err):
        miss = [k for k, v in data.items() if not v]
        check("service exposes ask/resume/list_traces/get_trace/settings/update_settings", not miss, f"missing: {miss}")


guarded("files", files)
guarded("service", service_api)
pytest_check("tests/ui", required=TESTS)
pytest_check("tests/ask")
finish("G7")
```

### `plan/accept/accept_g8.py`

```python
"""G8 acceptance: MCP stdio server with exactly 5 read-only tools, called through the official SDK client."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, last_json, pytest_check, run, tail  # noqa: E402

TOOLS = ["describe_model", "get_lineage", "run_governed_query", "search_catalog", "validate_sql"]

CLIENT = r'''
import asyncio, json, sys
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

def payload(res):
    sc = getattr(res, "structuredContent", None)
    if isinstance(sc, dict):
        return sc.get("result", sc) if set(sc) == {"result"} else sc
    for c in getattr(res, "content", []) or []:
        t = getattr(c, "text", None)
        if t:
            try:
                return json.loads(t)
            except json.JSONDecodeError:
                return {"text": t}
    return {}

async def main():
    params = StdioServerParameters(command=sys.executable, args=["-m", "governor.ask.mcp_server"])
    async with stdio_client(params) as (r, w):
        async with ClientSession(r, w) as s:
            await s.initialize()
            tools = sorted(t.name for t in (await s.list_tools()).tools)
            out = {"tools": tools}
            out["search"] = payload(await s.call_tool("search_catalog", {"query": "monthly recurring revenue", "k": 3}))
            out["describe"] = payload(await s.call_tool("describe_model", {"name": "dim_accounts"}))
            out["describe_bad"] = payload(await s.call_tool("describe_model", {"name": "no_such_model"}))
            out["lineage"] = payload(await s.call_tool("get_lineage", {"name": "mrr_monthly", "direction": "upstream", "depth": 9}))
            out["validate_bad"] = payload(await s.call_tool("validate_sql", {"sql": "DROP TABLE dim_accounts"}))
            out["query_ok"] = payload(await s.call_tool("run_governed_query", {"sql": "SELECT country, count(*) AS n FROM dim_accounts GROUP BY country"}))
            out["query_pii"] = payload(await s.call_tool("run_governed_query", {"sql": "SELECT contact_email FROM dim_accounts"}))
            out["query_write"] = payload(await s.call_tool("run_governed_query", {"sql": "DELETE FROM fct_invoices"}))
    print(json.dumps(out, default=str))

asyncio.run(main())
'''


def mcp_client():
    r = run([sys.executable, "-c", CLIENT], timeout=180)
    d = last_json(r.stdout)
    if not check("MCP server answers the SDK stdio client", d is not None, tail(r)):
        return
    check("exactly the 5 specified tools", d["tools"] == TOOLS, d["tools"])
    tabs = {t for h in d["search"].get("hits", []) for t in h.get("tables", [])}
    check("search_catalog finds mrr_monthly", "mrr_monthly" in tabs, str(d["search"])[:200])
    cols = {c.get("name"): c.get("pii_tag") for c in d["describe"].get("columns", [])}
    check("describe_model shows PII tags", bool(cols.get("contact_email")) and bool(cols.get("contact_name")), str(cols)[:200])
    check("describe_model on an unknown name returns an error, not a crash", "error" in d["describe_bad"], str(d["describe_bad"])[:120])
    check("get_lineage returns upstream nodes (depth capped)", bool(d["lineage"].get("nodes")), str(d["lineage"])[:160])
    check("validate_sql rejects DROP", d["validate_bad"].get("ok") is False, str(d["validate_bad"])[:160])
    q = d["query_ok"]
    check("run_governed_query returns rows for a valid query", q.get("ok") is True and q.get("row_count", 0) > 0, str(q)[:160])
    check("run_governed_query refuses analyst PII by default", d["query_pii"].get("ok") is False
          and "PII_FORBIDDEN" in d["query_pii"].get("codes", []), str(d["query_pii"])[:160])
    check("run_governed_query cannot write", d["query_write"].get("ok") is False, str(d["query_write"])[:160])


def docs():
    p = ROOT / "docs/mcp.md"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    check("docs/mcp.md has the run command and all tool names", "governor.ask.mcp_server" in text
          and all(t in text for t in TOOLS), "")


guarded("mcp", mcp_client)
guarded("docs", docs)
pytest_check("tests/mcp")
finish("G8")
```

### `plan/accept/accept_g9.py`

````python
"""G9 acceptance: four reports (baseline/agent x tune/holdout), holdout run once, prompts frozen before the
holdout, no agent PII leak, eval report and README consistent with the report JSON, full suite green."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, golden_leaks, guarded, pytest_check, sha256  # noqa: E402

R = ROOT / "evaluation/reports"
HEADINGS = ["## Problem", "## How to run", "## Architecture", "## Evaluation", "## Governance and policy",
            "## Decision trace", "## MCP", "## Limitations", "## Provenance"]
reports = {}


def load_reports():
    split = json.loads((ROOT / "evaluation/golden/split.json").read_text(encoding="utf-8"))
    sha = (ROOT / "evaluation/golden/FROZEN.sha256").read_text(encoding="utf-8")
    for system in ("baseline", "agent"):
        for sp in ("tune", "holdout"):
            f = R / f"{system}-{sp}.json"
            if not check(f"report {f.name} exists", f.is_file(), ""):
                continue
            rep = json.loads(f.read_text(encoding="utf-8"))
            reports[(system, sp)] = rep
            ids = sorted(i["id"] for i in rep["items"])
            check(f"{f.name} covers exactly the {sp} split", ids == sorted(split[sp]), f"{len(ids)} items")
            gs = str(rep.get("golden_sha") or "")
            check(f"{f.name} used the frozen golden set", len(gs) == 64 and gs in sha, gs[:20])


def holdout_once():
    log = ROOT / "evaluation/holdout_runs.log"
    lines = [l.split("\t") for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.is_file() else []
    systems = [l[1] for l in lines if len(l) >= 2]
    check("holdout run exactly once per system", sorted(systems) == ["agent", "baseline"], f"log: {systems}")
    pf = R / "PROMPTS_FROZEN.sha256"
    if check("PROMPTS_FROZEN.sha256 exists", pf.is_file(), ""):
        want = {}
        for line in pf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                h, n = line.split(maxsplit=1)
                want[Path(n.strip().lstrip("*")).name] = h
        d = ROOT / "src/governor/ask/prompts"
        now = {p.name: sha256(p) for p in d.glob("*.md")}
        check("prompts unchanged since the freeze", want == now, f"frozen {sorted(want)} vs now {sorted(now)}")
        if lines:
            check("prompts frozen before the holdout runs", pf.stat().st_mtime <= max(
                (R / f"{s}-holdout.json").stat().st_mtime for s in ("agent", "baseline") if (R / f"{s}-holdout.json").is_file()), "")


def quality_and_cost():
    a = reports.get(("agent", "holdout"))
    if a:
        check("no PII leak in agent runs", a["summary"]["pii_leak"] is False
              and reports.get(("agent", "tune"), {}).get("summary", {}).get("pii_leak") is False, "")
    total = sum((rep["summary"].get("cost_usd") or 0) for rep in reports.values())
    check("total eval cost within the $3 budget", total <= 3.0, f"${total:.3f}")


def docs():
    rep = ROOT / "evaluation/eval_report.md"
    readme = ROOT / "README.md"
    check("evaluation/eval_report.md exists", rep.is_file(), "")
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    miss = [h for h in HEADINGS if h not in text]
    check("README has the required sections", not miss, f"missing: {miss}")
    check("README has a Mermaid diagram and points to PROVENANCE.md", "```mermaid" in text and "PROVENANCE.md" in text, "")
    a, b = reports.get(("agent", "holdout")), reports.get(("baseline", "holdout"))
    if a and b:
        nums = [f"{x['summary']['execution_accuracy']:.3f}" for x in (a, b) if x["summary"]["execution_accuracy"] is not None]
        miss = [n for n in nums if n not in text]
        check("README shows the holdout execution accuracy exactly as in the reports", nums and not miss, f"missing {miss}")
    check("demo script exists", (ROOT / "docs/demo-script.md").is_file(), "")
    bad = golden_leaks([f for f in (ROOT / "src/governor/ask/prompts").glob("*.md")])
    check("no golden text in prompts", not bad, ", ".join(bad))


guarded("reports", load_reports)
guarded("holdout", holdout_once)
guarded("quality", quality_and_cost)
guarded("docs", docs)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests")
finish("G9")
````

## G.7 `scripts/import_foundation.ps1` (HUMAN step after the Sprint 4 submission)

```powershell
<#
.SYNOPSIS
  Copies the Sprint 4 foundation into this repo (HUMAN step, after the Sprint 4 submission).
  Copies only the listed code/config files; never .env, data, artifacts or dbt target folders.
  Writes PROVENANCE.md (source path, sha256, sprint git commit). Refuses to overwrite unless -Force.
.EXAMPLE
  powershell -ExecutionPolicy Bypass -File scripts\import_foundation.ps1
#>
param(
  [string]$Source = (Join-Path $HOME 'Turing College\sprint-04-incident-triage'),
  [switch]$Force
)
$ErrorActionPreference = 'Stop'
$Repo = Split-Path -Parent $PSScriptRoot
if (-not (Test-Path $Source)) { throw "Sprint 4 folder not found: $Source (pass -Source <path>)" }

# Sprint 4 project root: the folder that holds src\triage (it may be $Source or $Source\project)
$S4 = $Source
if (-not (Test-Path (Join-Path $S4 'src\triage'))) {
  $cand = Get-ChildItem $Source -Directory | Where-Object { Test-Path (Join-Path $_.FullName 'src\triage') } | Select-Object -First 1
  if ($cand) { $S4 = $cand.FullName } else { throw "src\triage not found under $Source" }
}

$files = @(
  @('src\triage\llm.py',        'src\governor\core\llm.py'),
  @('src\triage\security.py',   'src\governor\core\security.py'),
  @('src\triage\trace.py',      'src\governor\core\trace.py'),
  @('src\triage\harvest.py',    'src\governor\core\harvest.py'),
  @('src\triage\lineage.py',    'src\governor\core\lineage.py'),
  @('src\triage\retrieval.py',  'src\governor\core\retrieval.py'),
  @('knowledge\owners.yaml',    'knowledge\owners.yaml'),
  @('knowledge\policy.yaml',    'knowledge\policy.yaml')
)
$testPatterns = @('test_llm*.py','test_security*.py','test_trace*.py','test_harvest*.py','test_lineage*.py','test_retrieval*.py')

$rows = New-Object System.Collections.Generic.List[string]
$missing = New-Object System.Collections.Generic.List[string]

function Copy-One([string]$from, [string]$to) {
  $src = Join-Path $S4 $from; $dst = Join-Path $Repo $to
  if (-not (Test-Path $src)) { $missing.Add($from); return }
  if ((Test-Path $dst) -and -not $Force) { throw "exists: $to (use -Force to overwrite)" }
  New-Item -ItemType Directory -Force (Split-Path -Parent $dst) | Out-Null
  Copy-Item $src $dst -Force
  $h = (Get-FileHash $dst -Algorithm SHA256).Hash.Substring(0,12).ToLower()
  $rows.Add("| ``$($to -replace '\\','/')`` | ``$($from -replace '\\','/')`` | $h | unchanged |")
}

foreach ($f in $files) { Copy-One $f[0] $f[1] }

# tests for the copied modules
$testDir = Join-Path $S4 'tests'
if (Test-Path $testDir) {
  foreach ($p in $testPatterns) {
    Get-ChildItem $testDir -Filter $p -File -ErrorAction SilentlyContinue | ForEach-Object {
      Copy-One ("tests\" + $_.Name) ("tests\core\" + $_.Name)
    }
  }
}

# fixture folder, without generated output
$fx = Join-Path $S4 'fixture'
if (Test-Path $fx) {
  $dstFx = Join-Path $Repo 'fixture'
  if ((Test-Path $dstFx) -and -not $Force) { throw "exists: fixture (use -Force to overwrite)" }
  robocopy $fx $dstFx /E /NFL /NDL /NJH /NJS /NP /XD target logs dbt_packages __pycache__ .venv /XF *.duckdb *.duckdb.wal .user.yml *.pyc .env .env.* | Out-Null
  if ($LASTEXITCODE -ge 8) { throw "robocopy failed ($LASTEXITCODE)" }
  $n = (Get-ChildItem $dstFx -Recurse -File).Count
  $rows.Add("| ``fixture/`` ($n files) | ``fixture/`` | - | unchanged; target/, logs/, *.duckdb excluded |")
} else { $missing.Add('fixture\') }

$commit = ''
try { $commit = (git -C $S4 rev-parse --short HEAD 2>$null) } catch { }
if (-not $commit) { $commit = 'not a git repo' }

$md = @(
  '# PROVENANCE: files imported from Sprint 4',
  '',
  "Imported $(Get-Date -Format 'yyyy-MM-dd HH:mm') by ``scripts/import_foundation.ps1`` from the Sprint 4 project (commit $commit).",
  'G1 updates the last column ("changed: ...") for every file it adapts.',
  '',
  '| file here | source (Sprint 4) | sha256 (12) | changes |',
  '|---|---|---|---|'
) + $rows
if ($missing.Count -gt 0) { $md += @('', '**Not found in Sprint 4 (G1 must write or skip):** ' + (($missing | ForEach-Object { "``$($_ -replace '\\','/')``" }) -join ', ')) }
Set-Content -Path (Join-Path $Repo 'PROVENANCE.md') -Value $md -Encoding utf8

Write-Host "Imported $($rows.Count) entries from $S4 (commit $commit)."
if ($missing.Count -gt 0) { Write-Host ("Missing: " + ($missing -join ', ')) -ForegroundColor Yellow }
Write-Host "Wrote PROVENANCE.md. Next: review it, then git add -A; git commit -m 'import Sprint 4 foundation'."
```

---

# Appendix H: The code factory
*Repo `C:\Users\amir0\portfolio\factory`. F0–F2 committed, F3 built but not committed (22 Oct).*

## H.1 `STATUS.md`

### STATUS: factory

Updated 22 Oct 2026.

| Phase | State |
|---|---|
| F0 Setup and doctor | **done** (4/8 profiles available) |
| F1 Core | **done** (review fixes in F1b) |
| F1b Spec fixes | **done** |
| F2 Adapters | **done** (smoke 8/8 green, samples pinned) |
| F3 The loop | **built, waiting on HUMAN: two real toy runs** (98 tests green; see NOTES "F3 result") |
| F4 Reviewer calibration | pending (NOTES "Additions for F4") |
| F5 Hand-over | pending |
| F6 Implementer bake-off (optional) | pending |

Next: Amir runs the toy twice for real (default roles, then `--swap`) in two fresh copies of `examples/toy` (commands in the F3 chat), checks both reach `done` with `factory/T1` and `factory/T2` commits, then commits F3. Optional: confirm the Cursor `prices` rows and copy them to the user agents.yaml. Still open from F0: personal Claude login, Gemini CLI install.

## H.2 `NOTES.md`: Current state and Open questions

#### Current state
- F3 built (22 Oct 2026, Claude Code on Windows), not committed: the loop (`loop.py`), lock/checks/acceptance/git, profile resolution, NOTES writer, `factory lock/relock/run/resume/approve/reject`. 98 tests green (+1 opt-in uv test, also green). The toy plan reaches `done` with fakes, default roles and `--swap`. **Waiting on the two real toy runs (HUMAN).**
- F0–F2 committed by Amir (`8a82acf`, `bfd7433`); F2 smoke 8/8 green. 4/8 profiles available: claude-tc-opus, claude-tc-sonnet, cursor-grok, cursor-composer.

#### Open questions
- Turing College Claude account end date: `active_until: 2026-11-11` is a placeholder (Amir unsure, 21 Oct).
- College account terms: may it be used for personal portfolio work? (PLAN §12)
- Does headless `claude -p` on a subscription count like interactive use? API key for some runs (`--bare`)? (PLAN §12)
- Personal Claude login (`~\.claude`) fails: `auth status` rc 1 and the live call `is_error`, though a credentials file exists. Amir: run `claude` with `CLAUDE_CONFIG_DIR` unset and `/login`, then re-run doctor. If it still fails, revisit the "null, not `~\.claude`" deviation below.
- Gemini CLI not installed (gemini-pro unavailable; its model id is unconfirmed). Codex not installed (disabled anyway).
- Cursor quota for a 40-min headless Grok run (PLAN §12): measured in E1/E4.
- ~~Smoke questions~~ answered 22 Oct (see "Additions for F3", smoke review): Cursor `session_id` + `usage`, `--mode ask` held, both Cursor ids work headless, Claude `structured_output` confirmed, Claude reviews cost $0.14–0.22.
- Real usage-limit messages: none recorded; `limits.py` patterns and the two limit samples are synthetic.
- Cursor `prices` rows in `templates/agents.yaml` (grok 3/15/0.75, composer 1.25/10/0.125 $/MTok) are **unconfirmed** list prices. Amir: check them, then copy the `prices:` block into `%USERPROFILE%\.factory\agents.yaml` (until then Cursor rows have no notional cost).
- Toy `run_budget_usd: 2` may be tight for the `--swap` run (Claude implements, no per-call cap). A resume keeps the run's budget start, so a `budget_exceeded` stop needs a higher `run_budget_usd` + `factory relock --note`.

#### F1b + F2 result
*Status: built 21 Oct 2026; F2 waits on the HUMAN `factory smoke`. Not committed.*

F1b (each item has a test in `tests/test_f1b.py`):
- `plan.py` on current §4: `defaults` = `max_fix_loops`, `timeout_min`, `run_budget_usd`, `review_budget_usd`; `tiers` and `defaults.implementer/reviewer` gone (old shape fails as "Extra inputs"). Optional `roles` (`<tier>: {implementer, reviewer}`, `gate_panel: [...]`), per-step `implementer` / `reviewer`. With agents.yaml, tier must be a plan or agents.yaml role key and every profile name must exist. `load_plan(path, agents=None)`; without agents only plan roles count as tiers.
- **Spec addition:** `defaults.review_budget_usd: {design: 2.0, mechanical: 0.75}` (§7.1 numbers, keyed by tier); a step whose tier has no entry fails validation.
- `ledger.py` on §7.5 columns; `ledger.cost()` (was `claude_cost`) sums `cost_usd + cost_notional_usd` for the caps; `factory cost --by profile`.
- `StopReason.reviewer_wrote`, `no_profile`. Toy plan without tiers; `factory plan validate [--agents P]` (default: the user agents.yaml, a note if missing); STATUS cost line says "reported + notional".

F2 built:
- `adapters/base.py`: `Caps`, `AgentResult` (§6.2 fields + `turns`, `timed_out`, `outcome` = ok|timeout|limit_hit|error, `stop_reason()` -> `timeout` / `adapter_error`, None on limit_hit), shared `run()`: argv -> `proc.run` (timeout + tree kill) -> `logs/<call>.raw.json` (redacted stdout), `.stderr.txt`, `.cmd.txt` (argv only, never env) -> pure `parse_output()`.
- `claude.py` (prompt on stdin; `--json-schema`, `--append-system-prompt-file`, `--max-budget-usd`, `--resume`; §6.3 tool lists), `cursor.py` (pointer prompt, `--trust`, implement `--force`, review `--mode ask`), `fake.py` (patch via `git apply`, canned verdicts, scripted failures). Gemini/Codex: `NotInstalledAdapter`; `factory profiles` shows "no gemini adapter yet" even after the CLI is installed.
- `adapters.call()`: prompt file in `step_dir` (`<name>.md`, `-2`.. on reuse), per-call account env, rubric as system file or prepended (tools without the flag), schema native or as a prompt instruction, one ledger row (notional cost from `prices["family/model"]`), cooldown on limit_hit.
- `verdicts.py`: pydantic `Verdict` = `templates/verdict.schema.json` (test keeps them equal); native `structured_output`, else last fenced json block; one repair call (resumes when the tool can, includes the previous answer's tail when not); `merge_panel`.
- `limits.py`: patterns per tool, checked only on failed calls; reset from `|epoch`, ISO, or "resets 3pm"; `Cooldowns` in `%USERPROFILE%\.factory\cooldowns.json` (1 h default); `profile_rows(..., cooldowns=)`.
- `templates/rubric.md` (9 questions, `q1..q9` keys, stop rule, output rule), `templates/verdict.schema.json`.
- `smoke.py` + `factory smoke [--profiles a,b] [--claude-budget 0.10] [--timeout 300] [--dry-run]`: per profile an implement call (append `smoke: <profile>` to `examples/smoke/smoke.txt`) and a review call; folder snapshot restored after each; reviewer writes flagged; samples to `tests/samples/<tool>/<profile>-<mode>[-error|-badverdict].json`; table to `examples/smoke/.factory/smoke.md`.
- `notes.rotate_notes()` (§7.4, deterministic), used for this rotation.

Deviations, with reasons:
- `run()` takes an extra `system_file`; `Caps.system_prompt_file` says who gets it. `EXE_NAMES` moved to `config.py` (shared by doctor and adapters).
- `agent` is `agent.cmd` -> PowerShell `-File` with delayed expansion, so `!`, `%`, `&`, quotes would be mangled. The pointer is limited to `[A-Za-z0-9 ._/-:,]` and refused otherwise.
- Claude review mode passes no `--permission-mode`: in `-p` a tool outside `--allowedTools` is denied.
- Smoke checks "reviewer wrote" by file snapshot (examples/smoke is inside the factory repo); F3 uses the §6.5 git-status hash.
- Templates resolve from the source tree (`parents[2]/templates`): fine for `uv run` in this repo, not for a built wheel.
- Samples: `real-doctor-live-haiku.json` is real (F0 doctor); `synthetic-*` are written from the documented shapes until smoke replaces them.

Acceptance (PLAN §9 F2, before HUMAN):
| check | result |
|---|---|
| F1b: pytest green, toy plan validates, one test per fix | **pass**: 59 passed; `plan validate` ok against the user file and the template; 7 tests in `test_f1b.py` |
| adapter contract; claude, cursor, fake; missing tools reported | **pass**: `test_claude_args`, `test_cursor_args_and_pointer`, `test_missing_tools_report_no_adapter` |
| verdicts: broken verdict fixed by one repair call | **pass**: `test_broken_verdict_repaired_by_one_call`, `test_verdict_still_invalid_after_repair` |
| usage-limit sample triggers a cooldown | **pass** (synthetic sample): `test_limit_sample_triggers_cooldown`, `test_limit_without_reset_cools_one_hour` |
| proc timeout + tree kill -> `StopReason.timeout` | **pass**: `test_timeout_kills_and_maps_to_stop_reason` |
| secret-safe logging; ledger rows | **pass**: `test_call_writes_prompt_raw_and_ledger` (planted key redacted, no env in cmd log) |
| parsers pass on recorded samples | **pass on 8** (1 real, 7 synthetic); real smoke samples are picked up by the same test |
| samples table (profile, mode, ok, seconds, tokens/cost, verdict valid) | **pending HUMAN** `factory smoke`; dry run shows all 8 command lines |

#### Additions for F3
- First, after Amir's smoke: run `uv run pytest`; every new sample in `tests/samples/` must pass `test_recorded_samples`. Fix `CursorAdapter.parse_output` field names (session id for `--resume`) and the error shape to match; delete synthetic samples that a real one replaces (keep the limit ones). Record smoke answers to §12 in NOTES.
- If a cursor review edited `smoke.txt` ("REVIEWER WROTE"), `--mode ask` is not read-only: §6.5 then carries the guarantee alone.
- Every agent call goes through `adapters.call()` (prompt file, ledger, cooldown). `AgentResult.stop_reason()` gives `timeout` / `adapter_error`; `limit_hit` means stash partial work (§6.1) and take the next profile. "Failed twice" (§5 `adapter_error`) is the loop's retry, not the adapter's.
- Reviews: `call(..., schema=verdicts.schema(), rubric=verdicts.rubric_path(), budget_usd=plan.defaults.review_budget_usd[tier])`, then `verdicts.get_verdict(first, repair, adapter.caps.resume)`; invalid -> `adapter_error`. Gate steps: `merge_panel`, STATUS shows each verdict.
- Create `profiles.py`: move `profile_rows` there and add resolution (flag -> step override -> plan roles -> agents.yaml roles; expiry, cooldowns, family rule, `--swap`); none left -> `no_profile`.
- Caps: `ledger.cost(rows, step=)` against a step cap and `ledger.cost(rows)` against `run_budget_usd`. Implementer timeout = `defaults.timeout_min * 60`.
- After a committed step: write Current state from `verdict.current_state`, add the step's result/additions, then `notes.rotate_notes(notes)`.
- Still missing for F3: `templates/step_prompt.md` + `prompts.py` (§7.2), `checks.py`, `accept.py`, `gitops.py`, `factory lock/run/resume/approve/reject`. The toy accept scripts are still untested.
- (review 22 Oct, claude.ai) F1b + F2 verdict: **pass, pending smoke**. 59 tests green in the VM too. For F3: give the claude review mode `--disallowedTools "Edit,Write,NotebookEdit"` as well (flags back up the §6.5 guard, they don't replace it); check `--workspace` paths with the same shim-safe rule as the pointer; `plan validate` still prints "tiers" (wording only).
- (review 22 Oct, smoke) **8/8 smoke calls green**: every implement added the line, every review gave a valid `pass`, no reviewer wrote (`--mode ask` held). Claude reviews cost more than the $0.10 spec cap (opus $0.22, sonnet $0.14, first uncached call), so keep the 0.25 smoke cap and treat the §7.1 review budgets as realistic. Real Cursor JSON: `session_id` (parser already reads it) **and `usage` {inputTokens, outputTokens, cacheReadTokens, cacheWriteTokens}**, which §6.3 said Cursor lacks. Parse it into tokens_in/out and give Cursor models `prices` rows so the ledger gets a notional cost (needed for F6). Timing: grok implement 107 s vs composer 23 s for a one-line edit.


## H.3 `NOTES.md`: F3 result

#### F3 result
*Status: built 22 Oct 2026; the two real toy runs (HUMAN) are pending. Not committed.*

Built (`src/factory/`):
- `loop.py` `Runner`: per step `pending -> implementing -> checking -> accepting -> reviewing -> (fixing -> checking ...) -> passed -> gated -> approved -> committed -> done`; every transition saved. Acceptance failure -> fix loop with the failure table, no reviewer; review `fix` -> fix loop with `verdict.fixes`; `stop` -> `verdict_stop`. `run()` (stops at the first gate or stop; rc 1 on a stop), `approve` (commit, continue), `reject` (note = fix list, one extra loop past the cap), `resume` (stopped -> checking, so lock and scope are re-checked; a step stopped before it started goes back to pending).
- Implementer: usage limit -> `git stash push -u -m "factory: <step> interrupted (<profile>)"`, profile excluded for the step, next profile starts from a clean tree with the plain step prompt; other failure retried once, then `adapter_error`; timeout -> `timeout`. Reviewer: limit -> next reviewer; failure retried once; invalid verdict after the repair call -> `adapter_error`; §6.5 fingerprint (porcelain + diff + untracked contents) before/after each review incl. repair -> stash `factory: reviewer edits <profile>` + `reviewer_wrote`. Budgets checked before and after every call (`budget_exceeded`).
- `profiles.py` (moved `profile_rows` here; doctor re-exports): `Resolver` with precedence flag -> step override -> plan roles -> agents.yaml roles, `--swap` swaps the two lists (flags still win), availability (expiry, cooldown, doctor, adapter), family rule with logged same-family fallback, `panel()` on gate steps or `--panel`. Fake profiles count as installed.
- `checks.py` (lock incl. helper `.py` files next to the accept scripts; HEAD; scope = allowed_paths + STATUS/NOTES/NOTES-archive; secrets in added lines + untracked files), `accept.py` (last stdout line JSON, log per run, `VIRTUAL_ENV` stripped for the target's `uv run`), `gitops.py` (branch `factory/<step>` from current HEAD, so steps stack; commit; stash; diff stat incl. untracked), `prompts.py` + `templates/step_prompt.md` (§7.2 order; `Additions for <step>` read from NOTES).
- NOTES writer: after a commit, `Current state` = `verdict.current_state`, `<step> result` (profiles, loops, branch, acceptance table, review summary), `Additions for <next step>`, then `rotate_notes`. STATUS gains implementer and per-reviewer verdict columns plus the stop detail.
- CLI: `factory lock` (refuses when a lock exists and differs), `relock --note` (logs under `## Relocks` in NOTES), `run [--implementer P] [--reviewer P,Q] [--swap] [--panel] [--until-gate] [--force-step S]`, `resume`, `approve S`, `reject S --note`. Every loop command takes `--plan` and `--agents`. Run flags are saved in state.json, so resume/approve/reject keep them; a plain `run` resets them to the default roles.
- F2 review follow-ups: Claude review adds `--disallowedTools "Edit,Write,NotebookEdit"`; Cursor `--workspace` must match a shim-safe path pattern; Cursor `usage` parsed (tokens_in = input + cache read + cache write; `tokens_cache` priced with `cache_read`); `plan validate` says "roles used"; `examples/toy/.gitignore`.

Spec additions / deviations, with reasons:
- `defaults.step_budget_usd` (optional, None): §7.5 asks for a step cap, §4 has no field.
- The run budget counts ledger rows since the `factory run` started; resume/approve/reject continue that run's budget.
- `StepState` carries run data (branch, base_head, implementer, excluded, verdicts, merged verdict, fix list, accept JSON) so any command can continue from state.json alone.
- `--until-gate` is accepted but is the only behaviour (a run always stops at a gate).
- Tests are slow-ish (~100 s for test_f3: process spawns on Windows); `FACTORY_UV_E2E=1` adds one test of the real CLI path with `uv run` acceptance (no agents), green.

Acceptance (PLAN §9 F3, before HUMAN):
| check | result |
|---|---|
| state machine with fakes, every stop reason once | **pass**: `test_every_stop_reason` (11 reasons) + resume, relock, gate tests |
| resolution: expired, cooling, same-family skipped, swap, step override | **pass**: 3 tests (plus flags, plan roles, panel, same-family fallback) |
| panel merge rules | **pass**: `test_panel_merge` (F2) + `test_gate_panel_reject_then_approve` |
| toy with fakes reaches `done`, both steps committed on `factory/*` (default and `--swap`) | **pass**: `test_toy_end_to_end_default_roles`, `_swap` |
| planted scope violation / acceptance-script edit / reviewer write stop the run | **pass**: `scope_violation`, `lock_mismatch`, `reviewer_wrote` cases |
| `factory cost --by profile` prints the ledger totals | **pass** (in the default-roles e2e test) |
| toy for real, default roles; then `--swap` | **pending HUMAN** |


## H.4 Workflow reference (`agentic-dev-workflow.md` §3–§5: token playbook, review rubric, factory sketch)

#### 3. Token optimisation playbook

##### 3.1 Route the model by task type

| Task type | Examples | Model class | Why |
|---|---|---|---|
| Design-sensitive, not fully testable | Fixture or test design, ground truth and labels, graph and state, evaluation harness | Strong (current Grok, Opus-class) | Mistakes are silent and expensive |
| Mechanical, with executable acceptance | UI wiring, refactors, tests for a written spec, docs and README drafting, corpus drafting | Cheap and fast (e.g. Cursor Composer) | Tests catch mistakes; retries are cheap |
| Review at a design gate | Spec lock, data and label design, eval design, pre-submission | Opus | This is where the catches in §4 came from |
| Routine review | Mechanical steps with green acceptance | Sonnet, or an acceptance summary alone | Low risk |

A cheaper implementer only saves money if it doesn't trigger more fix loops. On long, design-heavy steps, retries eat the savings.

##### 3.2 Context hygiene (rules to put in every project's `AGENTS.md`)

1. **One fresh chat per numbered prompt.** State lives in files.
2. **Never read big generated artifacts whole.** Query them: `jq` with a limit, `duckdb` queries, or a harvested metadata table.
3. **Quiet output:**
   - `pytest -q`;
   - send dbt and other build logs to a file and show only the summary line and errors;
   - truncate tool results in traces.
4. **Point at sections, not whole documents:** "PLAN §6, §8".
5. **Keep NOTES.md short.** Hold the current state, open questions and the latest review there; move old acceptance logs to `NOTES-archive.md`, which is read only on demand.
6. **Put stable instructions first** (AGENTS.md, spec) and the changing parts last. That helps prompt caching on both tools.

##### 3.3 Executable acceptance

Give each step a `scripts/accept_pN.py` that runs the checks and prints a compact PASS/FAIL table, about 20 lines. Then the implementer, the reviewer and any future orchestrator all read the same short summary instead of long logs.

##### 3.4 Review economy

- **The reviewer reads:** the acceptance summary, `git diff --stat`, then only the files the diff points to.
- **Spend review effort at design gates** (§3.1). For mechanical steps a green acceptance is enough.
- **Review findings and the next step's additions go into NOTES**, so the next implementer prompt can stay short.

##### 3.5 Scripted runs (Claude Code)

- `--output-format json` returns `total_cost_usd`; log it for every run.
- `--max-budget-usd` caps a run.
- `--bare` skips hooks, plugins, `CLAUDE.md` and auto-memory. That makes runs reproducible and cheaper to start, but they need `ANTHROPIC_API_KEY` (no subscription login). Pass context with `--append-system-prompt-file`.

##### 3.6 Price reference (re-check before relying on it)

| Model | Input $/MTok | Output $/MTok | Source, date |
|---|---:|---:|---|
| Claude Fable 5.1 | 10 | 50 | Anthropic pricing page, 20 Oct 2026 |
| Claude Opus 5.5 | 4 | 20 | same |
| Claude Sonnet 5.5 | 2 | 10 | same |
| Claude Haiku 4.5 | 1 | 5 | same (Batch API: 50% off all of these) |
| Cursor Composer 2 (Standard) | 0.50 | 2.50 | Vantage write-up (benchmarks are Cursor's own) |
| Cursor Composer 2 (Fast, the Cursor default) | 1.50 | 7.50 | same |

Cursor plan usage (including Grok) is a quota, not a per-token bill. The question there is how fast the pool is used up.

---

#### 4. Review rubric: questions that caught real problems

Use these at every design gate. Each one caught something in Sprint 4.

1. **Could a naive heuristic pass the evaluation?** The decoys first sat outside the failure path, so "blame the nearest changed model" was never fooled. Error-level staging tests turned every incident into "the source next door did it".
2. **Does anything the agent can read reveal the answer?** Explanatory SQL comments in injected patches ("...cross-joined and left at -1..."); "Reformatted only" on decoys; runtime code able to open `labels.json` or the specs.
3. **Does the test data exercise the claimed capability?** Shallow lineage with dead-end models; a "schema drift" class that was really a code change.
4. **Are time-dependent values pinned?** Freshness was compared with `now()`, so every incident built a day later would have looked stale. Fixed with a per-run `as_of`.
5. **Do the tools expose the evidence a human would use?** `read_node` showed declared columns, not the warehouse's, so a rename looked backwards.
6. **Is ground truth independent of model output?** Never relabel from model answers. Freeze the holdout before any prompt work.
7. **Is the taxonomy unambiguous?** "A stale source that was already stale" can be argued either way, so it was replaced.
8. **Does the feature claimed for grading actually run in real traces?** Agentic RAG passed its tests, but the agent never called search in six real runs.
9. **Do the acceptance criteria contradict each other?** Two did in Sprint 4 P3, and the implementer resolved them sensibly. Read acceptance criteria as carefully as code.

**Reuse:** this rubric is the system prompt of the automated reviewer in §5.

---

#### 5. The code factory

##### 5.1 Stages and human gates

```
spec (human gate) → implement → acceptance script → review (rubric §4)
      ↑                                              │
      └──────── fix list (≤ 2 loops) ←─────── fix ───┤
                                                     ├─ pass → commit → next step
                                                     └─ stop → human
```

**Human gates that stay manual:**
- the spec lock;
- anything that defines ground truth (fixtures, labels, evaluation metrics);
- release or submission.

Automate the steps between gates.

##### 5.2 Tooling (headless modes)

- **Cursor CLI:**
  - `agent -p "<prompt>" --force --output-format json`. Without `--force` it only proposes changes.
  - Use `CURSOR_API_KEY` for CI.
  - A model flag isn't documented on the headless page; check `agent --help`.
- **Claude Code:**
  - `claude -p "<prompt>" --output-format json --json-schema '<verdict schema>' --allowedTools "Read,Bash(git diff *),Bash(uv run *)" --permission-mode acceptEdits --max-budget-usd 2`.
  - `--resume <session_id>` continues a session.
  - The Agent SDK (Python or TypeScript) gives the same loop with callbacks.

##### 5.3 Orchestrator sketch

```
for step in plan.steps:                       # P0..Pn, each with prompt + acceptance script + gate flag
    git switch -c factory/<step>
    implementer(step.prompt + NOTES additions)          # agent -p ... --force
    summary = run(scripts/accept_<step>.py)             # compact PASS/FAIL JSON
    verdict = reviewer(rubric, git diff, summary)       # claude -p ... --json-schema verdict
    loops = 0
    while verdict.verdict == "fix" and loops < 2:
        implementer(verdict.fixes); summary = run(...); verdict = reviewer(...); loops += 1
    if verdict.verdict == "pass" and not step.human_gate: commit; continue
    stop and notify the human (verdict, summary, diff stat)
```

**Verdict schema:**

```json
{"verdict": "pass|fix|stop",
 "fixes": [{"file": "...", "problem": "...", "change": "..."}],
 "rubric": {"q1": "ok | issue: ...", "...": "..."},
 "additions_for_next_step": "..."}
```

##### 5.4 Guardrails

- A budget cap per run (`--max-budget-usd`) and per step.
- At most 2 fix loops.
- A fresh session per step.
- A branch per step; commit only on pass.
- The reviewer gets read-only tools plus `git diff`.
- The implementer never commits.
- Secrets stay in the environment and are never read by agents.
- Log the cost of every run.

##### 5.5 Risks

- **Spec ambiguity spreads.** The fix is a strong spec gate.
- **Tests can pass while behaviour is wrong.** Rubric questions 1, 3 and 8 exist for this.
- **Implementer and reviewer can agree on the wrong thing.** Use different model families, a rubric-driven review, and human gates.
- **Context drift in long runs.** Use fresh sessions and short NOTES.
- **Windows quirks:** DuckDB file locks, CRLF, PowerShell quoting. Test the orchestrator on one step first.

##### 5.6 Build plan (after the Sprint 4 submission)

1. **Acceptance scripts** for an existing step (retrofit Sprint 4 P4 as a template).
2. **Reviewer-only automation:** headless Claude with the rubric and the verdict schema, run on a recorded step.
3. **Implementer automation** for one mechanical step.
4. **The orchestrator loop** with gates, used on the next governor module: governed questions (NL→SQL on the same metadata store).

---


## H.5 Factory spec (`PLAN.md`, source of truth since F0)

### Code factory: build spec, and its first job (governor-ask)

*Started 21 Oct 2026.*

- **Source:** `C:\Users\amir0\Turing College\_knowledge\factory-build-spec.md`.
- **Mirror:** the Project doc `claude/factory-build-spec.md`.
- **After F0:** this spec is copied into the factory repo as `PLAN.md`, and that copy becomes the source of truth.

**Companion:** `agentic-dev-workflow.md` (§3 token playbook, §4 review rubric, §5 factory sketch). This spec turns that §5 into a build plan.

---

#### 0. How to use this document

1. **F0–F2 can start now.** They touch only the new factory folder, never the Turing College sprint folders.
2. **F0:** start a fresh chat in the Turing College Project and paste prompt §13.1.
3. **Every later phase:** a fresh chat with prompt §13.2 and the phase number. State lives in the repo's `NOTES.md` and `STATUS.md`, not in the chat.
4. **After Sprint 4 is submitted:**
   - spec the first target with Claude (§13.3);
   - run the factory on it (§13.4).

---

#### 1. What this is called

- **The pattern:** an *evaluator–optimizer workflow*, Anthropic's term in "Building effective agents". One model produces work, another evaluates it and sends feedback, in a loop.
  - With humans at fixed gates, it is usually called a *human-in-the-loop coding pipeline* or a *code factory*.
  - A *dark factory* is the fully unattended version. That is not the goal here.
- **Our name:** *factory*.
- **Roles:**
  - *implementer:* writes the code;
  - *reviewer:* judges it and returns a verdict;
  - *orchestrator:* our Python;
  - *gatekeeper:* Amir.
- **Roles are not tools.** Implementer and reviewer are roles, and any agent profile can play either (§6). A profile is a tool (Claude Code, Cursor, Gemini CLI, Codex CLI), an account and a model. "Claude Opus implements, Cursor Grok reviews" and the reverse are both one-line config changes, or one command-line flag.

---

#### 2. Locked decisions

| # | Decision | Why |
|---|---|---|
| D1 | The orchestrator is Python 3.12 + uv, a plain CLI (`factory …`). It runs on Amir's Windows machine in PowerShell. No agent framework. | The loop is a small state machine. A framework adds tokens and debugging surface without adding value. |
| D2 | Every CLI agent sits behind one adapter contract with two modes, `implement` (can write) and `review` (read-only). Claude Code and Cursor adapters come first, Gemini CLI and Codex CLI when installed, plus a fake for tests. | Amir has several subscriptions and wants to compare them. The contract keeps the loop identical whichever agent plays a role. |
| D3 | Roles are bound to *profiles* (tool + account + model + family) through fallback lists. Plan steps and command-line flags can override them. | Switching who implements and who reviews must take seconds, not code changes. |
| D3a | By default the reviewer is a different model family from the implementer. A same-family pairing is allowed only when explicit, and it is logged. | Lowers the risk that both agree on the wrong thing (workflow doc §5.5). |
| D3b | Accounts are first-class. Each Claude Code account has its own config directory (`CLAUDE_CONFIG_DIR`). A profile can expire (`active_until`) and cool down after a usage limit. | The Turing College Claude account runs out in about 3 weeks; it should be used first and then fall away without breaking runs. |
| D4 | Acceptance scripts are written at spec time, reviewed by Amir and hash-locked. The implementer cannot change them. | Executable acceptance is the cheapest reviewer. Locking stops "make the test pass by editing the test". |
| D5 | The reviewer runs only when acceptance passes. | Don't pay a model to read failing work: the failure table is the fix list. |
| D6 | Each step starts a fresh session. Within a step, fix loops resume the implementer's session if the CLI supports it. | Fresh sessions keep context small across steps. Resuming within a step reuses warm context instead of re-reading files. |
| D7 | The implementer never commits. The orchestrator commits to `factory/<step>` branches when a step passes, and Amir merges. | Same rule as the course repo. Every step becomes one reviewable diff. |
| D8 | State lives in files: `plan.yaml`, `.factory/` (runs, ledger, lock), `NOTES.md`, `STATUS.md`. | Any chat can pick up cheaply from `STATUS.md`. Nothing depends on chat memory. |
| D9 | There are human gates at the spec lock, at ground-truth steps, at security-sensitive steps and at release. Everything else runs unattended, with up to 2 fix loops. | Workflow doc §5.1. |
| D10 | Secrets come only from the Windows user environment. Agents are denied `.env*`, and the diff is scanned for key patterns before every commit. | Keys pasted into a chat are the reminder that this can happen. |

---

#### 3. Architecture

```
plan.yaml + plan/prompts/ + plan/accept/ ──factory lock──► .factory/lock.json
        │
factory run ──► for each step:
   build the prompt file (stable prefix → step → additions → fixes)
   resolve the implementer profile (override → step → tier list; skip expired / cooling / unavailable)
   implementer adapter in implement mode (claude | cursor | gemini | codex | fake)
   deterministic checks: lock hash · HEAD unchanged · scope guard · secret scan
   acceptance script (JSON summary, ≤ 30 lines)
      fail → fix loop (≤ 2) with the failure table, no reviewer
      pass → resolve the reviewer profile(s) (cross-family by default; a panel on HUMAN-gate steps)
             reviewer adapter in review mode → verdict JSON, validated; working tree must be unchanged
              fix  → fix loop (≤ 2)
              stop → STOPPED, STATUS.md written, exit non-zero
              pass → human gate? → wait for approve / reject
                     commit to factory/<step> → NOTES + STATUS + ledger → next step
```

**Package layout:**

```
factory/
  pyproject.toml            # [project.scripts] factory = "factory.cli:main"
  src/factory/
    cli.py                  # run, status, approve, reject, resume, lock, relock, cost, doctor, smoke, calibrate, profiles, bakeoff
    config.py  plan.py      # pydantic models for plan.yaml and agents.yaml
    profiles.py             # profile resolution: overrides, fallback lists, expiry, cooldowns, family rule
    state.py                # per-step state machine, persisted in .factory/state.json
    prompts.py              # prompt assembly (§7.2)
    adapters/ base.py claude.py cursor.py gemini.py codex.py fake.py
    verdicts.py             # verdict extraction: native schema, else fenced JSON; validation; one repair retry
    limits.py               # usage-limit detection per tool, cooldown store
    checks.py               # lock, scope, secrets, HEAD
    accept.py               # runs acceptance, parses the JSON line
    review.py               # verdict schema, rubric
    notes.py                # NOTES writer and rotation, STATUS.md
    ledger.py               # cost and time ledger (CSV)
    gitops.py               # branch, commit, diffstat
    proc.py                 # subprocess with timeout and Windows process-tree kill
  templates/                # AGENTS.md, rubric.md, verdict.schema.json, step_prompt.md
  examples/toy/             # 2-step toy plan for end-to-end tests
  examples/smoke/           # scratch repo for real CLI smoke calls
  calibration/              # small repos with planted flaws (F4)
  tests/
```

---

#### 4. Plan format

**`plan.yaml`:**

```yaml
project: governor
notes: NOTES.md
agents: AGENTS.md
defaults:
  max_fix_loops: 2
  timeout_min: 40
  run_budget_usd: 15          # cap on reported or notional cost for one `factory run`
roles:                         # optional; overrides the role lists in agents.yaml (§6.1) for this repo only
  design:     {implementer: [claude-tc-opus, claude-me-opus, cursor-grok], reviewer: [cursor-grok, gemini-pro]}
steps:
  - id: G1
    title: Repo, fixture and metadata store
    tier: mechanical
    prompt: plan/prompts/G1.md
    accept: plan/accept/accept_g1.py
    allowed_paths: [src/governor/meta/, fixture/, tests/, pyproject.toml, uv.lock]
    human_gate: false
    review_focus: "copied code keeps provenance; no Sprint 4 paths hard-coded"
    # optional per-step overrides:
    # implementer: cursor-composer
    # reviewer: [claude-tc-sonnet]
```

Precedence for choosing a profile: command-line flag → step override → `plan.yaml` roles → `agents.yaml` roles.

**Step prompt (`plan/prompts/Gn.md`), at most 60 lines:**
- what to build, and the constraints;
- the files or sections to read, by name;
- "Done when `plan/accept/accept_gn.py` passes".

Never write "read PLAN.md".

**Acceptance contract:**
- `uv run python plan/accept/accept_gn.py` exits 0 on pass and 1 on fail.
- The last stdout line is JSON: `{"step":"G1","pass":true,"checks":[{"name":"pytest","ok":true,"detail":"42 passed"}]}`.
- Everything else printed is 30 lines or fewer. Long logs go to `.factory/runs/<run>/<step>/logs/`.
- Checks are deterministic only: tests, file existence, schema checks, and small evaluations with a fixed seed. No LLM calls, unless the step is an evaluation step and the plan gives it a budget.

---

#### 5. The loop

**States.** Each step moves through `pending → implementing → checking → accepting → reviewing → (fixing → checking → …) ×≤2 → passed → gated → approved → committed → done`, or ends in `stopped(reason)`.
- The state is saved after every transition, and `factory resume` continues from it.
- Re-running a finished step needs `--force-step`.

**Stop reasons.** Each one writes `STATUS.md` and exits non-zero:

| Reason | Trigger |
|---|---|
| `verdict_stop` | The reviewer returned `stop`. |
| `loops_exhausted` | The fix loops ran out. |
| `budget_exceeded` | A step or run budget was exceeded. |
| `lock_mismatch` | The plan, a step prompt or an acceptance script changed since `factory lock`. |
| `scope_violation` | A changed path is outside `allowed_paths` plus `NOTES.md`. |
| `secret_in_diff` | The diff contains a key pattern. |
| `implementer_committed` | HEAD moved. |
| `adapter_error` | An adapter failed twice, or a verdict was still invalid after the repair call. |
| `reviewer_wrote` | The working tree changed during a review (§6.5). |
| `no_profile` | Every profile in a role's list is expired, cooling down or unavailable. |
| `timeout` | The implementer ran past its timeout. |

**Human commands:**
- `factory status`: the step table, also written to `STATUS.md`.
- `factory approve G2`: commit and continue.
- `factory reject G2 --note "…"`: the note becomes the fix list for one more loop.
- `factory resume`: continue after Amir has fixed something by hand. It re-checks the lock and the scope.
- `factory relock --note "…"`: a human-only spec change, logged in `NOTES.md`.
- `factory cost [--by step|role|model]`.

---

#### 6. Agents: profiles, accounts and adapters

##### 6.1 Profiles and accounts (`%USERPROFILE%\.factory\agents.yaml`)

Profiles describe Amir's machine and accounts, so they live in the user folder rather than in any repo. A plan names profiles and never names tools directly.

```yaml
accounts:
  claude:
    turing:   {env: {CLAUDE_CONFIG_DIR: "%USERPROFILE%\\.claude-turing"}}   # college account, logged in once (F0)
    personal: {env: {CLAUDE_CONFIG_DIR: "%USERPROFILE%\\.claude"}}          # or the other way round; F0 asks
profiles:
  claude-tc-opus:   {tool: claude, account: turing,   model: opus,   family: anthropic, active_until: 2026-11-11}  # confirm the date
  claude-tc-sonnet: {tool: claude, account: turing,   model: sonnet, family: anthropic, active_until: 2026-11-11}
  claude-me-opus:   {tool: claude, account: personal, model: opus,   family: anthropic}
  claude-me-sonnet: {tool: claude, account: personal, model: sonnet, family: anthropic}
  cursor-grok:      {tool: cursor, model: "<id from agent models>", family: xai}
  cursor-composer:  {tool: cursor, model: "<id from agent models>", family: cursor}
  gemini-pro:       {tool: gemini, model: "<id from gemini --help>", family: google}
  codex-gpt:        {tool: codex,  model: "<id>", family: openai, enabled: false}     # when Amir gets Codex
roles:                     # first available wins
  design:     {implementer: [claude-tc-opus, claude-me-opus, cursor-grok],      reviewer: [cursor-grok, gemini-pro, claude-me-opus]}
  mechanical: {implementer: [cursor-composer, claude-tc-sonnet],               reviewer: [claude-tc-sonnet, claude-me-sonnet, gemini-pro]}
  gate_panel: [cursor-grok, gemini-pro]   # extra reviewers on HUMAN-gate steps
prices:                    # API-equivalent $/MTok, used only for the notional cost of tools that report tokens but not cost
  google/<model>: {in: 0, out: 0}
```

**A profile is available when all of these hold:**
- it is enabled;
- today is on or before `active_until`;
- it is not cooling down after a usage limit;
- doctor saw its tool installed and logged in;
- for a reviewer: it is not in the implementer's family, unless `allow_same_family: true` is set or no other reviewer is available. Using a same-family reviewer is logged.

**Switching** takes one flag or one line:
- `factory run --implementer claude-tc-opus --reviewer cursor-grok`;
- `factory run --swap`, which uses the first available reviewer as implementer and the first available implementer as reviewer;
- a step override in `plan.yaml`;
- editing `roles` in `agents.yaml`.

**Usage limits:**
- Each adapter recognises its tool's limit messages and exit codes and returns `limit_hit` with the reset time when the tool reports one.
- The profile cools down until then, or for 1 hour if no time is given. Cooldowns are stored in `%USERPROFILE%\.factory\cooldowns.json`.
- The step retries with the next profile in the list.
- If an implementer is cut off mid-step, its partial work is saved with `git stash push -u -m "factory: <step> interrupted (<profile>)"`, and the next profile starts the step from a clean tree. Nothing is deleted.

**Claude accounts.** Each account has its own config directory, and credentials live in that folder's `.credentials.json`.
- **One-time login for the second account** (F0, HUMAN):

  ```powershell
  $env:CLAUDE_CONFIG_DIR = "$HOME\.claude-turing"
  claude
  ```

  Then run `/login` with the college account and close the session.
- **Side effect:** a fresh config folder has no user `CLAUDE.md` and no memory, which is what headless factory runs should have anyway.

**`factory profiles`** prints one row per profile: tool, account, model, family, availability, and the reason when a profile is unavailable.

##### 6.2 Adapter contract (`adapters/base.py`)

```python
class Caps:            # declared per tool, confirmed at F0/F2
    json_output: bool; schema_output: bool; reports_cost: bool; reports_tokens: bool
    resume: bool; read_only_mode: bool

class AgentResult:
    ok: bool; text: str; structured: dict | None; session_id: str | None
    seconds: float; tokens_in: int | None; tokens_out: int | None
    cost_usd: float | None; limit_hit: bool; reset_at: str | None; error: str | None; raw_path: Path

def run(mode: Literal["implement", "review"], prompt_file: Path, workdir: Path, model: str,
        env: dict, schema: dict | None, budget_usd: float | None, timeout_s: int,
        resume_id: str | None) -> AgentResult
```

**Shared rules for every adapter:**
- **Short command lines.** The prompt goes to a file under `.factory/runs/<run>/<step>/`. The command line carries only a short pointer ("Read `<file>` and do the task in it."), or the file is fed on stdin where the tool supports it. This avoids Windows' 32k command-line limit and PowerShell quoting.
- **Executables:** resolve them with `shutil.which` (Windows shims are `.cmd` or `.exe`) and call `subprocess.run([...], shell=False, encoding="utf-8", timeout=…)`.
- **Timeouts:** kill the whole process tree (`taskkill /T /F /PID <pid>`).
- **Logging:** store the raw output at `raw_path`. Never log environment variables.
- **Per-call environment:** the profile's account variables (such as `CLAUDE_CONFIG_DIR`) apply to that call only.

##### 6.3 The tools

The flags below are the documented ones as of Oct 2026. F0 saves each tool's `--help` and confirms them, and differences go into NOTES. Anything not yet confirmed is listed in §12.

| Tool | implement mode | review mode | Structured verdict | Usage it reports |
|---|---|---|---|---|
| **Claude Code** `claude -p` | `--permission-mode acceptEdits`; `--allowedTools "Read,Edit,Write,Grep,Glob,Bash(uv run:*),Bash(git status:*),Bash(git diff:*)"` | `--allowedTools "Read,Grep,Glob,Bash(git diff:*),Bash(git log:*)"` | native: `--json-schema`, read from `structured_output` | `total_cost_usd`, `num_turns`, `session_id` |
| **Cursor** `agent -p` | `--force --trust` | no `--force`, so changes are only proposed; `--mode ask` if the installed version has it | fenced JSON in the final message | none: seconds only (cost from the Cursor usage page) |
| **Gemini CLI** `gemini` | an auto-approve mode (`--approval-mode` or `--yolo`; confirm) | default approval mode, so writes are refused in headless runs (confirm) | fenced JSON in `response` | `stats` tokens |
| **Codex CLI** `codex exec` | `--sandbox workspace-write` (with `--full-auto` if needed) | `--sandbox read-only` | native: `--output-schema <file>`, `-o <file>` | from `--json` events (confirm fields) |
| **Fake** | applies a recorded patch | returns a canned verdict | native | canned |

**Common command shapes:**

```
claude -p --model opus --output-format json [--json-schema "<schema>"] [--append-system-prompt-file .factory/rubric.md] --max-budget-usd <b> < prompt.md
agent -p --output-format json --model <id> --workspace <repo> [--force --trust] "Read <prompt file> and do the task in it. Do not commit."
gemini --output-format json -m <id> [approval flag] "Read <prompt file> and do the task in it."
codex exec --json -m <id> --sandbox <mode> [--output-schema verdict.schema.json -o verdict.json] - < prompt.md
```

**Notes:**
- `claude --bare` is faster and reproducible, but needs `ANTHROPIC_API_KEY` instead of a subscription login. It is a per-profile switch, off by default.
- F2 records one real JSON sample per tool and mode and pins each parser to it. Session ids for resume and the error shapes must be confirmed, not assumed.

##### 6.4 Verdicts from any reviewer (`verdicts.py`)

1. **Get the verdict JSON.** Use the native schema output where the tool has it (Claude, Codex). Otherwise use the last fenced ```` ```json ```` block of the final message. The review prompt tells every reviewer to end with exactly one such block.
2. **Validate it with pydantic** against `templates/verdict.schema.json`.
3. **If it is invalid,** make one repair call: "Return only the verdict JSON, valid against this schema", resuming the session where the tool supports it. If the repair also fails, stop with `adapter_error`.

**Panel** (HUMAN-gate steps, or `--panel`): every available `gate_panel` reviewer that isn't in the implementer's family also reviews. The verdicts are merged:
- `stop` if any reviewer says stop;
- else `fix` if any says fix, with the fixes combined and duplicates removed;
- else `pass`.

`STATUS.md` shows each reviewer's verdict separately, which is also raw material for the agent comparison (F4, F6).

**Verdict schema** (`templates/verdict.schema.json`):

```json
{"type":"object",
 "required":["verdict","summary","fixes","rubric","additions_for_next_step","current_state"],
 "properties":{
  "verdict":{"enum":["pass","fix","stop"]},
  "summary":{"type":"string","maxLength":600},
  "fixes":{"type":"array","items":{"type":"object","required":["file","problem","change"],
     "properties":{"file":{"type":"string"},"problem":{"type":"string"},"change":{"type":"string"}}}},
  "rubric":{"type":"object","additionalProperties":{"type":"string"}},
  "additions_for_next_step":{"type":"string","maxLength":1500},
  "current_state":{"type":"string","maxLength":1200},
  "notes_for_human":{"type":"string","maxLength":600}}}
```

**Rubric** (`templates/rubric.md`): the 9 questions from workflow doc §4, plus the step's `review_focus`, plus one closing instruction: "Say `stop` when the problem is in the spec or the acceptance script, not in the code." Tools without a system-prompt flag get the rubric at the top of the prompt file. It is still the stable prefix.

##### 6.5 Read-only reviewers, enforced by the orchestrator

Tool flags are not trusted alone. Before a review, the orchestrator records a hash of `git status --porcelain` together with the diff. After the review, it records the same hash again. If anything changed, the reviewer's edits are stashed (`factory: reviewer edits <profile>`), the verdict is discarded, and the step stops with `reviewer_wrote`.

---

#### 7. Token and cost rules (built into the code, not left to discipline)

##### 7.1 Model routing

Routing is the `roles` block in `agents.yaml` (§6.1). The default while the Turing College Claude account is active, until about 11 Nov 2026:

| Work | Implementer (first available) | Reviewer (first available, other family) | Budget per review |
|---|---|---|---|
| **Design tier:** ground truth, eval harness, graph and state, security | `claude-tc-opus` → `claude-me-opus` → `cursor-grok` | `cursor-grok` → `gemini-pro` → `claude-me-opus` | $2.00 |
| **Mechanical tier:** UI, code to a written spec, refactors, docs | `cursor-composer` → `claude-tc-sonnet` | `claude-tc-sonnet` → `claude-me-sonnet` → `gemini-pro` | $0.75 |
| **Human-gate steps** | as the tier | the tier's reviewer plus the `gate_panel` (§6.4), then Amir | — |

**Why this default:**
- It uses the college account hardest while it exists, for the most token-heavy role (implementing design steps).
- It keeps the reviewer in a different family.
- It spends the cheap Cursor quota on mechanical work.

When the college account expires, the same lists fall through to the personal account and Cursor with no edits.

**Swapping** (for example, Grok implements and Opus reviews) is `--swap` for one run, or a reorder of the lists. Experiments F4 and F6 decide what the long-term default should be.

##### 7.2 Prompt assembly (stable parts first, for prompt caching)

1. **Fixed header** from `templates/step_prompt.md`: "AGENTS.md applies", the never-read list, and output rules (quiet commands, paste summaries).
2. **The step prompt.**
3. **`Additions for <step>`** from `NOTES.md`, written by the previous step's reviewer.
4. **Fix list**, from loop 1 on only: the acceptance failure table or `verdict.fixes`, plus Amir's reject note.

Nothing else goes in: no whole PLAN, no NOTES history, no chat transcript.

**The reviewer's prompt** contains:
- step id, title and `review_focus`;
- the acceptance JSON;
- `git diff --stat`;
- the list of changed files.

The rubric is the system prompt, which stays stable. The reviewer opens only the changed files it needs.

##### 7.3 Context hygiene in target repos (the factory writes this into `AGENTS.md` at init)

- **Never read whole:**
  - lockfiles;
  - `manifest.json`, `catalog.json` and `run_results.json`;
  - `*.duckdb`;
  - `.factory/` and `NOTES-archive.md`;
  - any data file over 200 KB.

  Query them instead (jq or duckdb, with `LIMIT`).
- **Quiet commands:** `pytest -q`, build logs to a file, print summaries only.
- **Paste results, not logs.**

##### 7.4 NOTES rotation (deterministic, no LLM)

After each committed step, `NOTES.md` keeps:
- `Current state`, from `verdict.current_state`;
- `Open questions`;
- the result, review and additions of the last two steps.

Older sections move to `NOTES-archive.md`. Target: `NOTES.md` under 150 lines.

##### 7.5 Ledger and budgets

- **Ledger:** `.factory/ledger.csv` has one row per agent call:
  - `ts, step, loop, role, profile, tool, account, model, seconds, turns, outcome`;
  - `tokens_in, tokens_out`, when the tool reports them;
  - `cost_usd`, when the tool reports it (Claude);
  - `cost_notional_usd`, computed from tokens with the `prices` table (Gemini, Codex);
  - nothing for Cursor beyond seconds.
- **Subscriptions.** Every account here is a subscription, so reported cost is notional: it shows API-equivalent spend and lets runs be compared, not money leaving the account.
- **Caps:** one per step and one per run, on reported plus notional cost. Exceeding either stops with `budget_exceeded`.
- **Report:** `factory cost` prints the totals.
- **Cursor usage:** checked by Amir on the Cursor usage page. The ledger's seconds and call counts per step let the two be matched.

---

#### 8. Guardrails

- **Lock.** `factory lock` writes the sha256 of `plan.yaml`, the step prompts and the acceptance scripts to `.factory/lock.json`. A run refuses to start or continue on a mismatch.
- **Deterministic checks before acceptance.**
  - Scope guard.
  - HEAD-unchanged check.
  - Secret scan of added lines. Patterns:
    - `sk-`, `sk-lf-`, `pk-lf-`;
    - `AKIA[0-9A-Z]{16}`;
    - `-----BEGIN`;
    - `OPENROUTER_API_KEY=`;
    - strings of 40+ high-entropy characters.
- **Secrets denied to agents.**
  - In target repos, `.claude/settings.json` denies `Read(./.env)` and `Read(./.env.*)`.
  - `AGENTS.md` gives Cursor the same rule.
  - Cursor CLI permission rules, if the installed version supports them, deny `git commit`, `git push` and deletes outside the repo.
- **Branches.** One branch per step. `main` changes only when Amir merges.
- **Windows.**
  - `.gitattributes`: `* text=auto eol=lf`.
  - Acceptance scripts close their DuckDB connections.
  - Only one factory run per repo at a time (`.factory/run.lock`).

---

#### 9. Factory build phases

Each phase ends with its acceptance, a "Fn result" and an "Additions for Fn+1" section in the factory repo's `NOTES.md`, an updated `STATUS.md`, and a stop.

##### F0: Setup and doctor (ends with a HUMAN step)

- **Repo.**
  - Ask Amir once for the parent folder (default `C:\Users\amir0\portfolio`). Create `factory/` in it.
  - Set up: a uv project, `git init`, `.gitignore` (`.factory/`, `.venv/`) and `.gitattributes`.
  - Add `AGENTS.md` (rules and the never-read list), `PLAN.md` (this spec), `NOTES.md` and `STATUS.md`.
- **Accounts.** Write `%USERPROFILE%\.factory\agents.yaml` from the template in §6.1. Ask Amir which Claude account is logged in at `~\.claude` today, and what date the college account ends.
- **`factory doctor`.**
  - Reports the versions of python, uv, git, and each agent tool that is installed: `claude`, `agent`, `gemini`, `codex`.
  - Saves each tool's `--help`, plus `agent models`, to `.factory/doctor/`.
  - Checks each profile's login (per Claude account, with that account's `CLAUDE_CONFIG_DIR`), without printing tokens.
  - Prints the `factory profiles` table.
- **HUMAN.**
  - Amir installs any missing CLIs.
    - Cursor: `irm 'https://cursor.com/install?win32=true' | iex`.
    - Gemini CLI and Codex CLI are optional. Install them with each tool's official instructions.
  - He logs the second Claude account into its own config folder (§6.1).
  - He runs `uv run factory doctor` in PowerShell.
- **Accept:**
  - Every profile is available, or has a named reason why not.
  - Every flag in §6.3 is checked against the saved help output, and any differences are listed in NOTES.
  - The model ids in `agents.yaml` are filled in from the saved model lists.

##### F1: Core

- **Build:** config and plan models, `factory plan validate`, the state machine with persistence, the ledger, run directories, and `status` with `STATUS.md`.
- **Tests:**
  - invalid plans are rejected with clear messages;
  - state survives a restart;
  - status renders.
- **Accept:** `pytest -q` is green, and `factory plan validate examples/toy/plan.yaml` passes.

##### F2: Adapters

- **Build:**
  - the adapter contract (§6.2) with claude, cursor and fake adapters first;
  - gemini and codex adapters for whatever is installed. A missing tool gets an adapter that reports "not installed" in `factory profiles`;
  - `verdicts.py` (§6.4) and `limits.py` (limit detection; cooldowns);
  - prompt-file passing;
  - `proc.py` with timeout and tree kill;
  - parsers pinned to real samples;
  - secret-safe logging.
- **Tests:** with fakes and with the recorded samples, including a broken verdict that the repair call fixes and a usage-limit sample that triggers a cooldown.
- **HUMAN.** `factory smoke` in PowerShell makes two tiny real calls per available profile in `examples/smoke`:
  - an implement call that adds one line to a file;
  - a review call that must return a valid verdict.

  Claude is capped at $0.10 per call. The samples are saved to `tests/samples/<tool>/`.
- **Accept:** a samples table (profile, mode, ok, seconds, tokens/cost, verdict valid), parsers that pass on the samples, and ledger rows.

##### F3: The loop

- **Build:**
  - lock, checks, the acceptance runner, review, fix loops, gates, git operations, the NOTES writer and rotation;
  - `approve`, `reject`, `resume` and `relock`;
  - profile resolution (`profiles.py`): precedence, fallback, expiry, cooldown, the family rule, `--implementer`, `--reviewer`, `--swap` and `--panel`;
  - the read-only review guard (§6.5);
  - the stash-and-switch for an implementer cut off mid-step.
- **Tests** (all with fakes):
  - the whole state machine, triggering every stop reason once;
  - profile resolution: an expired profile, a cooling profile, a same-family reviewer skipped, a swap, a step override;
  - the panel merge rules.
- **End-to-end:** `examples/toy` (two steps: a function with its tests, then a CLI flag).
  - First, with fakes.
  - Then once for real with the default roles.
  - Then once with `--swap`.
- **Accept:**
  - The toy plan reaches `done` both ways, with both steps committed on `factory/*` branches.
  - A planted scope violation, a planted acceptance-script edit and a reviewer that writes a file all stop the run.
  - `factory cost --by profile` prints the ledger totals.

##### F4: Reviewer calibration (experiment E3)

- **Setup.** `calibration/` holds 5 or 6 tiny synthetic repos, each a recorded step diff with one known flaw. Reconstruct them; do not copy Sprint 4 code. The flaws:
  - an answer-key leak in a code comment;
  - a test that a naive heuristic passes;
  - two acceptance criteria that contradict each other;
  - a time-dependent value that isn't pinned;
  - a tool that exposes declared columns instead of actual ones;
  - one clean control.
- **Run.** `factory calibrate --reviewers all` runs every available profile, in review mode, on each repo. It scores the catch rate, false alarms, verdict validity (before and after the repair call), seconds, and cost or tokens.
- **Accept:** one table, with a row per reviewer profile, written to `docs/agent-comparison.md` (section "Reviewers").
- **Why it matters:** this decides the reviewer lists, and it is a portfolio artifact in its own right ("I evaluate my reviewers").

##### F6: Implementer bake-off (optional, any time after F3)

- **Setup.** `examples/bakeoff/`: a 3-step toy plan with real design content, such as a small CSV → DuckDB loader with a data-quality check and tests. It is locked like any plan.
- **Run.** `factory bakeoff --implementers all --reviewer <one fixed profile>` runs the plan once per implementer profile, each on its own branch.
- **Measures:**
  - steps passed without help;
  - fix loops;
  - reviewer findings;
  - seconds;
  - cost, tokens or quota use;
  - lines changed.
- **Accept:** a "Implementers" section in `docs/agent-comparison.md`.
- **Result.** Together with F4, this is Amir's own comparison of Claude, Cursor (Grok and Composer), Gemini and, later, Codex. It is measured on the same tasks under the same gates, not taken from vendor benchmarks.

##### F5: Hand-over

- **Build:**
  - `docs/HOWTO.md`: daily use in 15 lines;
  - install as a tool (`uv tool install --editable .`);
  - a README for the factory itself.
- **Then** the governor spec session (§13.3), but not before Sprint 4 is submitted.

---

#### 10. First target: governor-ask (governed questions)

This is a seed brief. The spec session (§13.3) turns it into the governor repo's `PLAN.md`, `plan.yaml` and acceptance scripts.

**Why this one.**
- It was candidate A on the Sprint 4 shortlist, and it is rung R4 (plus pieces of R6) of the governor ladder in `idea1-deep-track-plan.md` §4.
- It reuses Sprint 4's fixture, metadata store, lineage and PII policy. The new work is the NL→SQL loop, validation, governance traces and evaluation, which is the part hiring managers ask about.

**Problem and users.**
- Finance and ops analysts ask questions of the billing mart: "MRR by plan last quarter", "unpaid invoices over 30 days by country".
- Analytics engineers worry about three things:
  - wrong SQL that looks right;
  - PII leaking into answers;
  - answers nobody can audit.
- governor-ask answers with governed SQL and shows its work. It refuses or masks according to policy, asks back when a question is ambiguous, and records a decision trace.

**Reuse.** Copy these after the Sprint 4 submission, and record provenance in the README:
- `fixture/`: the billing mart, its generator and the green build;
- `harvest.py` and the `meta.duckdb` schema;
- `lineage.py`;
- `knowledge/policy.yaml` and `owners.yaml`;
- `llm.py` (the OpenRouter client with cost);
- the patterns in `security.py`.

**Graph** (a LangGraph `StateGraph`):

```
guard → retrieve_context (catalog cards, column docs, metric definitions; hybrid search)
      → plan (models, grain, filters) → [clarify: interrupt when ambiguous]
      → draft_sql → validate → dry_run (DuckDB EXPLAIN) → repair (≤ 2, given the errors)
      → execute (read-only connection, row cap, timeout)
      → answer (numbers only from the result; SQL, models used, upstream lineage, source freshness)
      → record_trace
```

`validate` does these checks:
- the SQL parses with sqlglot;
- it is a SELECT only;
- every table and column is on the catalog allowlist;
- the role policy holds: PII is blocked or aggregated;
- a LIMIT is enforced.

**Who owns what.**
- **Python:** the allowlist, policy decisions, dry-run and execution, freshness and lineage.
- **The model:** interpreting the question, the plan, the SQL draft and the wording.

**Roles** (light personalisation): `analyst` (no PII; aggregates only on customer-level data) and `finance_admin` (PII masked unless a field-level grant exists). The role is picked in the UI. Policy is data in `policy.yaml`, not prompt text.

**Decision trace.** In the spirit of the EU AI Act's Article 12; inspired by it, not a compliance claim. One row per question records:
- role and question;
- retrieved ids and the plan;
- each SQL attempt, with the validator's output;
- policy decisions and the dry-run;
- the executed SQL, row count and result hash;
- the answer;
- model, tokens and cost;
- human feedback.

A Trace explorer page queries these rows.

**MCP.** Expose the read-only tools (`search_catalog`, `describe_model`, `get_lineage`, `validate_sql`, `run_governed_query`) as an MCP server over stdio, using the official Python SDK, so they work from Claude Desktop or Cursor. Confirm the SDK's API at that step.

**Evaluation (the headline).**
- **Golden set:** about 40 questions over the billing mart, each with gold SQL that has been executed on the green warehouse. Categories, with the correct behaviour where it isn't an answer:
  - simple, join, time grain, metric definition;
  - ambiguous: a clarifying question;
  - policy: refuse, aggregate or mask, depending on role;
  - unanswerable: "not in this data".
- **Split:** 25 tune and 15 holdout, frozen at G2, before any agent prompt exists. Amir reviews the gold SQL. Ground truth is never relabelled from model answers.
- **Metrics:**
  - execution accuracy: result sets match, ignoring order unless the question asks for one, with a numeric tolerance;
  - valid-SQL rate, first try vs after repair;
  - clarification precision and recall;
  - policy compliance, where any PII leak fails the whole run;
  - cost and latency.
- **Baseline:** a one-shot prompt with the full schema pasted in, no retrieval and no validator.
- **Stretch (later, R5):** a subset of Spider 2.0-DBT. Check its licence and harness before promising a number.

**Steps** (seed; finalised in §13.3):

| Step | What | Tier | Gate |
|---|---|---|---|
| G1 | Repo, copied fixture, green build, metadata store, tests | mechanical | — |
| G2 | Golden set, gold SQL, execution checker, frozen split | design | HUMAN (ground truth) |
| G3 | Baseline, and the eval harness scoring it | design | — |
| G4 | Catalog cards, hybrid schema retrieval, recall@k on the gold tables | mechanical | — |
| G5 | SQL validator, policy by role, dry-run, safe executor | design | HUMAN (security) |
| G6 | Graph, with the clarify interrupt, repair and traces | design | — |
| G7 | Streamlit pages: Ask, Trace explorer, Developer | mechanical | — |
| G8 | MCP server | mechanical | — |
| G9 | Evaluation (tune, then the holdout once) and README | design | HUMAN (release) |

---

#### 11. Environment notes

- **Where the orchestrator runs:** on Amir's Windows machine, in PowerShell, because `agent` and `claude` are installed there with his logins.
- **If you are the Claude app working through the device bridge:**
  - You can edit files in connected folders and run Python in the Linux VM.
  - Never run `uv sync` against the repo's `.venv` from the VM; it would replace the Windows environment. For VM runs, set `UV_PROJECT_ENVIRONMENT=$HOME/.venvs/<repo>`.
  - For anything that needs `agent`, `claude`, git commits or Windows paths, give Amir the exact PowerShell command. Have the command write its output to a file in the repo, then read that file.
- **If you are Claude Code running natively on Windows:** run everything yourself. The commit rule (D7) still applies.
- **Folders:** by default, `C:\Users\amir0\portfolio\factory` and `C:\Users\amir0\portfolio\governor`, as separate git repos. Amir creates the parent folder (`mkdir $HOME\portfolio`) and connects it.
- **Factory dependencies:** Python 3.12, uv, pydantic v2, PyYAML, typer or argparse, pytest. Any other dependency needs a reason in NOTES.

---

#### 12. Verify first (don't assume)

- **Cursor CLI on native Windows:**
  - the JSON output fields (the chat id for `--resume`, the error shape);
  - whether `--model` accepts the Grok and Composer ids that `agent models` shows;
  - how `--force` and `--sandbox` behave;
  - whether a permission config file exists for denying commands.
- **Claude Code**, against the installed version:
  - where the `--json-schema` result lands (`structured_output`);
  - `--max-budget-usd` and `--append-system-prompt-file`;
  - the `allowedTools` pattern syntax;
  - whether `--max-turns` exists.
- **Claude accounts on Windows.**
  - `CLAUDE_CONFIG_DIR` gives the second account its own login. A community account switcher relies on this, and it keeps credentials in that folder's `.credentials.json`.
  - Confirm that a headless `claude -p` started with that variable uses that account.
- **Gemini CLI**, against `gemini --help`:
  - the model flag;
  - the approval or YOLO flag names;
  - whether default approval mode refuses writes in headless runs;
  - the `stats` token fields;
  - usage-limit messages.
- **Codex CLI**, when installed:
  - `exec --json` usage fields;
  - `--output-schema` together with `-o`;
  - `--sandbox read-only`;
  - how to resume a session.
- **College account terms.** Check that the Turing College account may be used for personal portfolio work, and remember that its prompts and code sit under the college's organisation settings.
- **Billing.** Does headless `claude -p` on a subscription login count against the plan the same way interactive use does? Would Amir rather use an API key for some runs, which also allows `--bare`?
- **Cursor quota.** How much of the plan does a 40-minute headless Grok run use? Experiments E1 and E4 measure this.

---

#### 13. Prompts

##### 13.1 Kickoff, F0 (fresh chat in this Project)

```
New build: the "code factory", an orchestrator that runs an implement → review cycle automatically with human gates. Any of my agents (Claude Code on two accounts, Cursor, Gemini CLI, later Codex) can play either role, set by profiles. Later we use it to build governor-ask.

Read the Project doc claude/factory-build-spec.md (the spec; follow it) and claude/agentic-dev-workflow.md §3–§5. Nothing else unless the spec points to it.

Do phase F0 (spec §9). First ask me which parent folder to use (default C:\Users\amir0\portfolio) and request access to it. Stop at F0's HUMAN step and give me the exact PowerShell commands; I'll run them and tell you when the output files exist.

Hard rules: don't touch the Turing College sprint folders. Never read .env files or print keys. Keep NOTES.md short (spec §7.4). Finish by writing "F0 result" and "Additions for F1" into the factory repo's NOTES.md.
```

##### 13.2 Each later phase, F1–F6 (fresh chat each time)

```
Factory F<n>. Read the factory repo's STATUS.md, NOTES.md ("Current state", "Open questions", "Additions for F<n>") and PLAN.md §9 F<n> plus the sections it names. Don't read NOTES-archive.md or whole generated files.

Do F<n> as specified and run its acceptance. Write "F<n> result" and "Additions for F<n+1>" into NOTES.md, rotate NOTES per §7.4, and update STATUS.md. Stop and show me the acceptance table and any HUMAN step with exact PowerShell commands.
```

##### 13.3 governor spec session (after Sprint 4 is submitted)

```
Sprint 4 is submitted. Let's spec governor-ask for the factory.

Read: the factory repo's PLAN.md §4, §7.1 and §10; the Project docs claude/project-portfolio-strategy.md §2 and claude/idea1-deep-track-plan.md §4; the Sprint 4 README, for what we reuse. Ask me at most 5 questions first.

Then write, in <parent>\governor: PLAN.md (decisions, layout, eval design), plan.yaml (steps G1–G9 with tier, allowed_paths, review_focus and gates), plan/prompts/G*.md (≤ 60 lines each), plan/accept/accept_g*.py (deterministic, JSON on the last line), and AGENTS.md (with the never-read list). Run every acceptance script once on the empty repo to show it fails cleanly. I review, then run `factory lock`.
```

##### 13.4 Running it (Amir, PowerShell)

```powershell
cd $HOME\portfolio\governor
factory plan validate plan.yaml
factory lock
factory profiles                # who is available, and why not
factory run --until-gate        # runs steps until a HUMAN gate or a stop, with the default roles
factory run --until-gate --implementer cursor-grok --reviewer claude-tc-opus   # pick both for this run
factory run --until-gate --swap # reviewer implements, implementer reviews
factory run --until-gate --panel   # extra reviewers on every step, not just at gates
factory status                  # or open STATUS.md
factory approve G2              # or: factory reject G2 --note "…"
factory cost --by profile
```

When a run stops at a design gate and you want a second opinion, open a fresh Claude chat in the Project:

```
Review governor G<n>: read STATUS.md, the last step in NOTES.md, its acceptance JSON and `git diff --stat factory/G<n>`, and apply the rubric.
```

That is the only place a long Claude review is worth its tokens.
