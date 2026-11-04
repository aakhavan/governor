# Capstone design (C steps)

Agreed with Amir on 2 Nov 2026 in a design review. Product name to be decided (working name Goldsmith); the code name stays `governor` until the name is final, so there is one rename, later. Vocabulary: `CONTEXT.md`. Decisions with trade-offs: `docs/adr/`.

## 1. What the capstone proves

Starting from raw e-commerce data, governor designs and builds the medallion and KPI layer in dbt under two human approvals, declines what the data cannot support, and answers questions only from KPIs it has certified. Measured against a one-shot baseline.

## 2. Scope

- **In:** Olist test bed in Postgres (Docker); build mode (profile raw tables, propose a design against the layer blueprint, write the dbt project: silver written by the agent under checks, gold KPIs generated from catalogue templates); design gate and review gate; approved-decisions memory; ask with the certified path on the shop and the existing DuckDB billing mart; warehouse adapters (DuckDB, Postgres); per-role serving schemas; attack test set as a release gate; deployment on one VM with Docker Compose; Streamlit as a thin client.
- **Stretch, after the 8 Nov gate, in order:** KPI research agent (web, primary sources, Amir approves each definition); Superset dashboards from certified KPIs; an Airflow module.
- **Out until after 19 Nov:** check mode on messy platforms, extract/load triage adapters, BigQuery and Redshift adapters, catalog connectors, Drive/Confluence connectors, A2A, ML pipelines.
- **Batch 1 (C1-C6, this spec):** follow-ups, adapter seam, test bed, Postgres adapter and roles, serving schemas, catalogue and blueprint formats. **Batch 2** (specced after the KPI research and Amir's approval of definitions): profiling, design proposal and design gate, silver writer, gold from templates, dbt build/test/repair in the dev schema, branch and pull request, build evaluation, ask certified path and shop golden set, attack set, deployment.

## 3. Warehouse adapter contract (C2, C4)

```python
class WarehouseAdapter(Protocol):
    name: str        # "duckdb" | "postgres"
    dialect: str     # sqlglot dialect used by the validator
    def dry_run(self, sql: str, *, timeout_s: float) -> DryRun: ...          # DryRun(ok, error)
    def run(self, sql: str, *, timeout_s: float, row_cap: int) -> tuple[list[str], list[list[Any]]]: ...
    def list_columns(self, schemas: list[str] | None = None) -> list[ColumnInfo]: ...  # from information_schema
    def close(self) -> None: ...
```

- `ColumnInfo(schema, table, column, data_type)`; `DryRun(ok, error)`.
- `get_adapter(name: str | None = None, **options)` in `governor.core.adapters`; options pass to the adapter (for Postgres: `allowed_roles`); the name defaults to env `GOVERNOR_WAREHOUSE` (default `duckdb`). Connection settings come from env only (`GOVERNOR_PG_DSN` for Postgres); never from files in the repo.
- Every adapter raises the existing `QueryTimeout` and `QueryError`; every connection used for ask is read-only, has a statement timeout and is closed after use. Values returned by `run` are JSON-safe (Decimal and dates become strings).
- governor's own stores (`meta.duckdb`, `traces.duckdb`, `checkpoints.sqlite`) are not warehouses and do not go through the adapter.
- One conformance suite, parametrised by adapter: `tests/core/test_adapter_conformance.py`. Postgres cases skip when `GOVERNOR_PG_DSN` is unset.

## 4. Test bed (C3, C4)

- `testbed/docker-compose.yml`: Postgres 16, host port 55432, named volume, healthcheck, database `shop`, admin user `governor_admin`, password `${GOVERNOR_PG_PASSWORD:-governor_local}` (the local default is for the laptop test bed only; deployment sets its own).
- Schemas: `raw` (Olist tables, original column names plus `_loaded_at`), `dev_governor` (agent builds, batch 2), `analytics` (production dbt output, batch 2), `serve_<role>` (serving views, C5), `private` (salt, admin only).
- `testbed/load_olist.py --source <dir>`: validates headers against the expected Olist files, loads the 9 CSVs into `raw` with COPY in one transaction per table (truncate and load, so reruns are idempotent), prints row counts as one JSON line.
- `testbed/sample/`: hand-made synthetic CSVs with the exact Olist headers, at most 30 rows per file, clearly synthetic values, with these edge cases: one `customer_unique_id` with two `customer_id`s; a `canceled` order; an order with two reviews; an order delivered after its estimated date; an order with two payments. Tests and acceptance use the sample; the real dataset lives in `testbed/data/` (git-ignored) and is never committed.
- Expected files and headers (as published by Olist; the loader checks them, including the original spelling `product_name_lenght`):
  - `olist_customers_dataset.csv`: customer_id, customer_unique_id, customer_zip_code_prefix, customer_city, customer_state
  - `olist_geolocation_dataset.csv`: geolocation_zip_code_prefix, geolocation_lat, geolocation_lng, geolocation_city, geolocation_state
  - `olist_order_items_dataset.csv`: order_id, order_item_id, product_id, seller_id, shipping_limit_date, price, freight_value
  - `olist_order_payments_dataset.csv`: order_id, payment_sequential, payment_type, payment_installments, payment_value
  - `olist_order_reviews_dataset.csv`: review_id, order_id, review_score, review_comment_title, review_comment_message, review_creation_date, review_answer_timestamp
  - `olist_orders_dataset.csv`: order_id, customer_id, order_status, order_purchase_timestamp, order_approved_at, order_delivered_carrier_date, order_delivered_customer_date, order_estimated_delivery_date
  - `olist_products_dataset.csv`: product_id, product_category_name, product_name_lenght, product_description_lenght, product_photos_qty, product_weight_g, product_length_cm, product_height_cm, product_width_cm
  - `olist_sellers_dataset.csv`: seller_id, seller_zip_code_prefix, seller_city, seller_state
  - `product_category_name_translation.csv`: product_category_name, product_category_name_english
- Database roles (`testbed/sql/roles.sql`, applied by the admin): `governor_ask` (LOGIN, `default_transaction_read_only = on`, `statement_timeout = '10s'`, member of the reader roles, no direct grants); reader roles `governor_analyst` and `governor_finance_admin` (NOLOGIN, USAGE and SELECT only on their own `serve_<role>` schema); `governor_build` (LOGIN, CREATE only on `dev_governor`, for batch 2). Login passwords from env (`GOVERNOR_ASK_PASSWORD`, `GOVERNOR_BUILD_PASSWORD`; test-bed defaults `governor_ask_local` and `governor_build_local`, never used in deployment). The app runs `SET ROLE governor_<role>` per request, with the role taken from the token.

## 5. Serving schemas (C5)

- `python -m governor.core.serving apply --source <schema> --policy <file>` generates, for each table in the source schema, one view per role in `serve_<role>`, then grants each reader role SELECT on its own schema only.
- analyst: PII columns become `encode(sha256(convert_to(salt || value, 'UTF8')), 'hex')`, so equality and `COUNT(DISTINCT ...)` still work but raw values do not exist in the view. The salt lives in `private.pii_salt` (admin only; set from env `GOVERNOR_PII_SALT`); views read it with the view owner's rights, and the salt value never appears in a view definition.
- finance_admin: PII columns become the mask value unless the access file grants the column.
- The policy file uses the same flat format as `knowledge/policy.yaml` (column name to PII tag, applied to every table that has that column); finance grants use `table.column` as in `knowledge/access.yaml`; the shop's real policy is human-owned and written after C5; tests and acceptance use their own fixtures.
- The validator runs unchanged in the adapter's dialect: one statement, SELECT/WITH only, default-deny relations (schema-qualified serving views), no `SELECT *`, no wall-clock functions, LIMIT injected or capped. On Postgres the database is the PII boundary in batch 1; validator PII lineage on the shop follows in batch 2 once the gold layer and its harvest exist.

## 6. KPI catalogue format (C6)

`knowledge/kpis.yaml`, human-owned once C6 is approved. Only Amir sets `status: approved`.

```yaml
version: 1
kpis:
  - id: aov
    label: Average order value
    status: proposed            # proposed | approved
    definition: >-
      Item value of valid orders divided by the number of valid orders, per month.
    grain: month                # month | customer | cohort_month | total
    relations:
      orders: {description: one row per order}
    inputs:
      order_id:    {relation: orders, type: key}
      order_value: {relation: orders, type: money, description: item price, freight excluded}
      order_date:  {relation: orders, type: timestamp}
      valid_order: {relation: orders, type: boolean, description: the order counts as a sale}
    template_sql: |
      SELECT date_trunc('month', {order_date}) AS month,
             SUM({order_value}) / COUNT(DISTINCT {order_id}) AS aov
      FROM {orders}
      WHERE {valid_order}
      GROUP BY 1
    requires: [orders]          # data the KPI needs; a missing relation makes it not buildable
    prerequisites: []           # tests that must pass first, e.g. customer_key_unique
    sources: []                 # citation URLs for the definition
```

Validation: every `{placeholder}` in `template_sql` is a declared relation or input; every input names a declared relation; `id` is unique; `status` is one of the two values.

## 7. Layer blueprint format (C6)

`knowledge/blueprint.md`: YAML front matter (machine-readable) followed by prose that explains the rules. Human-owned once C6 is approved.

- `layers`: bronze = dbt sources (raw loaded tables, unchanged); silver = staging and intermediate (cleaned, typed, deduplicated, at least one non-aggregated version of each record); gold = marts (business-level, by domain). A company can override the mapping.
- `rules` (id, severity, text): L1 every model belongs to one layer (high); L2 gold reads only silver or gold (high); L3 silver reads only bronze or silver (high); L4 every silver primary key has unique and not_null tests (high); L5 every gold model has an owner and a description (medium); L6 PII columns are tagged in silver (high); L7 PII is excluded or masked in gold (high); L8 every gold KPI metric matches its catalogue template (high); L9 no type casts or string cleaning in gold (low).
- `exceptions`: list of {rule, target, reason, owner}; empty at the start.

## 8. Approved decisions (memory) format (C6)

`knowledge/approved.yaml`, changed only through reviewed pull requests.

```yaml
version: 1
decisions:
  - id: map-customer-key
    kind: column_mapping        # column_mapping | blueprint_exception | correction
    subject: kpi.repeat_purchase_rate.customer_key
    value: raw.olist_customers_dataset.customer_unique_id
    reason: customer_id is created per order
    approved_by: amir
    approved_on: 2026-11-05
    source: <branch or pull request>
```

## 9. Working alongside a separately polished ask

ask may be polished in another session. That work happens on its own branch and keeps three contracts: the adapter (section 3), the serving schemas and roles (sections 4 and 5), and the KPI catalogue (section 6). ask never imports from the build module, and the build module never imports from ask.

## 10. UI

Every UI is a thin client of the FastAPI app. No business logic in Streamlit pages, so the UI can be replaced (for example by a React or Next.js front end) without touching the backend.

## 11. Batch 2

Build mode (D steps) is specified in `docs/capstone/batch2.md`, agreed on 4 Nov 2026.
