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
| `/governor run <target>` | anyone | profile, propose and validate; stops at the design gate |
| `/governor status` | anyone | recent build threads and their last event |
| `/governor approve <thread>` | approvers | the same as `python -m governor.build approve <thread> --by <mapped name>` |
| `/governor reject <thread> <note>` | approvers | send the design back once with the note |
| `/governor publish <thread>` | approvers | commit to `governor/build-<id8>`, push, and open the pull request when the target has an `origin` remote |

`<thread>` is the full build thread id or its first 8 characters. Anything else gets the usage message. Each build thread has one message in the channel, updated in place with the stage checklist (profiled, design proposed, validated, waiting for approval, approved, silver built, gold built, published), the repairs and the model cost. At the design gate the thread under that message gets the design card with its **Approve** and **Reject** buttons (Reject asks for a note in a modal), and `design.md` is attached. An escalation shows the failing model and its error, with quoted literals and DETAIL lines removed. Publishing from Slack posts the pull-request link. Only users in `GOVERNOR_SLACK_APPROVERS` can approve, reject or publish; everyone else gets an ephemeral refusal.

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
