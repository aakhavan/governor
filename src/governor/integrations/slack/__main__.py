"""``python -m governor.integrations.slack``: start the Slack app in Socket Mode (no public URL needed).

Needs ``SLACK_BOT_TOKEN`` and ``SLACK_APP_TOKEN`` in the environment; see ``docs/slack.md``.
"""

from __future__ import annotations

import logging
import sys

from governor.integrations.slack.app import create_app
from governor.integrations.slack.config import ConfigError, SlackConfig


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    try:
        config = SlackConfig.from_env()
    except ConfigError as exc:
        print(f"governor slack: {exc}", file=sys.stderr)
        return 1
    missing = [n for n, v in (("SLACK_BOT_TOKEN", config.bot_token), ("SLACK_APP_TOKEN", config.app_token)) if not v]
    if missing:
        print(f"governor slack: set {', '.join(missing)} (see docs/slack.md)", file=sys.stderr)
        return 1
    if not config.approvers:
        print("governor slack: GOVERNOR_SLACK_APPROVERS is empty, so nobody can approve", file=sys.stderr)
    from slack_bolt.adapter.socket_mode import SocketModeHandler

    app = create_app(config)
    print(f"governor slack: Socket Mode, channel #{config.channel}, targets {sorted(config.targets) or 'none'}",
          file=sys.stderr)
    SocketModeHandler(app, config.app_token).start()
    return 0


if __name__ == "__main__":
    sys.exit(main())
