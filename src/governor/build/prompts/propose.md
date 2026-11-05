# Propose the silver layer and the KPI column mapping

You design the silver layer (dbt `staging` and `intermediate` models) of a company's dbt project from a profile of its raw tables, and you decide for every KPI in the catalogue whether it can be built from that silver layer. Code validates your answer, writes the SQL for staging and the gold KPI models, and a human approves the design before anything is built.

## What you get

- **Profile**: the raw tables, their row counts, columns (inferred type, null rate, distinct count, whether the column is PII), candidate keys and relationships between tables. Raw columns are all text; `inferred_type` is what their values look like. Some candidate keys on small data are accidents (timestamps or measures that happen to be unique): prefer `*_id` business keys.
- **Blueprint**: the layer rules the project is held to.
- **Catalogue**: every KPI with its definition, the relations it reads (a relation is a silver model you choose), the inputs it needs from each relation and their types.
- **Approved decisions**: mappings and corrections a human already approved for this company. Follow them unless the profile makes them impossible; say so in `assumptions` when you depart from one.
- On a repair: the findings code raised on your previous proposal, and that proposal. Fix every finding and keep what was right.
- After a rejection: the reviewer's note. Apply it.

## Rules for the silver models

- A **staging** model (`folder: "staging"`, name `stg_<entity>`) reads exactly one raw table: `source_table` is the raw table name and `refs` is `[]`. Each column's `expr` is a Postgres SQL expression over that raw table's columns only (for example `CAST(NULLIF(order_purchase_timestamp, '') AS timestamp)`). Give columns clear names and proper types.
- An **intermediate** model (`folder: "intermediate"`, name `int_<name>`) has `source_table: null` and `refs` naming the silver models it reads. Its columns declare the output with `expr: null`; the SQL is written later from your `description`, so the description must say the grain and how the refs are joined or deduplicated.
- Every model has a `primary_key` made of columns it declares.
- Set `pii: true` on every column that carries a PII column, in staging and wherever it is passed on. Leave out PII columns no KPI or join needs.
- Model names are unique.

## Rules for the KPIs

- Give a decision for **every** catalogue KPI and no others.
- `build`: set `domain` (the gold folder, such as `sales`, `customers`, `delivery`) and `mapping_pairs`: one `{"name": ..., "value": ...}` pair for every relation and every input of the KPI and nothing else (`name` is the relation or input, `value` what it maps to). A relation maps to the name of one of your silver models. A non-boolean input maps to a column that model declares. A `boolean` input maps to a boolean SQL expression over that model's declared columns (for example `is_paid AND NOT is_refunded`).
- `decline` when the raw data cannot support the KPI: give a `reason` and a `gap` with `missing` (the data that is missing), `typical_sources` (where companies usually get it) and `next_step` (what to load so the KPI can be built). Do not invent data that is not in the profile.
- Put every business assumption you made (status values that mean a sale, which key identifies a person, how duplicates are resolved) in `assumptions`.

## Answer

Return one JSON object with exactly these keys, and nothing else:

```json
{"silver_models": [{"name": "", "folder": "staging", "source_table": "", "refs": [], "description": "",
                    "primary_key": [""], "columns": [{"name": "", "expr": "", "type": "", "pii": false, "description": ""}]}],
 "kpis": [{"id": "", "decision": "build", "domain": "", "mapping_pairs": [{"name": "<relation or input>", "value": "<model, column or expression>"}]},
          {"id": "", "decision": "decline", "reason": "", "gap": {"missing": [""], "typical_sources": [""], "next_step": ""}}],
 "assumptions": [""]}
```

## Profile

{{profile}}

## Blueprint

{{blueprint}}

## Catalogue

{{catalogue}}

## Approved decisions

{{approved}}

{{repair}}
