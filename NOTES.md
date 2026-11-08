# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
D9c is in place. A built run's channel message shows Next: Open the pull request: /governor publish <id8> and an Open pull request button that only approvers can use; the Built reply carries the same button and the three steps, including certify with the path from GOVERNOR_SLACK_TARGETS and the approver's mapped name. After publish the header links the pull request, or names the branch when there is no origin, and the Next line is the merge-then-certify command; the button is replaced by the link. Approve and a Slack reject replace the design-card buttons, and a stale press gets an ephemeral reply and changes nothing. A source_table written as <profile schema>.<table> is normalised to the bare profiled name before validation; any other unknown name is still UNKNOWN_SOURCE_TABLE. The live sample gold test runs only when raw row counts match testbed/sample. Slack still only calls the build functions and puts no warehouse values in payloads.

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

## D9b result
*Slack clean-up, 07 Nov 2026 15:02.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 1 fix loop(s); branch `factory/D9b`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.build never imports Slack | yes |  |
| GOVERNOR_SLACK_RUNNERS documented | yes | missing |
| no 'Run finished at' reply | yes | still there |
| Slack modules import without tokens | yes |  |
| pytest tests/integrations | yes | 15 passed in 5.61s |
| required tests present | yes | 7 found |
| pytest tests/build | yes | 154 passed, 12 skipped in 46.32s |

Review: D9b matches section 20 and the acceptance run is trustworthy. Terminal headers are red (stopped, :x: then :heavy_minus_sign:) or green (built/published); superseded and interrupted cover other open records, and a gate-waiting design stays open. Reasons name every failing test with its full count in both dbt spellings, keep 131707 through the second scrub, and omit row tokens. Runners are allowlisted, uploaded design.md drops mapping cells without editing the file, and the notifier posts pr_url from the published event.

For Amir: Acceptance details missing and still there are not failures. check() records its detail argument even when ok is true. GOVERNOR_SLACK_RUNNERS is in docs/slack.md, and no integration source contains Run finished at. A run marked superseded is not cancelled; if that build later escalates, builds, or publishes, the notifier replaces the superseded header with that later outcome.

## Additions for D9c (implementer)
- Slack record fields: `approved_by` (from the approved event, for the certify `--by`), `branch`, `card_ts`/`card_decided` (the open design card), `built_ts`/`built_summary` (the Built reply whose button becomes the link). Certify `--target` is `GOVERNOR_SLACK_TARGETS[project]` (resolved absolute path), else the checkpointed target.
- Approve card update comes from the `approved` event (so terminal approvals also replace the buttons). The `rejected` event has no note and graph.py is outside D9c, so a Slack reject decides the card in the app *before* `graph.reject` (name + scrubbed note); a terminal reject shows `:x: Rejected` without name. If `graph.reject` then fails, the card still reads rejected (the warning is posted in the thread).
- Stale = card decided, press from an older card (`container.message_ts` != `card_ts`), or checkpoint status not `awaiting_design_approval`; publish button stale unless the record outcome is `built`. Slash commands are not stale-checked (they still go to the build, which refuses as before). Existing D9 test now expects the ephemeral stale answer on a second Approve press instead of the "not waiting" thread reply; D9b test expects the new `published: <url>` header.
- `design.normalise_source_tables` runs in `propose` (so the checkpointed proposal and silver see the bare name) and again in `validate`. Only the profile's own schema prefix is stripped (case-insensitive, quotes allowed); `public.<t>` or `raw.raw.<t>` stay UNKNOWN_SOURCE_TABLE.
- Live sample test: `_raw_ready` also compares `count(*)` of every `raw.<csv stem>` with the sample CSV row counts.

## D9c result
*Next steps in the channel, PR link, small fixes, 08 Nov 2026 15:03.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass, `claude-tc-fable`: pass; 0 fix loop(s); branch `factory/D9c`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.build never imports Slack | yes |  |
| propose prompt asks for the bare table name | yes | missing |
| Slack modules import without tokens | yes |  |
| pytest tests/integrations | yes | 21 passed in 7.78s |
| required tests present | yes | 6 found |
| pytest tests/build | yes | 155 passed, 12 skipped in 45.74s |
| required tests present | yes | 1 found |

Review: cursor-grok: pass | claude-tc-fable: pass

For Amir: The acceptance detail "missing" on the propose-prompt check is check()'s failure string; the check passed because propose.md tells the model to give the bare table name. A Slack reject marks the card decided before graph.reject, so a failed reject leaves the card reading rejected and blocks another press. A reject from the CLI shows ":x: Rejected" without a name or note, because the rejected event carries neither and graph.py is outside this step.

## Additions for the next plan
Record fields: approved_by (approved event, certify --by), branch and pr_url (published event), card_ts and card_decided (open design card), built_ts and built_summary (Built reply whose button becomes the link). Certify --target is GOVERNOR_SLACK_TARGETS[project], else the checkpointed target. A Slack reject writes the decided line, name plus scrubbed note, before graph.reject, because the rejected event has no note; graph.py was outside this step. A reject that does not pass through the Slack app shows ':x: Rejected' with no name. If graph.reject then fails, the card stays rejected and later presses are stale. The slash command /governor publish is not stale-checked; the button is, unless the record outcome is built. design.normalise_source_tables runs in propose, so the checkpoint and silver see the bare name, and again inside validate, which does not write the proposal back. Only the profile schema prefix is removed (case-insensitive, optional double quotes). public.<table> and raw.raw.<table> stay UNKNOWN_SOURCE_TABLE. _raw_ready skips the live sample gold test unless count(*) of every raw."<csv stem>" equals that sample CSV. The Open pull request button calls publish with open_pr true only when the target has a .git entry and an origin remote.
