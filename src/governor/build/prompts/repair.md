# Repair the SQL of one dbt model

The SQL of one silver model (dbt on Postgres) failed: code refused it before dbt, dbt could not build it, one of its key tests failed, or the built columns differ from the design. Rewrite it so it builds, passes its tests and returns exactly the declared columns.

## Rules

- Return **one** Postgres `SELECT` statement (a `WITH ... SELECT` is fine) and nothing else: no DDL, no DML, no `;`.
- A staging model reads only `{{ source('raw', '<its raw table>') }}`. An intermediate model reads only `{{ ref('<model>') }}` for the refs listed below, never `source()`. No other Jinja.
- Select **exactly** the declared columns, with those names, in that order.
- The result must have one row per primary key value.
- Use only column names that the refs below declare (or, for staging, that the error shows the raw table has).

## Model `{{model}}` ({{folder}})

{{description}}

Primary key: {{primary_key}}

Declared columns:

{{columns}}

## Refs

{{refs}}

## The SQL that failed

```sql
{{sql}}
```

## The error

```
{{error}}
```

## Answer

The corrected SQL only, in one ```sql block.
