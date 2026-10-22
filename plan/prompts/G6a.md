# G6a: The governor-ask graph (core)

One LangGraph v1 `StateGraph`; code owns the edges. This step builds the graph and its prompts with an in-memory checkpointer; persistence, traces, CLI and the eval system come in G6b. Reuse `governor.ask.retrieval`, `validator`, `executor`, `governor.core.lineage`, `governor.core.security`, `governor.core.llm`.

Build:
1. `src/governor/ask/schemas.py`: `QueryPlan{intent: answer|clarify|unanswerable, models, metrics, grain, filters, time_range, missing_slot}`, `SqlDraft{sql, rationale}`, `AnswerDraft{text_with_placeholders}`, graph state.
2. `src/governor/ask/graph.py`: `build_graph(*, llm=None, checkpointer=None)` (default: LangGraph `InMemorySaver`) with nodes exactly `guard, retrieve_context, plan, clarify, draft_sql, validate, dry_run, repair, execute, answer, record_trace`:
   - `guard`: `governor.core.security` regex + model flag; refusal text never echoes the input.
   - `plan`: structured output (gpt-5-nano). `clarify` calls `interrupt()` with the missing slot and resumes with the user's answer, then re-plans once.
   - `draft_sql` / `repair` (gpt-5-mini): repair gets validator codes and dry-run errors; at most 2 repairs, then a refusal.
   - `validate` → `PII_FORBIDDEN` or `TABLE_NOT_ALLOWED` ends in a policy refusal that names the rule, not the data.
   - `answer`: the model writes wording with placeholders like `{r0c1}`; Python fills every data value (numbers, names, categories, dates) from the result rows, and the result table is shown next to the text. Text outside placeholders may not contain digits or result values (checked in code). Also shows the executed SQL, models used, upstream sources (`core.lineage`) and freshness vs `as_of`.
   - Relative dates resolve against `governor.core.paths.as_of()`. Only trace timestamps read the clock, as `datetime.now(timezone.utc)`.
3. `record_trace` in this step builds the trace row (a dict) in state and stops there; G6b writes it to storage.
4. Prompts in `src/governor/ask/prompts/` (`plan.md`, `draft_sql.md`, `repair.md`, `answer.md`); no golden questions in them.
5. Offline tests in `tests/ask/` with a scripted fake chat model (`governor.ask.llm_testing`), with these exact test names:
   `test_clarify_interrupt_and_resume` (same process), `test_repair_then_success`, `test_repair_exhausted_refuses`, `test_policy_refusal_analyst`, `test_pii_masked_finance_admin`, `test_answer_numbers_come_from_result`, `test_guard_blocks_injection`, `test_volatile_time_never_reaches_execute`.

Read: `src/governor/ask/{retrieval,validator,executor,llm_testing,baseline}.py`, `src/governor/core/{llm,security,lineage,paths}.py`.

Done when `plan/accept/accept_g6a.py` passes.
