# Capstone batch 2 (D steps): build mode

Agreed with Amir on 4 Nov 2026. Batch 1 contracts (`design.md` sections 3 to 10) still hold; this file adds what build mode needs. Vocabulary: `CONTEXT.md`.

## 1. Decisions

- **The company owns its dbt project.** governor writes into a working copy of the company's dbt repo (for Olist: `aakhavan/olist-dbt`) given as `--target <dir>`, and opens a pull request there (D6). governor's own repo holds no company models. Tests use a temp directory and a local bare repo.
- **8 Nov build gate:** raw tables to tested gold models for the 5 order-level KPIs (`gmv`, `net_revenue`, `aov`, `on_time_delivery_rate`, `avg_review_score`), plus the gap report for the declined `conversion_rate` and `gross_margin`. The customer-level KPIs (`repeat_purchase_rate`, `cohort_retention`, `historical_clv`) follow in the same batch.
- **Models per node.** Planning work (reading the profile, proposing the design, the gap report) uses `GOVERNOR_BUILD_PLAN_MODEL`, a strong model. Writing work (intermediate SQL, repairs) uses `GOVERNOR_BUILD_WRITE_MODEL`, a mid model; after two failed repairs of one model the plan model gets one try (escalation). Both go through `governor.core.llm` with cost per call. Tests and acceptance use the fake LLM only.
- **Gates.** Design gate: an `interrupt()` in the build graph; Amir approves with `python -m governor.build approve <thread_id>` (an API endpoint can call the same function later). Review gate: the pull request (D6). No Streamlit pages in batch 2.
- **Deterministic where possible.** Profiling, staging SQL, gold SQL, tests, blueprint checks and the gap report are code. The model chooses names, types, keys, joins and the KPI column mapping, and writes intermediate SQL. Every model output is validated before it is used.
- `governor.build` never imports `governor.ask`, and `governor.ask` never imports `governor.build`.

## 2. Module layout (`src/governor/build/`)

| Module | Step | What |
|---|---|---|
| `workspace.py` | D1 | create the target dbt project layout (section 4), write `models/sources.yml` |
| `dbt.py` | D1 | run dbt as a subprocess for a target, parse `run_results.json` |
| `profile.py` | D2 | profile a raw schema (section 5) |
| `models.py` | D3 | Pydantic models: profile, design proposal, build summary |
| `design.py` | D3 | prompt the proposal, validate it (section 6), render the design report (section 7) |
| `graph.py` | D3–D5 | the build `StateGraph` (section 8) |
| `silver.py` | D4 | staging SQL from the design, intermediate SQL from the write model, checks, dbt build, repair |
| `gold.py` | D5 | gold models from catalogue templates, blueprint checks, gap report |
| `__main__.py` | D1–D5 | CLI: `init`, `profile`, `run`, `approve`, `reject` |
| `prompts/*.md` | D3–D4 | `propose.md`, `intermediate.md`, `repair.md` |

## 3. Database and test bed

- `governor_build` gets `USAGE` on schema `raw` and `SELECT` on its tables (it reads bronze to build silver), keeps `CREATE` on `dev_governor` only, and nothing else (D1, `testbed/sql/roles.sql`).
- Connection settings come from env only: `GOVERNOR_PG_HOST` (default `localhost`), `GOVERNOR_PG_PORT` (default `55432`), `GOVERNOR_PG_DB` (default `shop`), `GOVERNOR_BUILD_USER` (default `governor_build`), `GOVERNOR_BUILD_PASSWORD` (test-bed default `governor_build_local`). Nothing writes a password to a file.
- The compose file maps `${GOVERNOR_PG_PORT:-55432}`. Acceptance runs its own stack on port **55433** with its own DSNs, so the dev test bed and acceptance never collide.
- The shop's PII policy and access files are `knowledge/shop/policy.yaml` and `knowledge/shop/access.yaml` (human-owned, same formats as `knowledge/policy.yaml` and `knowledge/access.yaml`).

## 4. Target dbt project layout

```
<target>/
  dbt_project.yml          name from --project-name, profile: governor, models/marts materialized as table
  profiles/profiles.yml    dbt-postgres; every credential is env_var(...); target dev uses schema dev_governor
  models/sources.yml       bronze: source 'raw' with each raw table and its columns (generated)
  models/staging/          silver: stg_<entity>.sql + _staging.yml
  models/intermediate/     silver: int_<name>.sql + _intermediate.yml
  models/marts/<domain>/   gold: kpi_<id>.sql + _<domain>.yml
  tests/                   singular tests (composite primary keys)
  governor/design.json     the proposal (pending until approved)
  governor/design.md       the design report
  governor/approved.yaml   approved decisions for this company (design.md section 8 format)
  governor/gaps.md         the gap report
  governor/build.json      the last build summary
```

