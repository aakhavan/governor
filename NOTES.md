# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D4 is in place on D3. approve resumes the design-gate interrupt and writes silver: staging SQL from the approved design in code, intermediate SQL from the write model, both checked before dbt. check_sql requires one Postgres SELECT, declared refs only, source() only for that staging model's raw table, and no DDL or DML. dbt build --select staging intermediate runs as governor_build into dev_governor; column names are then checked in information_schema. A failing model is repaired twice with the write model and once with the plan model, then the run ends silver_built or escalated (model plus last error). repairs is the number of repair calls. Yml tags PII at config.meta, unique and not_null on a single-column key, and a singular test for a composite key. build does not import ask.

## Open questions
- G2b gate review (claude.ai, 22 Oct): golden set fine; but `fixture/build_green.py` stamps as_of from the wall clock (Sprint 4 behaviour), so a rebuild on another day shifts days_outstanding/overdue answers and breaks the golden as_of check. Spec change for G3 (item 0 + locked check): pin as_of in `fixture/AS_OF` = 2026-10-22T14:11:26+00:00. Needs `factory relock` before `approve G2b`.
- `fct_invoices.days_outstanding` follows the spec literally: 0 only when fully paid. Void invoices (416 not paid) therefore show days outstanding. Should void count as 0 / be excluded? (Amir decides; one-line change in the SQL.)
- `as_of` is the build's wall-clock instant (S4 design: source freshness needs `_loaded_at` within 12 h). Data dates are fixed (seed 42) but `days_outstanding` shifts with each rebuild. Pin as_of if golden answers must be stable across rebuilds.
- `governor.core.config` replaces S4 `triage.config`, which was not imported. Values reconstructed: `ALLOWED_MODELS` from the S4 test, MAX_TOKENS 4096 from the llm docstring; `FAST_MODEL` (`openai/gpt-5-nano`) and `EMBED_MODEL` (`openai/text-embedding-3-small`) are guesses, overridable by env. Check before G4/G5 use them.
- `chromadb` is not a dependency (not in the G1 list). `retrieval.build_index/load_index` need it; add it in the step that uses dense retrieval.
- access.yaml: every model and grant name matches the real warehouse (allowlist = the four marts; `dim_accounts.contact_email` exists and is tagged `email`). No renames needed.
- Capstone brief not yet available; PLAN §1 holds the provisional stance (ask = spine, one triage path = stretch).
- G2b gold numbers are frozen against as_of 2026-10-22T14:11:26+00:00 and the current green build. m05, m06 and j04 depend on days_outstanding / paid amounts; a rebuild that moves as_of changes them and the gold must be rechecked (FROZEN hashes cover the files, not the results).
- G2b metric gold (m01-m03) mirrors metrics.yaml and returns (month_start, value). compare needs equal column counts, so a bare number fails these items. Amir: keep (forces the snapshot month to be stated), or drop month_start from the gold?
- Sol suggested comparing column names/types in the checker; kept name-agnostic on purpose (LLM aliases vary; Spider-style execution accuracy), with equal column counts and permutation matching.

- G3: dbt `source freshness` measures `_loaded_at` against the wall clock (DuckDB now()), and `_loaded_at` is now the pinned as_of, so green sources report warn after 12 h and error after 24 h. build_green.py accepts that (status pass/warn/error, 2 results) instead of failing. Side effect: green sources.json / meta.freshness are not "pass", so `lineage.failing_nodes` on the green build would flag the two sources. Clean fix (outside G3 paths): a project macro overriding `collect_freshness` to use `var('as_of')` as snapshotted_at, or `loaded_at_query` in _sources.yml. Amir decides.
- G3: the prompt gave AS_OF as `2026-10-22T14:11:26+00:00`, but the locked check compares against `str()` of the YAML datetime, so fixture/AS_OF and as_of.txt use `2026-10-22 14:11:26+00:00` (same instant; fromisoformat reads both).
- G3: `--llm` defaults to `fake` so nothing spends money by accident; G10 must pass `--llm openrouter`. The report records `llm`.

