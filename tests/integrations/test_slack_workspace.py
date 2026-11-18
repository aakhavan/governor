"""F1 start-up line and usage footer (batch3.md sections 27.2 and 27.3). Offline."""
from types import SimpleNamespace

import pytest

from governor.core import paths
from governor.integrations.slack import __main__ as slack_main
from governor.integrations.slack.app import GovernorSlack
from governor.integrations.slack.config import SlackConfig

SECRETS = ("s3cret-pw", "governor_build_local", "governor_build", "xoxb-", "xapp-", "password", "user=")


@pytest.fixture
def pg_env(monkeypatch):
    monkeypatch.setenv("GOVERNOR_PG_HOST", "db.example")
    monkeypatch.setenv("GOVERNOR_PG_PORT", "55433")
    monkeypatch.setenv("GOVERNOR_PG_DB", "shop")
    monkeypatch.setenv("GOVERNOR_BUILD_USER", "governor_build")
    monkeypatch.setenv("GOVERNOR_BUILD_PASSWORD", "s3cret-pw")


def test_start_line_names_workspace_without_secrets(pg_env, monkeypatch, tmp_path, capsys):
    env = {"SLACK_BOT_TOKEN": "xoxb-test", "SLACK_APP_TOKEN": "xapp-test", "GOVERNOR_SLACK_APPROVERS": "U1",
           "GOVERNOR_SLACK_TARGETS": f"olist={tmp_path / 'target'}"}
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    started = []
    monkeypatch.setattr(slack_main, "create_app", lambda config: object())
    import slack_bolt.adapter.socket_mode as sm

    monkeypatch.setattr(sm, "SocketModeHandler", lambda app, token: SimpleNamespace(start=lambda: started.append(1)))
    assert slack_main.main() == 0 and started == [1]
    lines = [ln for ln in capsys.readouterr().err.splitlines() if "Socket Mode" in ln]
    assert len(lines) == 1
    line = lines[0]
    assert "#governor" in line and "olist" in line
    assert str(paths.KNOWLEDGE) in line and "db.example:55433/shop" in line
    for secret in SECRETS:
        assert secret not in line, secret


def test_usage_footer_names_workspace(pg_env, tmp_path):
    config = SlackConfig.from_env({"GOVERNOR_SLACK_APPROVERS": "U1", "GOVERNOR_SLACK_TARGETS": f"olist={tmp_path / 't'}"})
    gov = GovernorSlack(config, SimpleNamespace(), runner=lambda fn: None, threads=lambda: [],
                        build=SimpleNamespace(start=lambda *a, **k: pytest.fail("no build")))
    said = []
    for text in ("", "run elsewhere"):
        said.clear()
        gov.handle_command("U1", text, lambda **kw: said.append(kw))
        out = said[0]["text"]
        assert out.splitlines()[-1] == f"workspace: knowledge {paths.KNOWLEDGE.name} · database db.example:55433/shop"
        for secret in SECRETS:
            assert secret not in out, secret
