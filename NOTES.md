# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
F5 is implemented and reviewed as pass on branch factory/F5 (uncommitted). core/tenancy.py provides Tenant, load_tenants, tenants_path and TenantError; graph.start/approve/reject accept tenant= and build the graph from tenant_graph_kwargs (catalogue, blueprint, approved defaults, profiler/inspector/row counter bound to tenant.build_dsn(), run_dbt with tenant.dbt_env()) with explicit kwargs winning and checkpoints defaulting to tenant.checkpoints; start swaps the default policy for the tenant's and refuses a foreign target. certify(…, tenant=) checks GOVERNOR_PG_ADMIN_DSN against the tenant's host:port/db first and uses the tenant's kpis, policy and access files with deploy_env(tenant.dbt_env()). CLI --tenant on run/approve/reject/publish/certify fills --target and --project-name and refuses a mismatched --target (exit 2). No module-level path or os.environ is mutated per tenant. Known limits: events stay process-wide; registry does not alias localhost/127.0.0.1 in its shared-database check; policy/access existence is not validated at registry load. Acceptance: tests/core 120 passed, tests/build 197 passed.

## Open questions
- G2b gate review (claude.ai, 22 Oct): golden set fine; but `fixture/build_green.py` stamps as_of from the wall clock (Sprint 4 behaviour), so a rebuild on another day shifts days_outstanding/overdue answers and breaks the golden as_of check. Spec change for G3 (item 0 + locked check): pin as_of in `fixture/AS_OF` = 2026-10-22T14:11:26+00:00. Needs `factory relock` before `approve G2b`.
- `fct_invoices.days_outstanding` follows the spec literally: 0 only when fully paid. Void invoices (416 not paid) therefore show days outstanding. Should void count as 0 / be excluded? (Amir decides; one-line change in the SQL.)
- `as_of` is the build's wall-clock instant (S4 design: source freshness needs `_loaded_at` within 12 h). Data dates are fixed (seed 42) but `days_outstanding` shifts with each rebuild. Pin as_of if golden answers must be stable across rebuilds.
- `governor.core.config` replaces S4 `triage.config`, which was not imported. Values reconstructed: `ALLOWED_MODELS` from the S4 test, MAX_TOKENS 4096 from the llm docstring; `FAST_MODEL` (`openai/gpt-5-nano`) and `EMBED_MODEL` (`openai/text-embedding-3-small`) are guesses, overridable by env. Check before G4/G5 use them.
- `chromadb` is not a dependency (not in the G1 list). `retrieval.build_index/load_index` need it; add it in the step that uses dense retrieval.
- access.yaml: every model and grant name matches the real warehouse (allowlist = the four marts; `dim_accounts.contact_email` exists and is tagged `email`). No renames needed.
- Capstone brief not yet available; PLAN §1 holds the provisional stance (ask = spine, one triage path = stretch).
- G2b gold numbers are frozen against as_of 2026-10-22T14:11:26+00:00 and the current green build. m05, m06 and j04 depend on days_outstanding / paid amounts; a rebuild that moves as_of changes them and the gold must be rechecked (FROZEN hashes cover the files, not the results).
- G2b metric gold (m01-m03) mirrors metrics.yaml and returns (month_start, value). compare needs equal column counts, so a bare number fails these items. Amir: keep (forces the snapshot month to be stated), or drop month_start from the gold?
- Sol suggested comparing column names/types in the checker; kept name-agnostic on purpose (LLM aliases vary; Spider-style execution accuracy), with equal column counts and permutation matching.

- G3: dbt `source freshness` measures `_loaded_at` against the wall clock (DuckDB now()), and `_loaded_at` is now the pinned as_of, so green sources report warn after 12 h and error after 24 h. build_green.py accepts that (status pass/warn/error, 2 results) instead of failing. Side effect: green sources.json / meta.freshness are not "pass", so `lineage.failing_nodes` on the green build would flag the two sources. Clean fix (outside G3 paths): a project macro overriding `collect_freshness` to use `var('as_of')` as snapshotted_at, or `loaded_at_query` in _sources.yml. Amir decides.
- G3: the prompt gave AS_OF as `2026-10-22T14:11:26+00:00`, but the locked check compares against `str()` of the YAML datetime, so fixture/AS_OF and as_of.txt use `2026-10-22 14:11:26+00:00` (same instant; fromisoformat reads both).
- G3: `--llm` defaults to `fake` so nothing spends money by accident; G10 must pass `--llm openrouter`. The report records `llm`.

## F4 result
*Publish against a stale main, nothing to publish, 17 Nov 2026 18:10.*

