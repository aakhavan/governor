# Tenants

One governor process can serve several companies or datasets. Each one is a **tenant**: its own knowledge folder,
run state, target repository and database. Contract: `docs/capstone/batch3.md` sections 31 and 32; decision:
`docs/adr/0004-maintain-mode-and-tenancy.md`.

Without a registry (`GOVERNOR_TENANTS` unset or empty) governor runs single-tenant exactly as before.

## The registry

`GOVERNOR_TENANTS` names one YAML file:

```yaml
tenants:
  acme:      {root: tenants/acme, target: ../acme-dbt, pg_port: 55432}
  globex-eu: {root: tenants/globex-eu, target: ../globex-dbt, pg_port: 55433, pg_host: localhost, pg_db: shop}
```

| key | required | meaning |
|---|---|---|
| `root` | yes | the folder holding the tenant's `knowledge/` (`kpis.yaml`, `blueprint.md`, `approved.yaml`, `shop/policy.yaml`, `shop/access.yaml`) and its run state (`artifacts/`, with `build_checkpoints.sqlite`) |
| `target` | yes | the tenant's dbt repository |
| `pg_port` | yes | the port of the tenant's database |
| `pg_host` | no (`localhost`) | the host of the tenant's database |
| `pg_db` | no (`shop`) | the database name |

- Relative `root` and `target` resolve against the registry file's folder.
- Names use letters, digits, `_` and `-`. The name is the project name of the tenant's builds; for the dbt project
  name the Slack bot turns `-` into `_` (`globex-eu` becomes `globex_eu`).
- The registry is checked at start: unknown keys, a bad name, a missing `knowledge/kpis.yaml` or
  `knowledge/blueprint.md`, and two tenants sharing a `root`, a `target` or a database (host, port, db) are errors
  that name the tenant. `knowledge/shop/policy.yaml` is not checked here: a tenant without it fails when its run
  profiles the database.

## Use

- CLI: `python -m governor.build run --tenant acme` (also `approve`, `reject`, `publish`, `certify`); `--tenant`
  fills `--target` and `--project-name`, and an explicit `--target` that is not the tenant's is refused.
- Slack: with `GOVERNOR_TENANTS` set, the bot's targets are the tenant names: `/governor run acme`. Approve,
  reject, publish and their buttons find the tenant from the build thread. See `docs/slack.md`.

## Isolation

- A run for tenant A reads only A's knowledge (KPI catalogue, blueprint, approved decisions, policy), writes only
  A's run state and A's target, and connects only to A's database (A's host, port and db; dbt gets A's
  `GOVERNOR_PG_HOST/PORT/DB`).
- Build threads live in each tenant's own checkpoints: a thread started for A is unknown to B. The Slack bot finds a
  thread's tenant from those checkpoints; a short thread id that matches threads in two tenants is a usage error
  naming both, and nothing runs.
- `certify --tenant` refuses an admin DSN (`GOVERNOR_PG_ADMIN_DSN`) for another host, port or database than the
  tenant's.
- Messages name a database only as `host:port/db`; never a user, password or full DSN.

## Limits

- **`ask` is single-tenant.** The certified answer path and its registry serve one tenant only. In multi-tenant mode
  `/governor ask` replies `ask serves one tenant only; it is not available in multi-tenant mode yet` and runs nothing.
- **One Slack workspace.** One bot, one channel (`GOVERNOR_SLACK_CHANNEL`) and one set of runners and approvers for
  every tenant. Anyone allowed to approve can approve for any tenant.
- **Shared role tokens.** The build login (`GOVERNOR_BUILD_USER`, `GOVERNOR_BUILD_PASSWORD`) and the model keys come
  from the process environment and are the same for every tenant; the tenants differ by database address only.
- The build event log (`GOVERNOR_STATE_DIR/events.jsonl`) and the Slack message state are process-wide; they carry
  thread ids, names and counts, never data values. A thread's tenant comes from the checkpoints, not from events.
- No per-tenant roles, no row-level isolation inside one shared database (each tenant has its own database).
