"""Slack app for the build (batch2c section 17): a thin client on the build functions and the event log.

- ``config``: settings from env only.
- ``blocks``: Block Kit rendering, pure functions (no network, no tokens).
- ``notifier``: ``notify(event)`` for ``GOVERNOR_BUILD_NOTIFIERS``; one message per build thread, updated in place.
- ``app``: the Socket Mode app, ``/governor`` with strict parsing, Approve / Reject buttons and the reject modal.

Start with ``python -m governor.integrations.slack`` (setup: ``docs/slack.md``).
"""
