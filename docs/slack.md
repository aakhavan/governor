# Slack app

The Slack app moves the human design gate from the terminal to Slack (contract: `docs/capstone/batch2c.md` section 17). It is a thin client: every action calls the same build function as the CLI, and progress comes from the build events (`GOVERNOR_STATE_DIR/events.jsonl`). It runs in Socket Mode, so a laptop with no public URL is enough. `certify` stays a terminal command (it needs the admin login).

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
   ```

   To find a user id, open the person's Slack profile, choose *More* (⋯) and then *Copy member ID*. The build settings (`GOVERNOR_BUILD_DSN` and the others) are the same as for the CLI.
4. **Invite the bot.** In the channel (default `#governor`) run `/invite @governor`.
5. **Start the app.** Run `uv run python -m governor.integrations.slack`. It registers its notifier for the builds it starts. Terminal builds report to Slack when `GOVERNOR_BUILD_NOTIFIERS` names the notifier, as above.

## Use

| command | who | what |
|---|---|---|
| `/governor run <target>` | runners | profile, propose and validate; stops at the design gate |
| `/governor status` | anyone | recent build threads and their last event |
| `/governor approve <thread>` | approvers | the same as `python -m governor.build approve <thread> --by <mapped name>` |
| `/governor reject <thread> <note>` | approvers | send the design back once with the note |
| `/governor publish <thread>` | approvers | commit to `governor/build-<id8>`, push, and open the pull request when the target has an `origin` remote |

`<thread>` is the full build thread id or its first 8 characters. Anything else gets the usage message. Each build thread has one message in the channel, updated in place with the stage checklist (profiled, design proposed, validated, waiting for approval, approved, silver built, gold built, published), the repairs and the model cost. At the design gate the thread under that message gets the design card with its **Approve** and **Reject** buttons (Reject asks for a note in a modal), and `design.md` is attached. The attached copy leaves out the KPI mapping values (they can hold SQL literals; the line says "mappings omitted here; they are in the pull request"); the file in the target is unchanged. An escalation names the failing node and its error, with quoted literals and DETAIL lines removed: the error comes from the build checkpoint, else from `target/run_results.json` in the target (failing tests and their failure counts, never rows), else the stage is named. A publish posts the pull-request link from the `published` event (`pr_url`).

Only users in `GOVERNOR_SLACK_RUNNERS` can start a build; when it is not set, the approvers can. Only users in `GOVERNOR_SLACK_APPROVERS` can approve, reject or publish. Everyone else gets an ephemeral refusal and nothing starts.

### Terminal states

An ended run reads as ended in its progress message:

| state | header | checklist |
|---|---|---|
| escalated, blueprint failed, design invalid, rejected twice | `:red_circle: stopped at <stage>` and a one-line reason (at most 200 characters, scrubbed): the failing tests with their failure counts, or the error's first line | `:x:` on the failed stage, `:heavy_minus_sign:` on the stages after it |
| built | `:large_green_circle: built` | |
| published | `:large_green_circle: published` with the pull-request link | |
| superseded | `:white_circle: superseded by <id8>`: a new `/governor run` of the same project ended this open run | `:heavy_minus_sign:` on the stages not reached |
| interrupted | `:white_circle: interrupted (bot restarted)`: the app restarted while the run was open | `:heavy_minus_sign:` on the stages not reached |

"Open" means not ended and not waiting at the design gate. A design waiting at the gate is never superseded or interrupted: its checkpoint survives a restart and can still be approved. The background run posts no "finished" reply: at the gate the design card is the message, an error state has the escalation reply and the red header, and only an exception in the run itself posts `:warning: run failed: ...`.

The message state (build thread id to message timestamp) is kept in `GOVERNOR_STATE_DIR/slack_messages.json`. If Slack fails, the failure is logged and the build carries on.

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
      description: Run, approve, reject or publish a governor build
      usage_hint: "run <target> | status | approve <thread> | reject <thread> <note> | publish <thread>"
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
