# Capstone batch 2c (D9, D10, D13 draft): Slack, column descriptions, Superset

Agreed with Amir on 5 and 6 Nov 2026, after the evaluation passed (11/11 gold, 20/20 certified answers, red-team gate passed). Builds on `batch2.md` and `batch2b.md`.

## 16. Column descriptions from lineage (D10)

Most silver columns had no description after the first real build. `governor.build.docs` fills them from evidence governor already holds, deterministic first:

1. Gold value columns: the KPI's catalogue definition (and the column's role, for example "share of delivered orders on time").
2. Staging columns: a sentence from the lineage and the profile: source column and table, the expression applied ("cast from text"), type, key, null rate band (never values), and "personal data, hashed for analysts" when the policy tags it.
3. Intermediate columns with the same name as a column of a ref inherit that description.
4. Every column still empty: one write-model call per model (prompt `src/governor/build/prompts/describe.md`) with the model description, the columns' lineage expressions, profile counts, the design assumptions and the deterministic descriptions of its refs; never data values. At most 200 characters each.

Descriptions go into `_staging.yml`, `_intermediate.yml` and the marts yml when they are written; `governor/build.json` gains `docs_coverage` (share of columns with a description) and `governor/pr.md` shows it, so the reviewer reviews descriptions with the code. Fake script key: `{"describe": {"<model>": ["<json {column: description}>", ...]}}`.

## 17. Slack app (D9)

A thin client on top of the build functions and the event log (`batch2b.md` section 12); no build logic in Slack.

- Module `src/governor/integrations/slack/`, Slack Bolt for Python in Socket Mode (`slack-bolt`), so it runs on a laptop with no public URL. Start: `python -m governor.integrations.slack`. Settings from env only: `SLACK_BOT_TOKEN`, `SLACK_APP_TOKEN`, `GOVERNOR_SLACK_CHANNEL` (default `governor`), `GOVERNOR_SLACK_APPROVERS` (comma-separated Slack user ids allowed to approve), `GOVERNOR_SLACK_NAMES` (`<user id>=<name>` pairs; the name becomes `approved_by`), `GOVERNOR_SLACK_TARGETS` (`<name>=<path>` pairs, for example `olist=..\olist-dbt`).
- Slash command `/governor`: `run <target>`, `status`, `approve <thread>`, `reject <thread> <note>`, `publish <thread>`. Arguments are parsed strictly (known target names, a thread id that exists); anything else gets a usage message. Long work runs in a background thread after the 3-second acknowledgement.
- Notifier `governor.integrations.slack.notifier:notify` (registered through `GOVERNOR_BUILD_NOTIFIERS`): one message per build thread, updated in place with a stage checklist (profiled, design proposed, validated, waiting for approval, approved, silver built, gold built, published), repairs and cost; details go in the thread. At `design_gate` it posts a card: silver models, KPIs to build and to decline with their gap reasons, validation findings, and **Approve** / **Reject** buttons (reject asks for a note in a modal); `design.md` is attached as a file. At `published` it posts the pull-request link; at `escalated` the failing model and its error (no data values).
- Approvals: only users in `GOVERNOR_SLACK_APPROVERS` can approve, reject or publish; others get an ephemeral refusal. Approval calls the same `graph.approve` as the CLI with `by` = the mapped name; the decision lands in `approved.yaml` as before. `certify` stays a terminal command (it needs the admin login).
- Message state (thread id to message timestamp) lives in `GOVERNOR_STATE_DIR/slack_messages.json`. Block Kit rendering is pure functions so tests need no network.

## 18. Superset (D13, draft: run only if Amir decides on 7 Nov)

Superset as a container beside the test bed, reading `serve_analyst` through a read-only `governor_superset` role; datasets, charts and one "Shop KPIs" dashboard for the certified KPIs generated from `analytics.governor_certified` as Superset's YAML export and imported by script. Not in `plan.yaml` until decided.
