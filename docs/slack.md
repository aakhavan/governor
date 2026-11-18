# Slack app

The Slack app moves the human design gate from the terminal to Slack. It is a thin client: every action calls the same build function as the CLI, and progress comes from the build events (`GOVERNOR_STATE_DIR/events.jsonl`). It runs in Socket Mode, so a laptop with no public URL is enough. `certify` stays a terminal command (it needs the admin login).

## Setup in five steps

1. **Create the app from the manifest.** At <https://api.slack.com/apps> choose *Create New App*, then *From an app manifest*, pick the workspace and paste the manifest below.
2. **Turn on Socket Mode.** The manifest already sets `socket_mode_enabled: true`. Under *Basic Information*, then *App-Level Tokens*, create a token with the `connections:write` scope. This is the app token (`xapp-...`).
3. **Put the tokens in env variables.** Install the app to the workspace (*Install App*) and copy the *Bot User OAuth Token* (`xoxb-...`). Set both tokens in your shell or in your local `.env`. Never commit them.

   ```powershell
   $env:SLACK_BOT_TOKEN = "xoxb-..."
   $env:SLACK_APP_TOKEN = "xapp-..."
   $env:GOVERNOR_SLACK_CHANNEL = "governor"                      # default
   $env:GOVERNOR_SLACK_APPROVERS = "U012ABCDEF"                  # Slack user ids, comma-separated
   $env:GOVERNOR_SLACK_RUNNERS = "U012ABCDEF,U034GHIJKL"         # who may /governor run (default: the approvers)
   $env:GOVERNOR_SLACK_NAMES = "U012ABCDEF=amir"                 # user id = name written as approved_by
   $env:GOVERNOR_SLACK_TARGETS = "olist=..\olist-dbt"            # name = target dbt project (relative to the repo)
   $env:GOVERNOR_SLACK_LLM = "openrouter"                        # or fake:<script.json>
   $env:GOVERNOR_BUILD_NOTIFIERS = "governor.integrations.slack.notifier:notify"   # for builds run from the terminal
   $env:GOVERNOR_SLACK_ASK_ROLE = "analyst"                      # reader role for /governor ask (analyst or finance_admin)
   $env:GOVERNOR_SLACK_ASKERS = "*"                              # who may /governor ask: ids, * for everyone (default: the runners)
   $env:GOVERNOR_SLACK_ASK_LLM = "openrouter"                    # model for /governor ask, or fake:<script.json>
   $env:GOVERNOR_PG_DSN = "..."                                  # the ask login (needed for /governor ask)
   ```

   To find a user id, open the person's Slack profile, choose *More* (⋯) and then *Copy member ID*. The build settings (`GOVERNOR_BUILD_DSN` and the others) are the same as for the CLI.
4. **Invite the bot.** In the channel (default `#governor`) run `/invite @governor`.
5. **Start the app.** Run `uv run python -m governor.integrations.slack`. It registers its notifier for the builds it starts. Terminal builds report to Slack when `GOVERNOR_BUILD_NOTIFIERS` names the notifier, as above.

Before connecting, the app prints one start-up line: the channel, the targets, the knowledge folder it serves and the build database as `host:port/db` (never a user name, password or full DSN). The usage text in Slack ends with the same workspace, so you can check which knowledge folder and database the bot is on. Every database connection gives up after `GOVERNOR_PG_CONNECT_TIMEOUT` seconds (default 10), and the dbt profile uses the same setting. A database that is down or unreachable fails the build with an error instead of hanging at profiling.

## Use

| command | who | what |
|---|---|---|
| `/governor run <target>` | runners | profile, propose and validate; stops at the design gate |
| `/governor status` | anyone | recent build threads and their last event |
| `/governor approve <thread>` | approvers | the same as `python -m governor.build approve <thread> --by <mapped name>` |
| `/governor reject <thread> <note>` | approvers | send the design back once with the note |
| `/governor publish <thread>` | approvers | commit to `governor/build-<id8>`, push, and open the pull request when the target has an `origin` remote |
| `/governor ask <question>` | askers | a certified answer from the published KPIs (see below) |

`<thread>` is the full build thread id or its first 8 characters. Anything else gets the usage message. Each build thread has one message in the channel, updated in place with the stage checklist (profiled, design proposed, validated, waiting for approval, approved, silver built, gold built, published), the repairs and the model cost. At the design gate the thread under that message gets the design card with its **Approve** and **Reject** buttons (Reject asks for a note in a modal), and `design.md` is attached. The attached copy leaves out the KPI mapping values (they can hold SQL literals; the line says "mappings omitted here; they are in the pull request"); the file in the target is unchanged. An escalation names the failing node and its error, with quoted literals and DETAIL lines removed: the error comes from the build checkpoint, else from `target/run_results.json` in the target (failing tests and their failure counts, never rows), else the stage is named. A publish posts the pull-request link from the `published` event (`pr_url`).

Only users in `GOVERNOR_SLACK_RUNNERS` can start a build; when it is not set, the approvers can. Only users in `GOVERNOR_SLACK_APPROVERS` can approve, reject or publish, with the commands or the buttons. Everyone else gets an ephemeral refusal and nothing starts.

### Certified answers: `/governor ask`

`/governor ask <question>` is a thin client of the certified answer path (`governor.ask.certified.answer`). The question is everything after `ask`, 3 to 300 characters. The app answers at once with an ephemeral "Looking that up...", then:

