"""Slack tests: a fake Slack client (no network), the build state in a temp folder, the sample design."""
import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("_build_fixtures", ROOT / "tests" / "build" / "conftest.py")
_build_fixtures = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_build_fixtures)
sample_profile = _build_fixtures.sample_profile

FIXTURES = ROOT / "tests" / "fixtures" / "build"


class FakeSlack:
    """Records every Web API call; chat_postMessage returns a new ts. ``fail=True`` raises on every call."""

    def __init__(self, fail: bool = False):
        self.calls: list[tuple[str, dict]] = []
        self.fail = fail
        self._n = 0

    def _call(self, name: str, kwargs: dict) -> dict:
        self.calls.append((name, kwargs))
        if self.fail:
            raise RuntimeError("slack is down")
        return {"ok": True}

    def chat_postMessage(self, **kw):
        self._call("chat_postMessage", kw)
        self._n += 1
        return {"ok": True, "channel": "C123", "ts": f"1700000000.{self._n:06d}"}

    def chat_update(self, **kw):
        return self._call("chat_update", kw)

    def chat_postEphemeral(self, **kw):
        return self._call("chat_postEphemeral", kw)

    def views_open(self, **kw):
        return self._call("views_open", kw)

    def files_upload_v2(self, **kw):
        return self._call("files_upload_v2", kw)

    def named(self, name: str) -> list[dict]:
        return [kw for n, kw in self.calls if n == name]


@pytest.fixture(autouse=True)
def _state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path / "state"))
    for k in ("GOVERNOR_BUILD_NOTIFIERS", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN"):
        monkeypatch.delenv(k, raising=False)
    from governor.integrations.slack import notifier

    notifier.configure(None)
    yield
    notifier.configure(None)


@pytest.fixture
def fake():
    return FakeSlack()


@pytest.fixture
def failing():
    return FakeSlack(fail=True)


@pytest.fixture(scope="session")
def _profile() -> dict:
    return sample_profile()


@pytest.fixture
def profile(_profile) -> dict:
    return copy.deepcopy(_profile)


@pytest.fixture
def good() -> dict:
    return json.loads((FIXTURES / "sample_design.json").read_text(encoding="utf-8"))
