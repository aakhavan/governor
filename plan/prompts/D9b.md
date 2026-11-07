# D9b: Slack clean-up

Capstone batch 2c. Contract: `docs/capstone/batch2c.md` section 20 (section 17 still holds).

Build, in `src/governor/integrations/slack/` (Slack stays a thin client; no build logic):
1. Terminal states in the progress message (`blocks.progress` and the notifier's record): failed stage `:x:`, later stages `:heavy_minus_sign:`, `:red_circle: stopped at <stage>` with a one-line scrubbed reason (failing tests with failure counts, or the error's first line); `:large_green_circle:` for built and published.
2. Superseded on a new `/governor run` of the same project; interrupted at app start for records that are not terminal and not waiting at the design gate.
3. Remove the "Run finished at `<status>`" reply; keep `:warning: run failed` for exceptions.
4. The escalation reply always names the failing node and its error (checkpoint, then `target/run_results.json`, then the stage); failure counts only, never rows.
5. `GOVERNOR_SLACK_RUNNERS` gate on `run` (default: the approvers).
6. The uploaded `design.md` omits KPI mapping values, with the note of section 20.
7. `src/governor/build/publish.py`: the `published` event carries `pr_url`; the notifier posts the link from it. Update `docs/slack.md` (runners, terminal states).

Tests in `tests/integrations/`:
- `test_escalation_marks_progress_failed` (`:x:` on the failing stage, `:heavy_minus_sign:` after it, red header with the reason);
- `test_escalation_reason_names_failing_tests` (from a `run_results.json` fixture with two failing tests: names and counts, no rows);
- `test_new_run_supersedes_open_thread` (a gate-waiting record is not superseded);
- `test_startup_marks_interrupted_threads`;
- `test_no_finished_reply_at_the_gate`;
- `test_non_runner_cannot_start_a_build`;
- `test_design_upload_omits_mappings`;
- `test_published_event_carries_pr_url` (may live in `tests/build/`).

Read: `docs/capstone/batch2c.md` sections 17 and 20, `src/governor/integrations/slack/*`, `src/governor/build/{events,publish,graph,silver}.py`, `tests/integrations/`.

Done when `plan/accept/accept_d9b.py` passes.