## D3 result
*Design proposal, validation, report and the design gate, 04 Nov 2026 18:34.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D3`.

| check | ok | detail |
|---|---|---|
| build never imports ask | yes |  |
| prompts/propose.md exists | yes | missing |
| sample design fixture exists | yes | tests/fixtures/build/sample_design.json |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| build init lists the 9 raw tables | yes |  |
| run pauses at the design gate | yes | {"thread_id": "361ad025-7769-4363-82ec-4975ac82930b", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| design report written | yes | C:\Users\amir0\AppData\Local\Temp\governor_accept_0e4y7ogz\olist-dbt\governor\design.md |
| report lists every catalogue KPI | yes |  |
| report has a gap report section | yes |  |
| report shows the approve command with the thread id | yes |  |
| design.json written | yes |  |
| conversion_rate and gross_margin declined with complete gaps | yes |  |
| invalid proposal stops as design_invalid (MAPPING_UNKNOWN_COLUMN) | yes | {"thread_id": "ec3f60f9-a4d3-4c84-aa63-98a950e873cf", "status": "design_invalid", "report": "C:\\Users\\amir0\\AppData\\ |
| invalid proposal stops as design_invalid (unbuildable KPI marked build) | yes | {"thread_id": "87c6b230-b6e9-433b-a73f-d75e42734feb", "status": "design_invalid", "report": "C:\\Users\\amir0\\AppData\\ |
| invalid proposal stops as design_invalid (PII_UNTAGGED) | yes | {"thread_id": "0820a3b0-7982-4210-92c9-b030cab8703b", "status": "design_invalid", "report": "C:\\Users\\amir0\\AppData\\ |
| a bad first proposal is repaired | yes | {"thread_id": "baae2829-65d5-4e08-9f17-68675fe8cb38", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| reject sends the design back and pauses again | yes | {"thread_id": "361ad025-7769-4363-82ec-4975ac82930b", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| approve in a new process records the design | yes | {"thread_id": "361ad025-7769-4363-82ec-4975ac82930b", "status": "design_approved", "report": "C:\\Users\\amir0\\AppData\ |
| approved column mappings recorded in the target's approved.yaml | yes | [['column_mapping', 'amir'], ['column_mapping', 'amir'], ['column_mapping', 'amir'], ['column_mapping', 'amir'], ['colum |
| pytest tests/build | yes | 67 passed, 8 skipped in 13.25s |

Review: D3 matches the step. Every section 6 code is implemented and fires on a minimal bad proposal; EXPR_UNPARSEABLE, KPI_DUPLICATE, and PROPOSAL_UNPARSEABLE cover the gaps the table leaves. The prompt strips min/max and sends PII columns as name, null rate, and distinct count, with no sample cell values. Code owns every edge. The gate is an interrupt, and approve/reject resume it from SQLite in a new process. Approvals append column_mapping decisions to the target's governor/approved.yaml and never write knowledge/. build does not import ask. Acceptance exercised that path on the Docker test bed.

For Amir: The unbuildable-KPI acceptance check is any() of three code names. This run's only finding was MAPPING_UNKNOWN_MODEL, which is the right code (product_costs mapped to stg_product_costs). Staging with no source_table is implemented as BAD_FOLDER but is not its own parametrized case. A later design_invalid after a rejection does not delete the previous design.json. CLI approved_on is date.today.

## Additions for D4
Extend the same StateGraph. record_decisions currently goes to END and sets status design_approved; point it at write_silver and set the final status to built or escalated in that same approve() resume. approve() resumes only while the next node is design_gate. State: target (absolute), project_name, policy, profile, proposal, findings, repairs, rejections, note, status, report, design, approved_by, approved_file, calls. repairs is the design-loop count and can already be 1 or 2 at approval; use a separate counter for SQL repair. calls uses operator.add, so return only the new usage dicts. design.json is Proposal.to_json_dict(), written only when validation passed, at <target>/governor/design.json. Staging expr is raw-table SQL; intermediate expr is null and the write model owns that SQL. Fake LLM via make_llm('fake:<script.json>'): propose[], intermediate{model:[]}, repair{model:[]}; the last reply repeats. Plan and write roles use GOVERNOR_BUILD_PLAN_MODEL and GOVERNOR_BUILD_WRITE_MODEL. Do not import governor.ask. Do not write knowledge/; company decisions stay in <target>/governor/approved.yaml. tests/fixtures/build/sample_design.json builds every catalogue KPI except conversion_rate and gross_margin, which it declines with gaps.

## D4 notes (implementer)
- `governor.build.silver`: `check_sql`, `staging_sql`, `write_silver` / `dbt_build_silver` / `repair_silver` / `next_step` over a JSON-able state dict (checkpointed by the graph under `silver`), and `build_silver(target, design, llm, runner=, inspector=)` chaining them. Prompts `prompts/intermediate.md`, `prompts/repair.md` (design only, no data values).
- Graph: `record_decisions -> write_silver -> {dbt_build_silver | repair_silver | silver_done}`, code-routed by `silver.next_step`. SQL refused by `check_sql` is never written and goes to repair before dbt runs. Per model: 2 write-model repairs, then 1 plan-model repair; still failing -> `escalated` with `{"model", "error"}`. `approve` returns `status` (`silver_built`|`escalated`), `models`, `tests_passed`, `repairs` (= state `sql_repairs`, repair calls), plus `escalated` when it applies. `build_graph` takes `dbt_runner`/`inspector` for offline tests.
- A failing test is attributed to the silver model whose name it contains (longest match). dbt with no results (profile/connection/parse error) escalates with `model: null` and no repair.
- yml: PII as column `config: {meta: {pii: true}}` (dbt 1.12 moved `meta` under `config`); key tests under `data_tests`; model `config.meta.primary_key`. Composite keys: `tests/<model>__primary_key.sql` (duplicates or null parts). Models stay views (dbt default); only marts are tables.
- Column check: names only (case-insensitive) against `information_schema.columns` in `dev_governor`, as the build login.
- For Amir: stale `stg_*`/`int_*` files from an earlier design are not deleted from the target. The offline CLI cycle in `test_graph.py` now ends `escalated` (its approve script has no intermediate SQL). The live pytest cases in `test_silver.py` skip without `GOVERNOR_BUILD_PASSWORD`; acceptance covers the live path.

## D4 result
*Silver writer, dbt build in the dev schema, repair and escalation, 04 Nov 2026 21:54.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D4`.

