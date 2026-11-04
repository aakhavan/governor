---
version: 1
layers:
  bronze:
    description: Raw loaded tables, unchanged.
    dbt: [sources]
  silver:
    description: Cleaned, typed and deduplicated data, with at least one non-aggregated version of each record.
    dbt: [staging, intermediate]
  gold:
    description: Business-level models, organised by domain.
    dbt: [marts]
rules:
  - id: L1
    severity: high
    text: Every model belongs to one layer.
  - id: L2
    severity: high
    text: Gold reads only silver or gold.
  - id: L3
    severity: high
    text: Silver reads only bronze or silver.
  - id: L4
    severity: high
    text: Every silver primary key has unique and not_null tests.
  - id: L5
    severity: medium
    text: Every gold model has an owner and a description.
  - id: L6
    severity: high
    text: PII columns are tagged in silver.
  - id: L7
    severity: high
    text: PII is excluded or masked in gold.
  - id: L8
    severity: high
    text: Every gold KPI metric matches its catalogue template.
  - id: L9
    severity: low
    text: No type casts or string cleaning in gold.
exceptions: []
---

# Layer blueprint

This file is the standard a data platform is held to when governor builds it or assesses it. The block at the top is read by code; this text explains it. Change it only through a reviewed pull request. A company can map the layers to different dbt folders and add named exceptions.

## Layers

- **Bronze** is the data as it arrived. In dbt these are the declared sources. Nothing is renamed, retyped or removed, so every later step can be traced back to what was loaded.
- **Silver** is the data made fit to use: columns get clear names and proper types, duplicates are removed, and bad values are handled. In dbt this is the `staging` and `intermediate` folders. Silver keeps at least one version of each record that is not summed up, so any figure can be broken back down to rows.
- **Gold** is what the business reads: facts, dimensions and KPI metrics, grouped by domain (sales, customers, delivery and so on). In dbt this is the `marts` folder.

## Rules

Severity says how much a broken rule matters: **high** means the layer cannot be trusted until it is fixed, **medium** means it should be fixed soon, **low** is a clean-up.

- **L1 (high): every model belongs to one layer.** Each model sits in exactly one of the folders above, so it is always clear what a model is for.
- **L2 (high): gold reads only silver or gold.** Business models never read raw tables directly; they use the cleaned versions, so cleaning is done once.
- **L3 (high): silver reads only bronze or silver.** Cleaning steps never depend on business models, so data flows one way.
- **L4 (high): every silver primary key has `unique` and `not_null` tests.** If a key can repeat or be empty, every count and join built on it can be wrong.
- **L5 (medium): every gold model has an owner and a description.** Someone answers for each business model, and anyone can read what it means.
- **L6 (high): PII columns are tagged in silver.** Personal data (names, emails, addresses and the like) is marked where it is cleaned, so later layers know to protect it.
- **L7 (high): PII is excluded or masked in gold.** Business models either leave personal data out or show it masked or hashed.
- **L8 (high): every gold KPI metric matches its catalogue template.** A KPI in gold is computed the way the KPI catalogue defines it, with only the column mapping changed for this company.
- **L9 (low): no type casts or string cleaning in gold.** Fixing types and text belongs in silver; if gold has to do it, silver is missing a step.

## Exceptions

An exception lets one model break one rule on purpose. Each one names the rule, the model (target), the reason and the owner who accepted it. The list starts empty.
