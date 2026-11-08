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

## 19. Keys checked against the profile (D14)

Agreed with Amir on 7 Nov 2026, after the first Slack run: the design declared `review_id` the key of `stg_order_reviews` (789 duplicates in Olist: one review can cover several orders) and keyed `stg_geolocation` on a column that is not unique (131,707 duplicates). Both passed validation, were approved, and failed the L4 key tests in the silver build, which escalates a failing staging model at once. The profile already holds each table's candidate keys (single columns and column pairs that are unique with no nulls), and the planner already sees them; nothing checked the design against them.

- New validation code `KEY_NOT_UNIQUE` in `design.validate`, for staging models with a `source_table` in the profile:
  - map each `primary_key` column to the raw column it reads: `expr` null means the raw column of the same name; an `expr` that is a bare column, or a cast of one, maps to that column; any other `expr` makes the key unverifiable and is a finding ("key column '<k>' is computed; key a staging model on raw columns");
  - the key is accepted when some candidate key of the source table is a subset of the mapped raw columns (a superset of a unique key is unique);
  - otherwise a finding that names the source table's candidate keys, or says the table has none ("`<table>` has no unique column or column pair in the profile; leave it unstaged unless a KPI needs it, or dedupe it in an intermediate model"). Counts and column names only, never values.
- Intermediate models are not checked (their grain is not visible statically; their L4 test still runs in dbt).
- The finding goes through the existing design repair loop like any other code, so the planner fixes it before the gate. `propose.md` gains one line: a staging model's `primary_key` must contain one of its source table's `candidate_keys`.
- Fixtures and fake scripts in `tests/fixtures/build/` are made consistent with the rule; the rule is not loosened to keep an old fixture passing.

## 20. Slack clean-up (D9b)

From the first Slack runs on 6 and 7 Nov and the D9 review notes.

- **Ended runs read as ended.** The progress message gets a terminal state:
  - `escalated` or `blueprint_failed`: the failing stage gets `:x:`, stages after it `:heavy_minus_sign:`, the header becomes `:red_circle: stopped at <stage>` plus a one-line reason (at most 200 characters, scrubbed like the escalation reply). For dbt test failures the reason names the failing tests and their failure counts (from the checkpointed error, or `target/run_results.json` in the target when the error is missing); for a connection or compilation error, the error's first line.
  - `built`: header `:large_green_circle: built`; `published`: `:large_green_circle: published` with the pull-request link.
  - **Superseded:** `/governor run <target>` marks every open record of the same project (not terminal, not waiting at the design gate) as `:white_circle: superseded by <id8>`; the build thread itself is not touched.
  - **Interrupted:** at app start, every record that is not terminal and not waiting at the design gate is marked `:white_circle: interrupted (bot restarted)`. A design waiting at the gate stays open: its checkpoint survives a restart and can still be approved.
- **No misleading reply.** The background run no longer posts "Run finished at `awaiting_design_approval`". At the gate it posts nothing extra (the card is the message); when the run ends in an error state it relies on the escalation reply and the terminal header; only an exception in the run itself posts `:warning: run failed: ...` as before.
- **Escalation names the failure.** The escalation reply always names the failing node and its error; `model: null` with an empty error no longer happens (fall back to `run_results.json`, then to the stage).
- **Who may run.** `GOVERNOR_SLACK_RUNNERS` (comma-separated Slack user ids) may use `/governor run`; default: the approvers. Others get an ephemeral refusal and nothing starts.
- **design.md without mapping SQL.** The uploaded copy omits KPI mapping values (they can hold SQL literals); the line says "mappings omitted here; they are in the pull request". The file in the target is unchanged.
- **PR link in the event.** `publish.py` adds `pr_url` (or null) to the `published` event; the notifier uses it.

## 21. Next steps in the channel, PR link, small fixes (D9c)

From the first complete Slack run on 8 Nov (thread `189ba982`: built, 8 KPIs, $0.04). Slack does not run custom slash commands in thread replies, so the next step must be visible in the channel message itself; once a pull request exists, reviewers approve and merge it on GitHub from the link.

- **Built:** the channel progress message gets a "Next" line under the checklist: `Open the pull request: /governor publish <id8>` and an **Open pull request** button (approvers only, same check as Approve; non-approvers get an ephemeral refusal). The thread's "Built" reply carries the same button and the three steps: ① open the pull request ② review and merge it on GitHub ③ certify in a terminal: `python -m governor.build certify --target <target> --by "<name>"` (the target path from `GOVERNOR_SLACK_TARGETS`; certify stays a terminal command because it needs the admin login).
- **Published:** the channel message header links the pull request (`:large_green_circle: published: <PR url>`) and its "Next" line becomes `Review and merge on GitHub, then certify: python -m governor.build certify ...`; the thread gets the link and the same line. Without a PR URL (no `origin`), it names the branch and says to merge it locally.
- **Decided buttons are replaced:** after approve or reject, the design card's buttons are replaced (message update) by `:white_check_mark: Approved by <name> at <time>` or `:x: Rejected by <name>: <note>`; after publish, the PR button is replaced by the link. A second press of a stale button answers ephemerally and changes nothing.
- **Schema prefix on source tables:** both live designs on 7 and 8 Nov wrote `source_table` as `raw.<table>`, which validation rejected as `UNKNOWN_SOURCE_TABLE` and cost one design repair each. Before validation, a `source_table` of the form `<profile schema>.<table>` is normalised to `<table>` when `<table>` is in the profile (code, not a repair); `propose.md` says to give the bare table name. Any other unknown name is still a finding.
- **Live sample test skips on the full data:** `test_live_sample_build_matches_independent_values` runs only when `raw` holds the synthetic sample (row counts of the raw tables equal the sample CSVs); against the full Olist data it skips with that reason.
