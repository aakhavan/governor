# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
F3 reviewed and passed. The build graph has a compare node between profile and propose: a target whose profile fingerprint hash matches, whose build.json is built under the same thread, and whose design.json exists ends as up_to_date with drift.md, an up_to_date event and no model or dbt call; force skips only that check; a changed hash routes to propose with the last approved design as previous and a names-only drift note, the report gets a drift section, and the first drift proposal is not a repair; no fingerprint means unchanged behaviour. CLI has run --force, Slack accepts run <target> force strictly and renders up_to_date as a terminal header without buttons. 187 build tests and 40 integration tests pass; the eight required tests exist in tests/build/test_maintain.py and tests/integrations/test_slack.py. Next: F4 publish against stale main.

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

## F2 result
*Profile fingerprint and drift, 17 Nov 2026 17:23.*

Implementer `claude-tc-opus`; reviewers `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/F2`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| drift module exists | yes | missing in src/governor/build/drift.py |
| diff exists | yes | missing in src/governor/build/drift.py |
| fingerprint written at approval | yes | missing in src/governor/build/graph.py |
| fingerprint published | yes | missing in src/governor/build/publish.py |
| pytest tests/build | yes | 181 passed, 12 skipped in 58.46s |
| required tests present | yes | 6 found |

Review: F2 does what section 28 asks. The fingerprint holds only names, inferred types, PII flags, candidate keys, version and schema name; tables, columns and keys are sorted so the sha256 over canonical JSON is order-independent. diff reports names and type pairs only. The record node writes governor/profile_fingerprint.json with thread_id, approved_on, hash and fingerprint next to approved.yaml, and publish.GENERATED names it. The graph changes nowhere else. Tests inject distinctive values and sample cells and prove none leak.

For Amir: Delete tests/core/test_build_drift.py and remove it from F2's allowed_paths in plan-batch3.yaml; it re-runs the six drift tests under a second module name whenever pytest is invoked on tests, and the relocked acceptance scripts no longer need it. The extra 'governor/profile_fingerprint.json' entry in publish.GENERATED is redundant with 'governor' but harmless.

## Additions for F3
F3 can rely on: graph.target_fingerprint(target) gives <target>/governor/profile_fingerprint.json; its JSON has keys thread_id, approved_on (ISO date), hash, fingerprint. drift.fingerprint accepts a Profile or the section 5 dict (it validates with Profile, extra='forbid', so pass exactly the profiler's dict). drift.fingerprint_hash(fp) is sha256 of json.dumps(fp, sort_keys=True, separators=(',',':')). drift.diff(old_fp, new_fp) returns Drift with .empty and .summary_lines() (sorted plain lines, names and type pairs only). The compare node should read the file through target_fingerprint and compare doc['hash'] with fingerprint_hash(fingerprint(state['profile'])). Note pytest's default norecursedirs skips tests/build when invoked on 'tests'; acceptance scripts now collect tests/build explicitly, so no re-export shim is needed. tests/core/test_build_drift.py is a workaround slated for deletion; do not depend on it.

## F3 notes (implementer)
Graph: profile -> compare -> (END when up_to_date | propose). compare returns {} without a readable fingerprint (29.3). Same hash plus build.json status built with the fingerprint's thread_id plus design.json, without force: writes drift.md, emits up_to_date (thread_id, last_build), status graph.UP_TO_DATE. Same hash otherwise: a full design from nothing (no drift note). Different hash: state drift = summary_lines, note = graph.drift_note(lines), proposal = design.json, so propose passes it as previous; repairs stay 0. _summary adds last_build/drift_report or drift. events.KINDS gained up_to_date. Slack: Command.force; build.start gets force=True only when forced; blocks.UP_TO_DATE is in TERMINAL, so supersede/interrupt skip it. Tests: tests/build/test_maintain.py, two at the end of tests/integrations/test_slack.py. Local pytest in a shell with GOVERNOR_ROOT set to another checkout fails the gate tests (wrong kpis.yaml); the acceptance script clears it.

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
