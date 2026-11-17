# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
F4 is implemented and accepted on branch factory/F4 (uncommitted). publish.py gained sync_main (fetch, fast-forward a behind-only main, refuse a diverged one with the exact one-line message, before any branch is created), a staged-diff check that returns nothing_to_publish without a commit and with the branch deleted, and no --allow-empty. __main__.py and the Slack app surface nothing_to_publish as a plain message. tests/build/test_publish.py has the four section-30 tests using a local bare origin and a clone under tmp_path, all offline. Acceptance: tests/build 191 passed 12 skipped, tests/integrations 40 passed, capstone ground truth unchanged.

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

## F3 result
*Up-to-date runs and drift-aware design, 17 Nov 2026 17:56.*

Implementer `claude-tc-opus`; reviewers `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/F3`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| compare node | yes | missing in src/governor/build/graph.py |
| force flag | yes | missing in src/governor/build/__main__.py |
| drift section in report | yes | missing in src/governor/build/design.py |
| pytest tests/build | yes | 187 passed, 12 skipped in 56.86s |
| pytest tests/integrations | yes | 40 passed in 11.98s |
| required tests present | yes | 8 found |

Review: F3 does what section 29 asks. compare sits between profile and propose, requires hash + built build.json with the same thread + design.json, writes drift.md, emits up_to_date and ends with no model or dbt call (test snapshots models/ by bytes and mtime). force only skips that check; drift seeds the previous design through the existing proposal/note path with a names-only note and repairs stays 0. No-fingerprint targets return {} and run as before. Slack parses the literal force only, plain runs call start unchanged, up_to_date is terminal with no buttons or thread replies.

For Amir: Clean step. Two cosmetic items only: the up_to_date Slack headline format differs slightly from the other terminal headers, and a stale drift.md can linger after a later full design of an unchanged schema.

## Additions for F4
graph.start now takes force=False and BuildState has force, drift and last_build keys; status UP_TO_DATE ends the graph after compare, before propose, so F5's tenant wiring must keep the profile and compare path tenant-aware (the fingerprint and build.json are read from the target, which is per tenant already). The drift note is in state['note'] and persists through repairs; a rejection replaces it. events.KINDS gained up_to_date. Slack: Command.force, GovernorSlack._run(target, thread_id, force=False) passes force only when True so plain calls stay byte-identical; blocks.UP_TO_DATE is in TERMINAL. Cosmetic leftovers: the up_to_date headline uses a newline before the build label unlike other states, and drift.md is not removed when a later run of an unchanged schema does a full design.

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
