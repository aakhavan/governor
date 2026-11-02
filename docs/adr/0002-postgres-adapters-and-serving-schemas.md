# Postgres test bed behind warehouse adapters, with per-role serving schemas

DuckDB has no database roles or grants, so every guarantee lived in governor's own validator. The test bed moves to Postgres, where each role queries only its own serving schema (personal data hashed for analysts, masked for finance) through a read-only login with a statement timeout, so a validator bug cannot leak data. Warehouses sit behind an adapter (DuckDB and Postgres now; BigQuery and Redshift later), and the DuckDB billing mart stays so the existing evaluation remains valid.

## Considered Options

- Validator-only enforcement, stated in the README: rejected, one bug would be a leak.
- Migrating everything to Postgres: rejected, it would invalidate the frozen billing evaluation and leave one adapter instead of two.
