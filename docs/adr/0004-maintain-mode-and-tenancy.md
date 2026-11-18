# ADR 0004: Maintain mode by profile fingerprint, and tenants as folders

- Status: proposed (17 Nov 2026), to be accepted when batch 3 is merged
- Contract: [`docs/capstone/batch3.md`](../capstone/batch3.md) sections 27–32

## Context

Build mode rebuilds from raw on every run. That is safe, because nothing reaches a stakeholder without a design approval, a merged pull request and certification, but it is not idempotent: an unchanged dataset still costs a planner call (1–2 minutes) and a full dbt build, and a rerun can propose a slightly different design for the same data.

governor also serves one dataset per process. Knowledge, run state and the database come from process-wide settings (`GOVERNOR_ROOT`, `GOVERNOR_PG_PORT`), so a second dataset needs a second terminal and a second bot, and a terminal with the wrong settings can build one company's data with another's KPIs (seen on 17 Nov).

## Decision

1. **Idempotency by fingerprint.** At approval, governor stores a fingerprint of the raw schema: table and column names, inferred types, PII flags and candidate keys, never counts or values. A later run whose fingerprint matches the last approved, built design ends as `up_to_date`, with no model call and no dbt run. `force` overrides it.
2. **Change by diff, not from scratch.** When the fingerprint differs, the planner gets the last approved design and a list of the differences, with the instruction to change only what the differences require. The gates are unchanged: a person still approves the new design and merges the pull request.
3. **Tenants are folders plus a database.** A tenant is a root folder (knowledge and run state), a target repository and a database address, listed in one registry file. Code passes the tenant explicitly through the build; nothing reads another tenant's settings. Without a registry, governor behaves exactly as before.

## Options considered

| Option | Why not, for now |
|---|---|
| Rebuild only changed dbt models (dbt state comparison) | Needs a stable design first; the drift-aware design keeps unchanged models identical, so this becomes possible next |
| Hash the whole profile, counts included | Every new order would count as a change; the schema is what decides whether the design must change |
| Detect changes with a model call | Adds a model decision where a deterministic comparison is exact |
| One shared database with row-level security per tenant | Stronger isolation needs more work in roles and serving views; separate databases per tenant are simpler and already safe |
| A hosted control plane with accounts | Product work, not needed for a pilot with one or a few teams |

## Consequences

- An unchanged rerun costs no model tokens and no dbt time; a changed one costs one planner call, as today.
- Data changes inside an unchanged schema (new rows) do not trigger a redesign, which is intended: dbt models rebuilt on a schedule handle new rows. Value-level drift (a new status value, a changed date format) is not detected yet.
- `ask` and the certified registry stay single-tenant until a later batch.