| check | ok | detail |
|---|---|---|
| sample design and silver fixtures exist | yes | tests/fixtures/build/ |
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| build init lists the 9 raw tables | yes |  |
| run pauses at the design gate | yes | {"thread_id": "7c556dce-bf99-4cbc-b038-a14c66ada5ff", "status": "awaiting_design_approval", "report": "C:\\Users\\amir0\ |
| approve builds silver | yes | {"thread_id": "7c556dce-bf99-4cbc-b038-a14c66ada5ff", "status": "silver_built", "report": "C:\\Users\\amir0\\AppData\\Lo |
| tests ran and passed | yes | 11 |
| the scripted bad draft was repaired | yes | 1 |
| every silver model exists in dev_governor | yes | [] |
| nothing written outside dev_governor | yes | [] |
| silver yml tags PII columns | yes |  |
| silver yml has unique and not_null key tests | yes |  |
| composite keys have singular tests | yes |  |
| a model that cannot be repaired ends escalated | yes | {"thread_id": "9fd8b17c-fc24-4565-8de1-9e03ca00db18", "status": "escalated", "report": "C:\\Users\\amir0\\AppData\\Local |
| pytest tests/build | yes | 88 passed, 10 skipped in 14.46s |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The live run is the evidence: tests_passed 11 equals 4 single-column keys times unique and not_null, plus 3 composite singular tests, and int_order_lines exists only after the repair replaced i.price with i.item_price. The yml checks in accept_d4.py are substring searches. Section 8 still says status built; the step and the script use silver_built until D5. When several models run out of repairs together, only the first is named. A dbt failure tied to no model escalates with model null. Reused targets keep stale SQL files. approved_on is still date.today.

## Additions for D5
On silver_built, continue to write_gold; leave escalated at END. Section 8's approve status built is the post-gold name; D4 returns silver_built plus models, tests_passed, and repairs. State.repairs is the design-loop count. SQL repairs are state.sql_repairs and silver.repairs, with per-model counts in silver.attempts (2 write, then 1 plan). calls uses operator.add; return only new usage dicts. Files: models/staging/_staging.yml, models/intermediate/_intermediate.yml, models/<folder>/<name>.sql, and tests/<model>__primary_key.sql for a composite key. PII is columns[].config.meta.pii (dbt 1.12). Single-column keys use data_tests [unique, not_null]. Composite keys do not get per-column unique tests; the singular test returns rows for a duplicate or a null key part. Model config.meta.primary_key lists the key. Silver models stay views; marts are tables via dbt_project.yml. The profile already targets dev_governor as governor_build. That schema is shared and not dropped, and a reused target keeps stale stg_/int_ files. The column check compares names only. design.json is the proposal at <target>/governor/design.json. The sample declines conversion_rate and gross_margin. Do not import governor.ask. Do not write knowledge/.
