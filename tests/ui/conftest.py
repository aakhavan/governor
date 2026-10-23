"""UI tests: the Streamlit pages over the API in-process (GOVERNOR_API_URL=asgi), offline FakeLLM."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from governor.ask import service
from governor.core import paths

ROOT = Path(__file__).resolve().parents[2]
UI = ROOT / "apps" / "streamlit"
TOKENS = "analyst:test-analyst-token,finance_admin:test-admin-token"
TOKEN = "test-analyst-token"
TIMEOUT = 120

if str(UI) not in sys.path:
    sys.path.insert(0, str(UI))


@pytest.fixture(autouse=True)
def _state_dir(tmp_path_factory, monkeypatch):
    state = tmp_path_factory.mktemp("state")
    monkeypatch.setattr(paths, "STATE", state)
    monkeypatch.setattr(paths, "TRACES", state / "traces.duckdb")
    monkeypatch.setattr(paths, "CHECKPOINTS", state / "checkpoints.sqlite")
    monkeypatch.delenv("GOVERNOR_TRACE_TEXT", raising=False)
    monkeypatch.setenv("GOVERNOR_API_URL", "asgi")
    monkeypatch.setenv("GOVERNOR_LLM", "fake")
    monkeypatch.setenv("GOVERNOR_API_TOKENS", TOKENS)
    yield state
    service.reset()  # close the checkpoint connection before the temp dir goes


@pytest.fixture
def use_api(monkeypatch):
    """Serve a fresh API app (env tokens; ``llm=`` scripts the model) to the asgi client."""
    from governor.api import app as api_app

    def use(**kwargs):
        monkeypatch.setattr(api_app, "app", api_app.create_app(**kwargs))

    use()
    return use


@pytest.fixture
def page(use_api):
    """An AppTest for a page under apps/streamlit (``None`` = the landing page), with or without a token."""

    def make(name: str | None = None, token: str | None = TOKEN) -> AppTest:
        at = AppTest.from_file(str(UI / (name or "app.py")), default_timeout=TIMEOUT)
        if token:
            at.session_state["api_token"] = token
        return at

    return make
