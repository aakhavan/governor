# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D3 is in place on top of D2. python -m governor.build run profiles raw, asks the plan model for a design, and validates it in code. A valid design writes governor/design.json and governor/design.md in the target and pauses on an interrupt with status awaiting_design_approval. approve and reject resume that thread from GOVERNOR_STATE_DIR/build_checkpoints.sqlite in a new process. Approve appends one column_mapping decision per built-KPI mapping to <target>/governor/approved.yaml, with approver, date, and source, and finishes as design_approved. knowledge/approved.yaml is only the cross-company default read into the prompt. A proposal with findings is sent back at most twice, then design_invalid, and design.json is not written. One rejection returns the design to the plan model with the note; a second ends as design_rejected. The prompt has no min, max, or raw cell values. build does not import ask.

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

## D2 result
*Profile the raw schema, 04 Nov 2026 18:09.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/D2`.

| check | ok | detail |
|---|---|---|
| Docker is running | yes | 29.9.2 |
| testbed/docker-compose.yml exists | yes | missing |
| compose stack up and healthy | yes |  Container governor_accept-postgres-1 Started  |  Container governor_accept-postgres-1 Waiting  |  Container governor_ac |
| sample loads into raw | yes | 9 tables |
| roles applied | yes | roles applied |
| profile CLI writes the profile | yes | {"out": "C:\\Users\\amir0\\AppData\\Local\\Temp\\governor_accept_qfhdv2gk\\profile.json", "schema": "raw", "tables": 9,  |
| all 9 raw tables profiled | yes | ['olist_customers_dataset', 'olist_geolocation_dataset', 'olist_order_items_dataset', 'olist_order_payments_dataset', 'o |
| row counts match the sample | yes |  |
| loader columns starting with _ are left out | yes |  |
| orders key is order_id | yes | [['order_id'], ['customer_id'], ['order_purchase_timestamp'], ['order_approved_at'], ['order_estimated_delivery_date']] |
| customer_id is a key and customer_unique_id is not | yes | [['customer_id']] |
| orders.customer_id relates to customers.customer_id | yes | [('olist_order_items_dataset.order_id', 'olist_orders_dataset.order_id'), ('olist_order_items_dataset.product_id', 'olis |
| purchase timestamp inferred as timestamp | yes | {'name': 'order_purchase_timestamp', 'inferred_type': 'timestamp', 'null_rate': 0.0, 'distinct': 5, 'pii': False, 'min': |
| price inferred as numeric | yes | {'name': 'price', 'inferred_type': 'numeric', 'null_rate': 0.0, 'distinct': 3, 'pii': False, 'min': 50.0, 'max': 100.0} |
| customer_unique_id is flagged PII with no min or max | yes | {'name': 'customer_unique_id', 'inferred_type': 'text', 'null_rate': 0.0, 'distinct': 5, 'pii': True, 'min': None, 'max' |
| no PII value appears in the profile | yes | [] |
| pytest tests/build | yes | 23 passed, 7 skipped in 0.61s |

Review: D2 profiles raw in SQL and matches section 5. Python receives counts plus min/max only for non-PII integer, numeric, date, and timestamp columns; policy columns, including numeric lat/lng, are counts only. Sample keys, the seven relationships, types, row counts, and the PII-string check all follow from that rule. Table and relationship order is sorted, and nothing reads the clock.

For Amir: On this five-row sample, section 5 treats every unique column as a key, so orders also keys its purchase, approved, and estimated-delivery timestamps, and products keys its measure columns. It will not hold on the full extract. The policy file does not name geolocation_zip_code_prefix, geolocation_city, geolocation_state, or seller_state. Those columns are text in the sample, so no value is written. Lat and lng are listed and their min/max are suppressed. Live pytest was skipped (no DB env in that process); the CLI check in accept_d2.py is what ran the profile.

## Additions for D3
profile_schema(dsn, schema, policy) and the profile CLI use build_dsn(). Shape: schema, profiled_at_rows (always true), tables (name order), relationships (from, to order). Columns are ordinal, skipping names that start with _. Fields: inferred_type (boolean|integer|numeric|date|timestamp|text), null_rate (6 d.p.), distinct, pii, min, max. pii means the column or table.column is a policy key (load_policy on knowledge/shop/policy.yaml). min/max only for non-PII integer (int), numeric (float), date (YYYY-MM-DD), timestamp (YYYY-MM-DD HH:MM:SS). Keys: non-null, distinct == rows; pairs only if no single-column key. Relationships: single-column keys only, from the other column to the key, coverage of non-null distinct values >= 0.95, 4 d.p. Sample has seven: items.order_id, items.product_id, items.seller_id, payments.order_id, reviews.order_id, orders.customer_id, products.product_category_name. customer_id is a key; customer_unique_id is not. Extra keys are tiny-sample artifacts (timestamps, review_score, product measures, seller zip/city/state); do not treat them as business primary keys. Models live in governor.build.models. build does not import governor.ask.

## D3 notes (implementer)
- New module `governor.build.llm` (not in the section 2 table): `make_llm("openrouter"|"fake:<script>")`, `BuildLLM.structured(kind, prompt, schema, role)` / `.text(kind, prompt, key, role)`; roles `plan`/`write` read `GOVERNOR_BUILD_PLAN_MODEL`/`GOVERNOR_BUILD_WRITE_MODEL` (default CHAT_MODEL), clients built on first call. Fake lists: in order, last repeats; `intermediate`/`repair` keyed by model name for D4. Every call appends a usage dict to `llm.calls`; the graph keeps them in state `calls`.
- Prompt has no data values at all: min/max are dropped for every column (not only PII), PII columns are name, pii, null_rate, distinct. Catalogue goes in without `template_sql`.
- Extra finding codes beyond section 6: `PROPOSAL_UNPARSEABLE` (reply is not a Proposal; graph), `EXPR_UNPARSEABLE` (staging expr or boolean mapping is not one expression, or is a query), `KPI_DUPLICATE`. `PII_UNTAGGED` also fires on an intermediate column that carries a PII column of its refs by name. A build KPI without `domain` is `MAPPING_INCOMPLETE`.
- Graph: `propose` counts a repair when it gets findings; 1 + 2 proposals, then write_report and `design_invalid` (design.md with findings, no approve command; design.json is not written for an invalid design). Reject resets the repair budget for one more round with the note and the previous proposal in the prompt; a second reject ends with `design_rejected`. `approve` writes one `column_mapping` per mapping entry (`id map-<kpi>-<name>`, value = the mapping value verbatim, `approved_on` = today's date), replacing same-id entries; the file is checked with `load_approved`.
- `run --profile <file>` uses a saved profile instead of the database; `tests/build/test_graph.py` uses it to run run/reject/approve in new processes offline. `run --policy` defaults to `knowledge/shop/policy.yaml` (answers the D2 question for `run`; `profile` is unchanged).
- Approved context for the prompt: `knowledge/approved.yaml` then `<target>/governor/approved.yaml`.
- For Amir: sample_design.json leaves review comment title/message out of silver (free text, no KPI needs it), and int_order_reviews keeps the latest answer per order by `review_answered_at`, then `review_id`.

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
