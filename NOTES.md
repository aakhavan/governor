# NOTES: governor

Rules: under 150 lines. Current state, open questions, last two steps' result + additions. Older sections go to `NOTES-archive.md` (the factory rotates).

## Current state
E1 is in place. /governor ask posts a certified answer to the configured channel and keeps refusals and errors ephemeral to the asker. The role comes only from GOVERNOR_SLACK_ASK_ROLE (analyst or finance_admin); anything else is a configuration error at startup. Who may ask is GOVERNOR_SLACK_ASKERS, or the runners when that is unset, or the approvers when the runners are also unset. The model is GOVERNOR_SLACK_ASK_LLM (default openrouter). The Slack package still imports without a database or tokens; governor.ask is imported only inside the default asker, which calls certified.answer on the ask login (GOVERNOR_PG_DSN). The channel message is the escaped question, CertifiedAnswer.text unchanged, and a context line with the role and, when present, the KPI id. SQL is not shown. The log records the outcome, the KPI id, and the Slack user id, never the question. The build commands, buttons, and publish path are unchanged.

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

## E1 result
*Certified answers in Slack (/governor ask), 11 Nov 2026 12:46.*

Implementer `claude-tc-opus`; reviewers `cursor-grok`: pass; 0 fix loop(s); branch `factory/E1`.

| check | ok | detail |
|---|---|---|
| capstone ground truth unchanged | yes | capstone ground truth unchanged |
| governor.build imports neither Slack nor ask | yes |  |
| governor.ask never imports integrations | yes |  |
| no top-level import of governor.ask in the Slack modules | yes | import it inside the default asker |
| Slack modules import without tokens or a database | yes |  |
| usage text lists ask | yes |  |
| docs/slack.md mentions /governor ask | yes |  |
| docs/slack.md mentions GOVERNOR_SLACK_ASK_ROLE | yes |  |
| docs/slack.md mentions GOVERNOR_SLACK_ASKERS | yes |  |
| docs/slack.md mentions GOVERNOR_SLACK_ASK_LLM | yes |  |
| pytest tests/integrations | yes | 36 passed in 7.56s |
| required tests present | yes | 9 found |

Review: E1 matches section 22. /governor ask takes its role only from GOVERNOR_SLACK_ASK_ROLE, calls certified.answer inside the default asker, and posts the escaped question, CertifiedAnswer.text, and the context line to the channel. Refusals and errors are ephemeral, do not repeat the question, and errors go through safe_text. Logs record outcome, KPI id, and user id. The sql field is not posted. The acceptance checks match this code.

For Amir: The integration tests inject a fake asker, so the suite never calls certified.answer. The real call is GovernorSlack._default_asker. A bad GOVERNOR_SLACK_ASK_ROLE raises ConfigError while building SlackConfig, and __main__ exits before Socket Mode starts.

## Additions for E2
E2 splits certified.answer and adds answer_reply. Slack must keep calling certified.answer(question, role, certified.make_llm(config.ask_llm)) with no adapter, from GovernorSlack._default_asker only. That import has to stay inside the function: a top-level governor.ask import fails the E1 check. The omitted adapter is the ask login (GOVERNOR_PG_DSN), same as the API. make_llm("openrouter") returns None, and answer() then builds the chat model. READER_ROLES is the dict in governor.core.serving (keys analyst and finance_admin). SlackConfig rejects any other ask role at construction, including the Postgres role names. Channel outcomes are answer, not_available, and unanswerable. refused and any exception are ephemeral and must not include the question. The channel shows text only; sql, value, and citation stay off the message and out of the log. Ask logs are outcome, kpi id, and Slack user id. GOVERNOR_SLACK_ASKERS unset means the runners, and unset runners means the approvers. * means every user.
