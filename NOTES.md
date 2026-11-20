# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
Run console V5 is in place: tabbed result views under the canvas with SummaryView, LineageView (React Flow), FunnelView and KpiEvidenceView (Recharts), and GuardPathView for ask runs. Captions and empty states come from copy.ts; Vitest covers render, empty state, and captions. Front-end acceptance (lint, typecheck, 27 tests, build) is green on branch factory/V5.

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

## V4 result
*React console with the live run canvas (React Flow), 20 Nov 2026 20:21.*

Implementer `cursor-grok`; reviewers `cursor-composer`: pass; 0 fix loop(s); branch `factory/V4`.

| check | ok | detail |
|---|---|---|
| console dependencies | yes | ok |
| npm scripts | yes | ok |
| apps/console/src/run/fold.ts | yes | missing |
| apps/console/src/graph/RunCanvas.tsx | yes | missing |
| apps/console/src/graph/GovernorNode.tsx | yes | missing |
| apps/console/src/copy.ts | yes | missing |
| apps/console/src/pages/RunsPage.tsx | yes | missing |
| apps/console/src/pages/RunPage.tsx | yes | missing |
| apps/console/src/pages/GraphPage.tsx | yes | missing |
| apps/console/package-lock.json | yes | missing |
| console .gitignore covers node_modules and dist | yes | missing entries |
| fold test reads the shared cases | yes | fold_cases.json not imported in a test |
| required console tests present | yes | 4 found |
| node 20+ on PATH | yes | v24.22.0 |
| npm ci | yes | npm warn install-scripts   esbuild@0.21.5 (postinstall: node install.js) | npm warn install-scripts | npm warn install-s |
| npm run lint | yes | > governor-console@0.0.0 lint | > eslint . |
| npm run typecheck | yes | > governor-console@0.0.0 typecheck | > tsc --noEmit |
| npm test | yes | [2m      Tests [22m [1m[32m19 passed[39m[22m[90m (19)[39m | [2m   Start at [22m 20:20:08 | [2m   Duration [2 |
| npm run build | yes | [2mdist/[22m[35massets/index-DY-1M5sn.css  [39m[1m[2m 25.21 kB[22m[1m[22m[2m │ gzip:   5.03 kB[22m | [2mdist |

Review: V4 delivers the console stack in apps/console/: fold.ts matches all eight fold_cases.json cases; RunCanvas implements §37 node and edge visuals; HeaderEventSource plus useRunEvents dedupe by seq and send Last-Event-ID on reconnect (tested). User strings live in copy.ts; icons are inline SVG. Lint, typecheck, 19 Vitest tests, and build passed per acceptance; no committed secrets.

For Amir: Fold parity and the four required console tests give solid confidence; a quick manual pass with the API in GOVERNOR_CONSOLE_OPEN=1 mode would still validate HeaderEventSource against a real stream.

## V5 result
*Result views (summary, lineage, build funnel, KPI evidence, guard path), 20 Nov 2026 21:00.*

Implementer `cursor-grok`; reviewers `cursor-composer`: pass; 0 fix loop(s); branch `factory/V5`.

| check | ok | detail |
|---|---|---|
| view SummaryView | yes | missing |
| view LineageView | yes | missing |
| view FunnelView | yes | missing |
| view KpiEvidenceView | yes | missing |
| view GuardPathView | yes | missing |
| required console tests present | yes | 7 found |
| node 20+ on PATH | yes | v24.22.0 |
| npm ci | yes | npm warn install-scripts   esbuild@0.21.5 (postinstall: node install.js) | npm warn install-scripts | npm warn install-s |
| npm run lint | yes | > governor-console@0.0.0 lint | > eslint . |
| npm run typecheck | yes | > governor-console@0.0.0 typecheck | > tsc --noEmit |
| npm test | yes | [2m      Tests [22m [1m[32m27 passed[39m[22m[90m (27)[39m | [2m   Start at [22m 20:59:35 | [2m   Duration [2 |
| npm run build | yes | - Using dynamic import() to code-split the application | - Use build.rollupOptions.output.manualChunks to improve chunki |

Review: V5 adds five result views under the run canvas with copy-driven captions, empty states, demo fixtures, and offline Vitest coverage. Build views read artifacts (and summary falls back to folded node summaries); ask guard path reads events plus view. Lineage, funnel, and KPI charts match §38; styles use theme tokens where it matters. Acceptance checks and npm lint/typecheck/test/build all passed.

For Amir: Worth a quick manual flip light/dark on lineage and funnel during the V6 showcase gate; automated tests do not assert theme contrast.

## Additions for the next plan
Multi-tenant Slack: GovernorSlack takes tenant_threads= (callable returning tenant -> thread ids) for tests; config.tenants non-empty switches every path. Notifier gets tenant_of= and records rec['tenant'] from the run_started project name, then from the tenants' checkpoints; every Notifier.reply appends a 'tenant <name>' context block via blocks.with_tenant, so any new reply type gets it for free, but a chat_update that rebuilds blocks must re-apply with_tenant (see _on_published). dbt_project_name(name) in app.py maps '-' to '_' and prefixes a leading digit with 't_'; the build CLI --tenant still hands init_target the raw tenant name, so a hyphenated tenant created from the CLI gets an invalid dbt project name unless Slack created the target first (init_target never overwrites). ask remains single-tenant and is refused before parse_command. The reviewer's pytest invocation was blocked by the permission policy; acceptance reported tests/integrations 46 passed and the full suite 549 passed, 21 skipped.

## Additions for V6
ResultPanel is wired on RunPage (build tabs: summary/lineage/funnel/kpi; ask: guard). Artifacts load only for build graph. V6 Playwright shots need console-build-lineage and console-ask-guard against a demo run with manifest/events; consider toggling theme during screenshot pass since chart theme is untested in Vitest. Fixtures live at tests/fixtures/console/build-full.artifacts.json and ask-repaired.events.json.
