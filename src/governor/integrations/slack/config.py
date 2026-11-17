"""Slack settings, read from env only (batch2c section 17). Tokens are read by name and never printed.

- ``SLACK_BOT_TOKEN`` (xoxb-...), ``SLACK_APP_TOKEN`` (xapp-..., Socket Mode)
- ``GOVERNOR_SLACK_CHANNEL``: channel for build messages (default ``governor``)
- ``GOVERNOR_SLACK_APPROVERS``: comma-separated Slack user ids allowed to approve, reject and publish
- ``GOVERNOR_SLACK_RUNNERS``: comma-separated Slack user ids allowed to ``/governor run`` (default: the approvers)
- ``GOVERNOR_SLACK_NAMES``: ``<user id>=<name>`` pairs; the name becomes ``approved_by``
- ``GOVERNOR_SLACK_TARGETS``: ``<name>=<path>`` pairs, for example ``olist=..\\olist-dbt`` (relative to the repo)
- ``GOVERNOR_SLACK_LLM``: the build model for run, approve and reject (``openrouter`` default, or ``fake:<script>``)
- ``GOVERNOR_SLACK_ASK_ROLE``: the reader role for ``/governor ask`` (default ``analyst``; one of the certified
  reader roles, else a configuration error at start)
- ``GOVERNOR_SLACK_ASKERS``: comma-separated Slack user ids allowed to ``/governor ask``, or ``*`` for everyone
  (default: the runners)
- ``GOVERNOR_SLACK_ASK_LLM``: the model for ``/governor ask`` (``openrouter`` default, or ``fake:<script>``)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Mapping

from governor.core import paths
from governor.core.serving import READER_ROLES

DEFAULT_CHANNEL = "governor"
DEFAULT_ASK_ROLE = "analyst"
EVERYONE = "*"
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
    ask_role: str = DEFAULT_ASK_ROLE
    askers: frozenset[str] | None = None  # None: the runners; {"*"}: everyone
    ask_llm: str = "openrouter"

    def __post_init__(self) -> None:
        if self.ask_role not in READER_ROLES:
            raise ConfigError(f"GOVERNOR_SLACK_ASK_ROLE: must be one of {', '.join(sorted(READER_ROLES))}")

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
        raw_askers = env.get("GOVERNOR_SLACK_ASKERS")
        askers = _ids(raw_askers) if raw_askers and raw_askers.strip() else None
        return cls(bot_token=env.get("SLACK_BOT_TOKEN") or None, app_token=env.get("SLACK_APP_TOKEN") or None,
                   channel=(env.get("GOVERNOR_SLACK_CHANNEL") or DEFAULT_CHANNEL).strip().lstrip("#"),
                   approvers=approvers, runners=runners, names=_pairs(env.get("GOVERNOR_SLACK_NAMES"), "GOVERNOR_SLACK_NAMES"),
                   targets=targets, llm=(env.get("GOVERNOR_SLACK_LLM") or "openrouter").strip(),
                   ask_role=(env.get("GOVERNOR_SLACK_ASK_ROLE") or DEFAULT_ASK_ROLE).strip(),
                   askers=askers, ask_llm=(env.get("GOVERNOR_SLACK_ASK_LLM") or "openrouter").strip())

    def is_approver(self, user_id: str) -> bool:
        return user_id in self.approvers

    def is_runner(self, user_id: str) -> bool:
        """``GOVERNOR_SLACK_RUNNERS`` may start builds; unset, the approvers may."""
        return user_id in (self.approvers if self.runners is None else self.runners)

    def is_asker(self, user_id: str) -> bool:
        """``GOVERNOR_SLACK_ASKERS`` (``*``: everyone) may ``/governor ask``; unset, the runners may."""
        if self.askers is None:
            return self.is_runner(user_id)
        return EVERYONE in self.askers or (bool(user_id) and user_id in self.askers)

    def name_for(self, user_id: str) -> str:
        """The ``approved_by`` name: the mapped name, else the Slack user id."""
        return self.names.get(user_id) or user_id


def workspace() -> tuple[Path, str]:
    """The knowledge folder this process serves and the build database as ``host:port/db`` (batch3 section 27).
    Never a user name, password or full DSN."""
    from governor.build.workspace import build_address

    return paths.KNOWLEDGE, build_address()


def start_line(config: SlackConfig) -> str:
    """The one line printed before connecting: channel, targets, knowledge folder and build database."""
    knowledge, database = workspace()
    return (f"governor slack: Socket Mode, channel #{config.channel}, targets {sorted(config.targets) or 'none'}, "
            f"knowledge {knowledge}, database {database}")


def ensure_notifier_registered(env: dict | None = None) -> None:
    """Add the Slack notifier to ``GOVERNOR_BUILD_NOTIFIERS`` (builds started from the app report to Slack)."""
    env = os.environ if env is None else env
    specs = [s.strip() for s in (env.get("GOVERNOR_BUILD_NOTIFIERS") or "").split(",") if s.strip()]
    if NOTIFIER_SPEC not in specs:
        env["GOVERNOR_BUILD_NOTIFIERS"] = ",".join(specs + [NOTIFIER_SPEC])


__all__ = ["ConfigError", "DEFAULT_ASK_ROLE", "DEFAULT_CHANNEL", "EVERYONE","NOTIFIER_SPEC", "SlackConfig", "ensure_notifier_registered",
           "start_line", "workspace"]
