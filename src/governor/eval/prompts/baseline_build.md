# One-shot dbt build (baseline)

You are a senior analytics engineer. Write a complete dbt project body for the raw schema below in ONE reply:
the silver models (staging and intermediate) and one gold table per KPI you can build. Nothing will be run, checked
or repaired before the project is built with `dbt build`, so every file must work as written (PostgreSQL).

## Rules

- Read raw tables only through `{{ source('raw', '<table>') }}`; read your own models through `{{ ref('<model>') }}`.
- Staging models go in `models/staging/`, intermediate models in `models/intermediate/`, gold tables in
  `models/marts/`. Optional tests (`schema.yml` files or singular `.sql` tests) go under `models/` or `tests/`.
- Each gold table is `models/marts/kpi_<kpi id>.sql` and returns exactly the output columns listed for that KPI
  under `output_columns` (same names; the time column first).
- Build a KPI only when the profile holds the data its definition needs. When it does not, write no file for it.
- Respect the blueprint layers and rules below. Columns marked `pii` must not reach a gold table.
- Raw columns may be stored as text: cast them explicitly (timestamps, numbers).
- Paths are relative to the project root and must start with `models/` or `tests/`.

## Reply format

Reply with JSON only, no prose:

```json
{"files": [{"path": "models/staging/stg_example.sql", "content": "select ..."}]}
```

## Raw schema profile

{{profile}}

## Blueprint

{{blueprint}}

## KPI definitions

{{kpis}}
