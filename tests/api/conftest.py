"""API tests: offline (FakeLLM), state in a temp dir, two known tokens."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from governor.ask import service
from governor.core import paths

TOKENS = "analyst:test-analyst-token,finance_admin:test-admin-token"


@pytest.fixture(autouse=True)
def _state_dir(tmp_path_factory, monkeypatch):
    state = tmp_path_factory.mktemp("state")
    monkeypatch.setattr(paths, "STATE", state)
    monkeypatch.setattr(paths, "TRACES", state / "traces.duckdb")
    monkeypatch.setattr(paths, "CHECKPOINTS", state / "checkpoints.sqlite")
    monkeypatch.delenv("GOVERNOR_TRACE_TEXT", raising=False)
    monkeypatch.setenv("GOVERNOR_LLM", "fake")
    monkeypatch.setenv("GOVERNOR_API_TOKENS", TOKENS)
    yield state
    service.reset()  # close the checkpoint connection before the temp dir goes


@pytest.fixture
def make_client():
    """A TestClient on a fresh app; pass ``llm=`` to script the model."""
    from governor.api.app import create_app

    def make(**kwargs) -> TestClient:
        return TestClient(create_app(**kwargs), raise_server_exceptions=False)

    return make


@pytest.fixture
def client(make_client) -> TestClient:
    return make_client()