Implementer `claude-tc-opus`; reviewers `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/F4`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| no empty commits | yes | missing in src/governor/build/publish.py |
| diverged main refused | yes | missing in src/governor/build/publish.py |
| --allow-empty removed | yes | still in src/governor/build/publish.py |
| pytest tests/build | yes | 191 passed, 12 skipped in 84.11s (0:01:24) |
| pytest tests/integrations | yes | 40 passed in 12.75s |
| required tests present | yes | 4 found |

Review: F4 does what section 30 asks. sync_main fetches origin/main before any branch exists, fast-forwards only a main that is behind with no own commits (guarded update-ref), and raises the exact DIVERGED line otherwise with main, origin/main and the working tree untouched. An unchanged build makes no commit, returns to main, deletes the branch and emits no event; --allow-empty is gone. Targets without origin run no sync or push. The four tests use a local bare origin and a clone under tmp_path only; CLI and Slack show a plain message.

For Amir: Two cosmetic items for later: plan/accept/_common.check prints the failure detail string even when ok is true, which makes the acceptance JSON read oddly; and sync_main runs one 'git status' per changed upstream file, so a very large merged PR will be slow but correct. The reviewer could not rerun pytest (command not permitted) and relied on the acceptance output.

## Additions for F5
publish() now runs sync_main(target) before 'checkout -B'. With an origin that has main it does ls-remote + fetch (network) up front, so a stub publisher or a monkeypatched pub.git is the way to keep later tests offline (see test_publish_without_remote_unchanged for the call-log pattern). publish() can return {'status': 'nothing_to_publish', 'reason': 'the build matches main'}: callers must treat it as a non-error (CLI prints 'Nothing to publish: ...' and exits 0; Slack _say's the same). No 'published' event and no .git/governor_published.json write happen in that case, so read_published(target) may still return the previous publish. sync_main is exported in __all__ and returns 'fast_forwarded' or None. Helpers: _generated(path) and ORIGIN_MAIN / DIVERGED constants in publish.py. The status --porcelain loop is per file; fine for now, batch it if a later step touches large upstream merges.

## F5 result
*Tenants (registry, per-tenant build, CLI --tenant), 17 Nov 2026 18:29.*

Implementer `claude-tc-opus`; reviewers `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/F5`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| tenancy module | yes | missing in src/governor/core/tenancy.py |
| graph takes a tenant | yes | missing in src/governor/build/graph.py |
| CLI --tenant | yes | missing in src/governor/build/__main__.py |
| pytest tests/core | yes | 120 passed, 12 skipped in 13.43s |
| pytest tests/build | yes | 197 passed, 12 skipped in 87.99s (0:01:27) |
| required tests present | yes | 8 found |

Review: F5 does what section 31 asks. Tenant is a frozen dataclass with derived paths, build_dsn and dbt_env; load_tenants refuses bad names, unknown keys, missing knowledge files and shared root/target/database. graph.start/approve/reject inject the tenant's catalogue, blueprint, approved defaults, policy, checkpoints, profiler, inspector, row counter and dbt env via build_graph kwargs; no module-level state or os.environ is mutated. certify checks the admin DSN host:port/db before anything runs. CLI --tenant fills target/project name and refuses a foreign target (exit 2). All eight tests present.

For Amir: No code changes needed. Two small inconsistencies worth a later tidy: the registry's duplicate-database check does not treat localhost/127.0.0.1/::1 as one host while certify's admin DSN check does, and the registry validates kpis.yaml and blueprint.md but not shop/policy.yaml or shop/access.yaml, so a tenant missing those fails later with a less helpful error. Events remain process-wide, as NOTES already records for F6.

## Additions for F6
For F6: (1) Use graph.start/approve/reject with tenant=<Tenant>; checkpoints default to tenant.checkpoints (root/artifacts/build_checkpoints.sqlite), so listing threads per tenant means opening each tenant's checkpoint file via graph.open_checkpointer(tenant.checkpoints). (2) Events (events_path) are still process-wide in GOVERNOR_STATE_DIR; map thread ids to tenants via checkpoints, not via events. (3) Tenant.address gives host:port/db for the start-up line and footer; never log build_dsn(). (4) Project name is the tenant name verbatim; names may contain '-', which dbt rejects as a project name, so either restrict names in the registry or map '-' to '_' when calling init_target. (5) load_tenants raises TenantError (a ValueError) naming the tenant; tenants_path() returns None when GOVERNOR_TENANTS is unset or empty. (6) The registry's shared-database check compares host strings lowercased only; certify's admin DSN check treats localhost/127.0.0.1/::1 as one host, so two entries differing only by localhost vs 127.0.0.1 are accepted by the registry. (7) The registry does not check policy.yaml/access.yaml exist; a tenant missing knowledge/shop/policy.yaml fails at profile time with a FileNotFoundError surfaced as 'build run failed'.