dbt always runs with `--project-dir <target> --profiles-dir <target>/profiles`. The dbt executable is found next to `sys.executable` without resolving symlinks (the C1 lesson). The company's approved decisions live in its own repo (`<target>/governor/approved.yaml`), so they are reviewed with its pull requests; `knowledge/approved.yaml` stays the cross-company default.

## 5. Profile format (D2)

```json
{"schema": "raw", "profiled_at_rows": true,
 "tables": [{"name": "olist_orders_dataset", "rows": 99441,
   "columns": [{"name": "order_id", "inferred_type": "text", "null_rate": 0.0, "distinct": 99441,
                "pii": false, "min": null, "max": null}],
   "candidate_keys": [["order_id"]]}],
 "relationships": [{"from": "olist_orders_dataset.customer_id", "to": "olist_customers_dataset.customer_id", "coverage": 1.0}]}
```

- `inferred_type`: `integer`, `numeric`, `timestamp`, `date`, `boolean` or `text`, from the values (raw columns are all text). Empty strings count as null.
- `min` and `max` only for non-PII columns of type integer, numeric, timestamp or date. PII columns (from the policy file) carry counts only: never a value, never a sample.
- `candidate_keys`: single columns with no nulls and `distinct == rows`; then column pairs, only for tables without a single-column key.
- `relationships`: for each candidate key column K and each column C with the same name in another table, the share of C's non-null distinct values found in K (`coverage`), listed when it is at least 0.95.
- Columns starting with `_` (the loader's `_loaded_at`) are left out.

## 6. Design proposal format and validation (D3)

```json
{"silver_models": [
   {"name": "stg_orders", "folder": "staging", "source_table": "olist_orders_dataset", "refs": [],
    "description": "one row per order", "primary_key": ["order_id"],
    "columns": [{"name": "order_id", "expr": "order_id", "type": "text", "pii": false, "description": "order key"},
                {"name": "purchased_at", "expr": "CAST(order_purchase_timestamp AS timestamp)", "type": "timestamp", "pii": false, "description": ""}]},
   {"name": "int_order_lines", "folder": "intermediate", "source_table": null, "refs": ["stg_order_items", "stg_orders"],
    "description": "one row per order item, with the order's status, purchase time and customer key",
    "primary_key": ["order_id", "order_item_id"],
    "columns": [{"name": "order_id", "expr": null, "type": "text", "pii": false, "description": ""}]}],
 "kpis": [
   {"id": "gmv", "decision": "build", "domain": "sales",
    "mapping": {"order_lines": "int_order_lines", "order_id": "order_id", "purchased_at": "purchased_at",
                "item_price": "item_price", "freight": "freight_value",
                "valid_order": "order_status NOT IN ('canceled', 'unavailable')"}},
   {"id": "conversion_rate", "decision": "decline", "reason": "no session or visit data in raw",
    "gap": {"missing": ["sessions"], "typical_sources": ["web analytics such as GA4", "the shop platform's session export"],
            "next_step": "load daily session data into raw, then rerun the build"}}],
 "assumptions": ["order_status values 'canceled' and 'unavailable' mean the order is not a sale"]}
```

- Staging models have a `source_table` and no `refs`; each column's `expr` is SQL over that raw table's columns. Intermediate models have `refs` to silver models and no `source_table`; their columns declare the output and `expr` is null (the write model writes the SQL in D4).
- A KPI mapping maps each catalogue relation to a silver model name and each input to a column of that relation's model, or to a boolean SQL expression over its columns (inputs of type `boolean`).

Validation is code and returns codes; any code sends the proposal back to the plan model with the findings (at most 2 repairs), then the run stops with status `design_invalid`.

| Code | When |
|---|---|
| `UNKNOWN_SOURCE_TABLE` | a staging `source_table` is not in the profile |
| `UNKNOWN_SOURCE_COLUMN` | a staging `expr` reads a column the source table does not have (parsed with sqlglot) |
| `BAD_FOLDER` | staging with refs or without source, intermediate with a source or without refs, or a ref that is not another silver model (blueprint L1, L3) |
| `DUPLICATE_MODEL` | two silver models share a name |
| `MISSING_KEY` | a model has no primary key or names a key column it does not declare (L4) |
| `PII_UNTAGGED` | a staging column reads a policy PII column but has `pii: false` (L6) |
| `KPI_UNKNOWN` / `KPI_MISSING` | a KPI id is not in the catalogue / a catalogue KPI has no decision |
| `MAPPING_INCOMPLETE` | a `build` KPI's mapping leaves a template name unfilled or names an unknown one (uses `catalogue.render`) |
| `MAPPING_UNKNOWN_MODEL` | a relation maps to a name that is not a silver model |
| `MAPPING_UNKNOWN_COLUMN` | an input maps to a column its relation's model does not declare, or an expression reads such a column |
| `DECLINE_WITHOUT_GAP` | a `decline` has no reason or no gap with `missing`, `typical_sources` and `next_step` |

## 7. Design report (`governor/design.md`)

Plain markdown for the design gate, in this order: summary line (silver models, KPIs to build, KPIs declined); a table of silver models (name, folder, from, key, PII columns); a table of KPIs (id, decision, domain, mapping or reason); the gap report (per declined KPI: missing data, typical sources, next step); assumptions; validation findings (empty when valid); and the exact approve and reject commands with the thread id.

## 8. Build graph and CLI

`StateGraph`, code owns every edge, checkpoints in `GOVERNOR_STATE_DIR/build_checkpoints.sqlite`:

```
profile → propose (plan model) → validate ──codes, ≤2──► propose
                                   │ ok
                              write_report → design_gate (interrupt)
        reject + note (once) ◄──────┤ approve
                                    ▼
          record_decisions → write_silver (D4) → dbt_build_silver ──fail──► repair (write model ≤2, then plan model once)
                                                        │ ok                        └─ still failing → escalated
                                                   write_gold (D5) → dbt_build_gold → summarise
```

CLI (each prints one JSON line last):

- `python -m governor.build init --target <dir> --project-name <name>`
- `python -m governor.build profile --schema raw [--policy knowledge/shop/policy.yaml]`
- `python -m governor.build run --target <dir> --project-name <name> [--llm fake:<script.json>|openrouter]` → `{"thread_id", "status": "awaiting_design_approval" | "design_invalid", "report"}`
- `python -m governor.build approve <thread_id> --by <name> [--llm ...]` → D3: `{"status": "design_approved"}`; from D4: `{"status": "built" | "escalated", ...}`
- `python -m governor.build reject <thread_id> --note "<text>" [--llm ...]`

Fake script (`--llm fake:<path>`): `{"propose": ["<proposal json>", ...], "intermediate": {"<model>": ["<sql>", ...]}, "repair": {"<model>": ["<sql>", ...]}}`; lists are consumed in order.

## 9. Silver (D4)

- Staging SQL is generated by code: `select <expr> as <name>, ... from {{ source('raw', '<table>') }}`.
- Intermediate SQL comes from the write model, given the model's description, its refs' declared columns and its own declared columns. Checks before dbt: one SELECT (sqlglot, after replacing Jinja calls), only `{{ ref('<declared ref>') }}`, no DDL or DML, no `source()`.
- `_staging.yml` and `_intermediate.yml`: description, columns, `meta: {pii: true}` on PII columns (L6), `unique` and `not_null` on a single-column key, a singular test in `tests/` for a composite key (L4).
- `dbt build --select staging intermediate` as `governor_build` into `dev_governor`. A failing model gets its error text and SQL back for repair; after the declared columns are checked against `information_schema`, a mismatch is a failure too.

## 10. Gold (D5)

- One model per `build` KPI: `models/marts/<domain>/kpi_<id>.sql` = `catalogue.render(kpi, mapping)` with each relation replaced by `{{ ref('<model>') }}`; materialized as a table.
- `_<domain>.yml`: description = the KPI definition; `meta`: `kpi_id`, `owner`, `source_tier`, `source_ref`, `template_sha256` (of the catalogue template) and `rendered_sha256` (of the model file as written) (L5, L8); `not_null` on the grain column.
- Static blueprint check `gold.check_project(target) -> list[Finding]` over the generated project: L1 folders, L2/L3 refs, L4 key tests, L5 owner and description, L6 PII tags, L7 no PII column in gold, L8 the model file equals a fresh `catalogue.render` from `governor/design.json` and both hashes match, L9 no `CAST`, `::`, `TRIM`, `LOWER`, `UPPER`, `REPLACE` in gold. High findings block the build.
- `governor/gaps.md` from the declined KPIs; `governor/build.json` summary: models, tests passed, KPIs built with row counts, gaps, cost.
