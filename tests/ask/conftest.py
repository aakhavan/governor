"""Keep graph runs in tests away from the real trace store and checkpoints."""

from __future__ import annotations

import pytest

from governor.core import paths


@pytest.fixture(autouse=True)
def _state_dir(tmp_path_factory, monkeypatch):
    state = tmp_path_factory.mktemp("state")
    monkeypatch.setattr(paths, "STATE", state)
    monkeypatch.setattr(paths, "TRACES", state / "traces.duckdb")
    monkeypatch.setattr(paths, "CHECKPOINTS", state / "checkpoints.sqlite")
    monkeypatch.delenv("GOVERNOR_TRACE_TEXT", raising=False)
    return state
