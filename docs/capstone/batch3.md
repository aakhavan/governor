# Batch 3: maintain mode and tenants (F1–F6)

Agreed 17 Nov 2026, after submission. Decision record: [`docs/adr/0004-maintain-mode-and-tenancy.md`](../adr/0004-maintain-mode-and-tenancy.md). Plan: `plan-batch3.yaml`, run on branch `batch3`. Sections continue the numbering of `batch2d.md`.

Two features, in that order:

1. **Maintain mode.** A run on a target whose raw schema has not changed since its last approved, built design ends as `up_to_date` with no model call and no dbt run. A run on a changed schema reports the drift and gives the planner the last approved design to adapt, instead of designing from nothing. Publishing is safe against a stale `main` and never makes an empty commit.
2. **Tenants.** One governor process serves several companies or datasets, each with its own knowledge folder, run state, database and target repository, and none of them can read another's.

Rules for every step:

- No behaviour changes when the new features are not used: no tenant registry means today's single-tenant behaviour, a target without a fingerprint runs as today. Every existing test stays green and unchanged unless this contract names it.
- No data values anywhere new: fingerprints, drift reports, events, Slack messages and prompts carry table and column names, types and counts of changes, never row values, min, max or sample values.
- Code owns every edge. Nothing here gives the model a new decision.
- The frozen capstone ground truth (`evaluation/`) is untouched.

---

## 27. Safety rails (F1)

**Why.** On 17 Nov a database container came up without its port, and the bot waited forever at profiling with no message. A second cause of confusion was that the bot never said which knowledge folder and database it was serving.

1. **Connection timeout.** A helper `src/governor/core/pgconn.py`: `connect_timeout_s()` returns `GOVERNOR_PG_CONNECT_TIMEOUT` as an int (default 10, minimum 1) and `with_timeout(dsn: str) -> str` returns the DSN with `connect_timeout` set when the DSN does not already set one (use `psycopg.conninfo.make_conninfo`; works for both URI and key-value DSNs). Apply it to `workspace.build_dsn()`, to every `psycopg.connect(...)` under `src/governor/build/` and `src/governor/core/serving.py`, and add `connect_timeout` to the dbt profile template written by `init_target` (dbt-postgres supports it). `src/governor/eval/` stays untouched.
2. **Start-up line.** `python -m governor.integrations.slack` prints one line before connecting: channel, targets, the knowledge folder (`paths.KNOWLEDGE`) and the build database as `host:port/db`. Never a user name, password or full DSN.
3. **Usage footer.** The usage text (`/governor` with no or a wrong command) ends with `workspace: knowledge <folder name> · database <host>:<port>/<db>`.

Tests (`tests/core/`, `tests/integrations/`):
`test_with_timeout_adds_connect_timeout_once` (URI and key-value DSNs; an existing `connect_timeout` is kept) ·
`test_build_dsn_has_connect_timeout` ·
`test_unreachable_database_fails_within_timeout` (a local socket that listens but never answers; `profile_schema` with `GOVERNOR_PG_CONNECT_TIMEOUT=2` raises within 10 s; offline, no Postgres) ·
`test_dbt_profile_template_has_connect_timeout` ·
`test_start_line_names_workspace_without_secrets` ·
`test_usage_footer_names_workspace`.

## 28. Profile fingerprint and drift (F2)

**Why.** To know whether a rerun has anything to do, governor needs a stable description of the raw schema at the time a design was approved, and a way to compare two of them.

1. `src/governor/build/drift.py`:
   - `fingerprint(profile) -> dict`: `{"version": 1, "schema": …, "tables": {table: {"columns": {column: {"type": inferred_type, "pii": bool}}, "candidate_keys": [[…]]}}}` with tables, columns and keys sorted. Only names, `inferred_type`, `pii` and `candidate_keys`; never `rows`, `null_rate`, `distinct`, `min`, `max` or relationships' coverage.
   - `fingerprint_hash(fp) -> str`: sha256 of the canonical JSON (sorted keys, no whitespace).
   - `diff(old, new) -> Drift`, a Pydantic model: `tables_added`, `tables_removed`, `columns_added` (table → columns), `columns_removed`, `type_changes` (table → column → [old, new]), `pii_changes` (table → columns), `keys_changed` (tables). `Drift.empty` and `Drift.summary_lines()` (one plain line per change, names only, sorted).
2. On approval (the `record_decisions` node of the build graph), write `<target>/governor/profile_fingerprint.json`: `{"thread_id", "approved_on", "hash", "fingerprint"}`, next to `approved.yaml`. Add it to the files `publish` commits (`GENERATED` in `publish.py`).

