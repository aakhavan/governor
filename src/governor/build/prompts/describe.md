# Describe the columns of one dbt model

You write column descriptions for one model of a company's dbt project (Postgres). Analysts read them in the dbt docs and in the data catalogue. The design was approved by a human; describe what the columns are, from the evidence below only.

## Rules

- Describe **only** the columns listed under "Columns to describe", each in one plain sentence of at most 200 characters.
- Use only the evidence below: the model description, the column lineage, the profile counts, the design assumptions and the descriptions of the refs. Do not invent business meaning the evidence does not support.
- Never write data values (no example ids, names, places, amounts or dates). Say what the column holds, not what is in it.
- A column marked personal data stays described as personal data, hashed for analysts.

## Model `{{model}}` ({{folder}})

{{description}}

Primary key: {{primary_key}}

## Columns

{{columns}}

## Columns to describe

{{empty}}

## Refs (the models this one reads, with their column descriptions)

{{refs}}

## Profile counts (raw tables behind this model; counts only)

{{profile}}

## Design assumptions

{{assumptions}}

## Answer

One JSON object and nothing else: `{"<column>": "<description>", ...}` with exactly the columns to describe.