- an answer, a "not available" gap or an unanswerable question is posted in the channel: the question, the answer text with its citation or gap, and a context line `certified path · role <role> · KPI <id>`. No SQL is shown.
- a refusal is shown only to the asker, without the question.
- an error is shown only to the asker as "Certified answers are not available right now: <reason>", with data values removed.

Settings:

- `GOVERNOR_SLACK_ASK_ROLE`: the reader role every Slack question runs as (default `analyst`; `analyst` or `finance_admin`). Any other value stops the app at start. Nothing in the question or in Slack can change it.
- `GOVERNOR_SLACK_ASKERS`: Slack user ids that may ask, comma-separated, or `*` for everyone. When it is not set, the runners may ask. Others get an ephemeral refusal.
- `GOVERNOR_SLACK_ASK_LLM`: the model that picks the KPI (default `openrouter`, or `fake:<script.json>`).

The app process needs the ask login in its environment (`GOVERNOR_PG_DSN`), the same as the API. The log records the outcome, the KPI id and the Slack user id, never the question.

### Next steps and the publish button

Slack does not run custom slash commands in thread replies, so the next step is shown in the channel message itself:

- **Built:** under the checklist, `Next: Open the pull request: /governor publish <id8>` and an **Open pull request** button. The thread's "Built" reply has the same button and three steps: ① open the pull request, ② review and merge it on GitHub, ③ certify in a terminal: `python -m governor.build certify --target <target> --by "<name>"`. The target path comes from `GOVERNOR_SLACK_TARGETS` and the name is the approver's mapped name (`GOVERNOR_SLACK_NAMES`). `certify` stays a terminal command because it needs the admin login.
- **Published:** the header links the pull request (`:large_green_circle: published: <PR url>`) and the "Next" line becomes `Review and merge on GitHub, then certify: python -m governor.build certify ...`. The thread gets the link and the same line. When there is no pull request (the target has no `origin`), the header names the branch and the line says to merge it into `main` locally, then certify.

Pressing **Open pull request** is the same as `/governor publish <id8>`. Only approvers can press it.

### Decided buttons

After an approve, the design card's buttons are replaced by `:white_check_mark: Approved by <name> at <time>`. After a reject, they are replaced by `:x: Rejected by <name>: <note>`, and the next proposal gets a new card with fresh buttons. After a publish, the **Open pull request** button is replaced by the link, in the channel message and in the "Built" reply. A stale button gets an ephemeral "out of date" answer and changes nothing. A button is stale when the design is already decided or no longer at the gate, when it is on an older card, or when the build is already published or not built yet.

### Terminal states

An ended run reads as ended in its progress message:

| state | header | checklist |
|---|---|---|
| escalated, blueprint failed, design invalid, rejected twice | `:red_circle: stopped at <stage>` and a one-line reason (at most 200 characters, scrubbed): the failing tests with their failure counts, or the error's first line | `:x:` on the failed stage, `:heavy_minus_sign:` on the stages after it |
| built | `:large_green_circle: built`, the "Next" line and the **Open pull request** button | |
| published | `:large_green_circle: published: <PR url>` (or the branch to merge locally) and the merge-then-certify line | |
| superseded | `:white_circle: superseded by <id8>`: a new `/governor run` of the same project ended this open run | `:heavy_minus_sign:` on the stages not reached |
| interrupted | `:white_circle: interrupted (bot restarted)`: the app restarted while the run was open | `:heavy_minus_sign:` on the stages not reached |

"Open" means not ended and not waiting at the design gate. A design waiting at the gate is never superseded or interrupted: its checkpoint survives a restart and can still be approved. The background run posts no "finished" reply: at the gate the design card is the message, an error state has the escalation reply and the red header, and only an exception in the run itself posts `:warning: run failed: ...`.

The message state (build thread id to message timestamp) is kept in `GOVERNOR_STATE_DIR/slack_messages.json`. If Slack fails, the failure is logged and the build carries on.

### Several tenants

With `GOVERNOR_TENANTS` set to a tenant registry (see `docs/tenants.md`), one bot serves every tenant in it:

- The targets are the tenant names: `/governor run acme` builds tenant `acme` (its knowledge, checkpoints, database and target). `GOVERNOR_SLACK_TARGETS` is ignored, with a warning at start-up.
- `approve`, `reject`, `publish` and the buttons find the tenant from the build thread, in each tenant's own checkpoints. A short id that matches threads in two tenants is a usage error naming both; give the full id.
- The progress message, the design card and every reply name the tenant. The start-up line and the usage footer list each tenant as `<name>: <host>:<port>/<db>`.
- `/governor ask` stays single-tenant: it replies `ask serves one tenant only; it is not available in multi-tenant mode yet` and runs nothing.

Without `GOVERNOR_TENANTS` the bot works as described above.

## Manifest

```yaml
display_information:
  name: governor
  description: Build approvals for governor (design gate, progress, publish)
features:
  bot_user:
    display_name: governor
    always_online: false
  slash_commands:
    - command: /governor
      description: Run, approve, reject or publish a governor build, or ask a certified question
      usage_hint: "run <target> | status | approve <thread> | reject <thread> <note> | publish <thread> | ask <question>"
      should_escape: false
oauth_config:
  scopes:
    bot:
      - chat:write
      - commands
      - files:write
settings:
  interactivity:
    is_enabled: true
  org_deploy_enabled: false
  socket_mode_enabled: true
  token_rotation_enabled: false
```
