"""Slack settings, read from env only (batch2c section 17). Tokens are read by name and never printed.

- ``SLACK_BOT_TOKEN`` (xoxb-...), ``SLACK_APP_TOKEN`` (xapp-..., Socket Mode)
- ``GOVERNOR_SLACK_CHANNEL``: channel for build messages (default ``governor``)
- ``GOVERNOR_SLACK_APPROVERS``: comma-separated Slack user ids allowed to approve, reject and publish
- ``GOVERNOR_SLACK_RUNNERS``: comma-separated Slack user ids allowed to ``/governor run`` (default: the approvers)
- ``GOVERNOR_SLACK_NAMES``: ``<user id>=<name>`` pairs; the name becomes ``approved_by``
- ``GOVERNOR_SLACK_TARGETS``: ``<name>=<path>`` pairs, for example ``olist=..\\olist-dbt`` (relative to the repo)
- ``GOVERNOR_SLACK_LLM``: the build model for run, approve and reject (``openrouter`` default, or ``fake:<script>``)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from governor.core import paths

DEFAULT_CHANNEL = "governor"
NOTIFIER_SPEC = "governor.integrations.slack.notifier:notify"
TARGET_NAME = re.compile(r"^[A-Za-z0-9_-]+$")


class ConfigError(ValueError):
    """A setting cannot be parsed; the message names the variable, never its value."""


def _pairs(raw: str | None, var: str) -> dict[str, str]:
    out: dict[str, str] = {}
    for item in (raw or "").split(","):
        item = item.strip()
        if not item:
            continue
        key, sep, value = item.partition("=")
        if not sep or not key.strip() or not value.strip():
            raise ConfigError(f"{var}: every entry must be <key>=<value>")
        out[key.strip()] = value.strip()
    return out


def _ids(raw: str | None) -> frozenset[str]:
    return frozenset(a.strip() for a in (raw or "").split(",") if a.strip())


def _target_path(raw: str) -> Path:
    p = Path(raw)
    return (p if p.is_absolute() else paths.ROOT / p).resolve()


@dataclass(frozen=True)
class SlackConfig:
    bot_token: str | None = None
    app_token: str | None = None
    channel: str = DEFAULT_CHANNEL
    approvers: frozenset[str] = frozenset()
    runners: frozenset[str] | None = None  # None: the approvers
    names: dict[str, str] = field(default_factory=dict)
    targets: dict[str, Path] = field(default_factory=dict)
    llm: str = "openrouter"

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "SlackConfig":
        env = os.environ if env is None else env
        targets = {}
        for name, raw in _pairs(env.get("GOVERNOR_SLACK_TARGETS"), "GOVERNOR_SLACK_TARGETS").items():
            if not TARGET_NAME.match(name):
                raise ConfigError("GOVERNOR_SLACK_TARGETS: target names use letters, digits, _ and - only")
            targets[name] = _target_path(raw)
        approvers = _ids(env.get("GOVERNOR_SLACK_APPROVERS"))
        raw_runners = env.get("GOVERNOR_SLACK_RUNNERS")
        runners = _ids(raw_runners) if raw_runners and raw_runners.strip() else None
        return cls(bot_token=env.get("SLACK_BOT_TOKEN") or None, app_token=env.get("SLACK_APP_TOKEN") or None,
                   channel=(env.get("GOVERNOR_SLACK_CHANNEL") or DEFAULT_CHANNEL).strip().lstrip("#"),
                   approvers=approvers, runners=runners, names=_pairs(env.get("GOVERNOR_SLACK_NAMES"), "GOVERNOR_SLACK_NAMES"),
                   targets=targets, llm=(env.get("GOVERNOR_SLACK_LLM") or "openrouter").strip())

    def is_approver(self, user_id: str) -> bool:
        return user_id in self.approvers

    def is_runner(self, user_id: str) -> bool:
        """``GOVERNOR_SLACK_RUNNERS`` may start builds; unset, the approvers may."""
        return user_id in (self.approvers if self.runners is None else self.runners)

    def name_for(self, user_id: str) -> str:
        """The ``approved_by`` name: the mapped name, else the Slack user id."""
        return self.names.get(user_id) or user_id


def ensure_notifier_registered(env: dict | None = None) -> None:
    """Add the Slack notifier to ``GOVERNOR_BUILD_NOTIFIERS`` (builds started from the app report to Slack)."""
    env = os.environ if env is None else env
    specs = [s.strip() for s in (env.get("GOVERNOR_BUILD_NOTIFIERS") or "").split(",") if s.strip()]
    if NOTIFIER_SPEC not in specs:
        env["GOVERNOR_BUILD_NOTIFIERS"] = ",".join(specs + [NOTIFIER_SPEC])


__all__ = ["ConfigError", "DEFAULT_CHANNEL", "NOTIFIER_SPEC", "SlackConfig", "ensure_notifier_registered"]
