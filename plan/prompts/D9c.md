# D9c: Next steps in the channel, PR link, small fixes

Capstone batch 2c. Contract: `docs/capstone/batch2c.md` section 21 (sections 17 and 20 still hold).

Build:
1. `src/governor/integrations/slack/`: the "Next" line and **Open pull request** button on the channel progress message and the thread's "Built" reply (approvers only); the published header with the PR link and the merge-then-certify line (branch and local merge when there is no PR URL); decided buttons replaced after approve, reject and publish; stale presses answered ephemerally with no effect. The certify line uses the target path from `GOVERNOR_SLACK_TARGETS` and the approver's mapped name.
2. `src/governor/build/design.py`: normalise `source_table` `<profile schema>.<table>` to `<table>` before validation when `<table>` is profiled; `prompts/propose.md`: give the bare table name.
3. `tests/build/test_gold.py`: the live sample test skips unless `raw` holds the sample (row counts equal the sample CSVs).
4. Update `docs/slack.md` (the publish button, the next-step lines).

Tests:
- `tests/integrations/`: `test_built_message_shows_next_step_and_pr_button`, `test_pr_button_requires_approver`, `test_published_header_links_pr_and_says_certify`, `test_published_without_pr_url_names_branch`, `test_design_buttons_replaced_after_approve`, `test_stale_button_press_changes_nothing`;
- `tests/build/`: `test_schema_prefixed_source_table_is_normalised` (and an unknown prefixed name is still `UNKNOWN_SOURCE_TABLE`).

Read: `docs/capstone/batch2c.md` sections 17, 20, 21, `src/governor/integrations/slack/*`, `src/governor/build/{design,publish}.py`, `tests/build/test_gold.py`, `tests/integrations/`.

Done when `plan/accept/accept_d9c.py` passes.