Tests (`tests/build/`):
`test_fingerprint_has_no_counts_or_values` ·
`test_fingerprint_is_stable_across_order` (shuffled tables, columns and keys give the same hash) ·
`test_diff_empty_for_same_profile` ·
`test_diff_reports_added_and_removed` ·
`test_diff_reports_type_pii_and_key_changes` ·
`test_approval_writes_fingerprint`.

## 29. Up-to-date runs and drift-aware design (F3)

**Why.** Today every run rebuilds from raw: about four minutes and a planner call even when nothing changed. This is the idempotency fix, and the first half of maintain mode.

1. **A `compare` node** between `profile` and `propose`. A run is **up to date** when all of these hold, and `force` is not set:
   - `<target>/governor/profile_fingerprint.json` exists and its `hash` equals the hash of the current profile;
   - `<target>/governor/build.json` has `status: built` and the same `thread_id` as the fingerprint;
   - `<target>/governor/design.json` exists.

   Then the run writes `<target>/governor/drift.md` (`No change in the raw schema since build <id8>, approved on <date>.`), sets status `up_to_date`, emits event `up_to_date` (`thread_id`, `last_build`), and ends. No model call, no dbt run, no file in `models/` touched.
2. **Drift.** When a fingerprint exists and the hash differs, the run goes on to `propose` with:
   - `previous` = the last approved design (`<target>/governor/design.json`);
   - `note` = `The raw schema changed since the last approved build:` + `Drift.summary_lines()` + `Keep every unchanged model and KPI mapping; change only what these differences require.`

   The design report (`design.md`) gets a section `## Drift since the last approved build` with the same lines, and `drift.md` holds them too. Validation, gates and repairs are unchanged. The first proposal of a drift run counts as a normal proposal, not a repair.
3. **No fingerprint** (first run, or a target built before this batch): today's behaviour, unchanged.
4. **`force`.** `graph.start(..., force=False)`; CLI `run --force`; Slack `/governor run <target> force` (the literal word `force` as an optional second argument; anything else stays a usage error). `force` skips only the up-to-date check.
5. **Slack.** `up_to_date` is a terminal state in the notifier: `:white_check_mark: up to date: no change since build <id8>`, no buttons, no thread replies beyond that line.

Tests (`tests/build/`, `tests/integrations/`):
`test_unchanged_target_is_up_to_date_without_model_calls` (the fake LLM has an empty script and records zero calls; no dbt call) ·
`test_failed_last_build_is_not_up_to_date` ·
`test_force_runs_full_design` ·
`test_drift_passes_previous_design_and_note` (the prompt holds the last design and the drift lines) ·
`test_design_report_lists_drift` ·
`test_target_without_fingerprint_runs_as_before` ·
`test_slack_run_force_parses` ·
`test_slack_up_to_date_message`.

## 30. Publish against a stale main (F4)

**Why.** On 17 Nov a local `main` that missed a merged pull request produced a build branch that conflicted in every generated file. A run that changed nothing also made an empty commit (`--allow-empty`).

1. Before branching, when the target has an `origin`: `git fetch origin main`. If local `main` is behind `origin/main` and has no commits of its own, fast-forward it. If it has commits of its own (diverged), raise `PublishError` with one line: `local main has diverged from origin/main; pull and resolve, then publish again`. Nothing is committed or pushed.
2. After staging the generated files on the build branch: when nothing differs from `main`, do not commit. Return to `main`, delete the build branch, and return `{"status": "nothing_to_publish", "reason": "the build matches main"}`. Drop `--allow-empty`.
3. Slack and CLI show `nothing_to_publish` as a plain message, not an error.

Tests (`tests/build/`, with a local bare repository as `origin`, offline):
`test_publish_fast_forwards_stale_main` ·
`test_publish_refuses_diverged_main` ·
`test_publish_with_no_changes_is_nothing_to_publish` ·
`test_publish_without_remote_unchanged`.

## 31. Tenants (F5)

**Why.** Knowledge, run state and the database are process-wide today (`GOVERNOR_ROOT`, `GOVERNOR_PG_PORT`), so serving a second dataset means a second terminal and a second bot, and a mixed-up terminal can build one company's raw data with another's KPIs. A tenant makes that boundary explicit.

