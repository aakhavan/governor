# Write the SQL of one intermediate dbt model

You write the SQL of one model in the `intermediate` folder of a company's silver layer (dbt on Postgres). The design was approved by a human; follow it exactly. Code checks your SQL and dbt builds and tests it.

## Rules

- Return **one** Postgres `SELECT` statement (a `WITH ... SELECT` is fine) and nothing else: no DDL, no DML, no `;`, no comments outside the SQL.
- Read other models only through `{{ ref('<model>') }}`, and only the refs listed below. Never use `source()` or any other Jinja.
- Select **exactly** the declared columns below, with those names (alias every expression), in that order. Their types are already right in the refs; do not cast unless the declared type differs.
- The result must have one row per primary key value: join and deduplicate as the description says (for example `row_number()` over the key, keeping the row the description names).

## Model `{{model}}`

{{description}}

Primary key: {{primary_key}}

Declared columns:

{{columns}}

## Refs (the models you may read and their columns)

{{refs}}

## Answer

The SQL only, in one ```sql block.
