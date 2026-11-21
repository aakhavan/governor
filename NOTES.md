# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
The run console SPA is feature-complete for batch 4: API routes, replay UI, tests, and docs. V6 packages it for compose (console on 8080), documents dev/Docker/replay/Studio in docs/console.md, adds a README showcase blurb, and commits four Playwright-generated screenshots under docs/showcase/. Full Python suite and console lint/typecheck/test/build pass per acceptance.

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

## V6 result
*Docker, screenshots, docs and README (showcase), 21 Nov 2026 16:33.*

Implementer `cursor-grok`; reviewers `cursor-composer`: pass; 0 fix loop(s); branch `factory/V6`.

| check | ok | detail |
|---|---|---|
| compose console service | yes | missing console service on 8080 |
| compose keeps console closed by default | yes | open mode set by default |
| console Dockerfile | yes | missing |
| nginx config | yes | missing |
| docs/console.md | yes | missing or incomplete |
| README run console section | yes | missing |
| screenshot script | yes | missing |
| node 20+ on PATH | yes | v24.22.0 |
| npm ci | yes | npm warn install-scripts   esbuild@0.21.5 (postinstall: node install.js) | npm warn install-scripts | npm warn install-s |
| npm run lint | yes | > governor-console@0.0.0 lint | > eslint . |
| npm run typecheck | yes | > governor-console@0.0.0 typecheck | > tsc --noEmit |
| npm test | yes | [2m      Tests [22m [1m[32m27 passed[39m[22m[90m (27)[39m | [2m   Start at [22m 21:28:40 | [2m   Duration [2 |
| npm run build | yes | - Using dynamic import() to code-split the application | - Use build.rollupOptions.output.manualChunks to improve chunki |
| API up in open mode | yes | port 60136 |
| build against the test API | yes | - Using dynamic import() to code-split the application | - Use build.rollupOptions.output.manualChunks to improve chunki |
| vite preview up | yes | http://127.0.0.1:60137 |
| playwright chromium | yes |  |
| screenshots | yes | > governor-console@0.0.0 screenshots | > node scripts/screenshots.mjs --url http://127.0.0.1:60137 --out C:\Users\amir0\ |
| screenshot console-runs.png | yes | 46963 bytes |
| screenshot console-build-live.png | yes | 105246 bytes |
| screenshot console-build-lineage.png | yes | 85929 bytes |
| screenshot console-ask-guard.png | yes | 99567 bytes |
| pytest tests | yes | 787 passed, 33 skipped in 228.59s (0:03:48) |
| pytest tests/build | yes | 207 passed, 12 skipped in 94.19s (0:01:34) |

Review: V6 delivers the console in Docker (Node 20 build, nginx SPA + /v1/ SSE proxy), compose on 8080 without default open mode, a Playwright screenshot harness with health checks, four believable 1440×900 showcase images, and updated console docs/README. Matches batch4 §39 and review_focus; acceptance results are trustworthy.

For Amir: README highlights dev startup only; Docker is in docs/console.md. For a live stack demo, set GOVERNOR_CONSOLE_OPEN in .env when using compose.

## Additions for the next plan
Docker users hit the console at :8080 with /v1/ proxied to the api service; they must set GOVERNOR_CONSOLE_OPEN (and origins if needed) on the api via .env — the console container has no API env. Regenerate showcase PNGs with `npm run screenshots` in apps/console (needs Chromium: npx playwright install chromium) against a running preview/dev URL and API in open mode. Screenshot script uses EventSource hold trick for build-live at 4×; lineage shot toggles light then dark theme.

## Additions for V6
ResultPanel is wired on RunPage (build tabs: summary/lineage/funnel/kpi; ask: guard). Artifacts load only for build graph. V6 Playwright shots need console-build-lineage and console-ask-guard against a demo run with manifest/events; consider toggling theme during screenshot pass since chart theme is untested in Vitest. Fixtures live at tests/fixtures/console/build-full.artifacts.json and ask-repaired.events.json.