1. **Registry.** `src/governor/core/tenancy.py`:
   - `Tenant`, a frozen dataclass: `name`, `root` (folder holding `knowledge/`), `target` (the dbt repository), `pg_host` (default `localhost`), `pg_port`, `pg_db` (default `shop`).
   - Derived paths: `knowledge`, `kpis_path`, `blueprint_path`, `approved_default` (`knowledge/approved.yaml`), `policy_path` and `access_path` (`knowledge/shop/…`), `state_dir` (`root/artifacts`), `checkpoints` (inside `state_dir`, same file name as today).
   - `build_dsn()`: the build login from env (`GOVERNOR_BUILD_USER`, `GOVERNOR_BUILD_PASSWORD`, today's defaults) with the tenant's host, port and database, through `with_timeout`. `dbt_env()`: the caller's env plus `GOVERNOR_PG_HOST/PORT/DB` of the tenant.
   - `load_tenants(path) -> dict[str, Tenant]` from YAML `tenants: {<name>: {root, target, pg_port, pg_host?, pg_db?}}`. Relative paths resolve against the registry file's folder. Names match `[A-Za-z0-9_-]+`. Errors name the tenant and the problem: unknown key, bad name, missing `knowledge/kpis.yaml` or `knowledge/blueprint.md`, two tenants sharing a `root`, `target` or `(host, port, db)`.
   - `tenants_path()` reads `GOVERNOR_TENANTS`; unset means no registry.
2. **Build.** `graph.start`, `graph.approve`, `graph.reject` take `tenant: Tenant | None = None`. With a tenant, the graph uses its catalogue, blueprint, default approved decisions, policy and checkpoints, a profiler bound to `tenant.build_dsn()`, and dbt with `tenant.dbt_env()`. Without one, nothing changes. The module-level `DEFAULT_*` constants stay for the no-tenant path.
3. **CLI.** `--tenant <name>` on `run`, `approve`, `reject`, `publish` and `certify`, requiring `GOVERNOR_TENANTS`. `--tenant` supplies `--target` and `--project-name` (the tenant name) when they are not given; an explicit `--target` that differs from the tenant's is an error. `certify --tenant` uses the tenant's knowledge, and refuses when `GOVERNOR_PG_ADMIN_DSN` points at another host, port or database than the tenant's.
4. **Isolation is the point.** A run for tenant A never reads B's knowledge, writes to B's state or target, or connects to B's database.

Tests (`tests/core/`, `tests/build/`):
`test_tenant_paths_resolve_relative_to_registry` ·
`test_tenant_registry_rejects_bad_entries` (bad name, unknown key, missing knowledge, shared root, shared database) ·
`test_run_for_tenant_uses_only_its_knowledge` (two tenants with different KPI ids; the captured planner prompt holds A's ids and none of B's) ·
`test_run_for_tenant_profiles_its_own_database` (the profiler receives A's host, port and database) ·
`test_tenant_checkpoints_are_separate` (a thread started for A is unknown to B) ·
`test_no_tenant_behaviour_unchanged` ·
`test_cli_tenant_fills_target_and_refuses_mismatch` ·
`test_certify_refuses_admin_dsn_of_another_tenant`.

## 32. One Slack bot for several tenants (F6)

1. With `GOVERNOR_TENANTS` set, the bot's targets are the tenant names, and each `/governor run <name>` goes to that tenant. `GOVERNOR_SLACK_TARGETS` is then ignored, with a warning at start-up. Without it, nothing changes.
2. Approve, reject, publish and their buttons find the tenant from the thread id: the bot lists threads per tenant (each tenant's checkpoints). A short thread id that matches threads in two tenants is a usage error that names both tenants.
3. Progress messages, design cards and replies name the tenant. The start-up line and the usage footer list each tenant as `<name>: <host>:<port>/<db>`.
4. `/governor ask` stays single-tenant in this batch: with `GOVERNOR_TENANTS` set, it replies ephemerally `ask serves one tenant only; it is not available in multi-tenant mode yet` and runs nothing.
5. `docs/tenants.md`: the registry format, one example with two tenants, the isolation rules and the limits (ask is single-tenant; one Slack workspace; shared role tokens).

Tests (`tests/integrations/`):
`test_targets_come_from_tenant_registry` ·
`test_run_routes_to_its_tenant` ·
`test_approve_resolves_tenant_from_thread` ·
`test_thread_in_two_tenants_is_a_usage_error` ·
`test_ask_refused_in_multi_tenant_mode` ·
`test_messages_name_the_tenant` ·
plus the whole suite green.

---

## Out of scope for batch 3

User accounts and per-user roles, rate limiting, a hosted control plane, multi-tenant `ask` and certified registry, Postgres row-level isolation inside one shared database, and incremental model-level rebuilds (rebuilding only the changed models: the drift-aware design already keeps unchanged models identical, so dbt's own state is the next step).
