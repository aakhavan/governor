"""GET /profiles and /profiles/{run_id}: stored raw profiles behind the API's bearer auth (offline, temp state dir)."""

from __future__ import annotations

import json
import os

import pytest
from fastapi.testclient import TestClient

from governor.ask import service
from governor.core import paths

TOKENS = "analyst:test-analyst-token,finance_admin:test-admin-token"
ANALYST = {"Authorization": "Bearer test-analyst-token"}
RUN_ID = "manual__2026-11-13T10_00_00+00_00"
PROFILE = {
    "schema": "raw", "profiled_at_rows": True,
    "tables": [{"name": "customers", "rows": 3, "candidate_keys": [["customer_id"]], "columns": [
        {"name": "customer_id", "inferred_type": "text", "null_rate": 0.0, "distinct": 3, "pii": False, "min": None, "max": None},
        {"name": "email", "inferred_type": "text", "null_rate": 0.0, "distinct": 3, "pii": True, "min": None, "max": None},
    ]}],
    "relationships": [],
}


@pytest.fixture
def state(tmp_path, monkeypatch):
    state = tmp_path / "state"
    (state / "profiles").mkdir(parents=True)
    monkeypatch.setattr(paths, "STATE", state)
    monkeypatch.setattr(paths, "TRACES", state / "traces.duckdb")
    monkeypatch.setattr(paths, "CHECKPOINTS", state / "checkpoints.sqlite")
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(state))
    monkeypatch.setenv("GOVERNOR_LLM", "fake")
    monkeypatch.setenv("GOVERNOR_API_TOKENS", TOKENS)
    yield state
    service.reset()


@pytest.fixture
def client(state) -> TestClient:
    from governor.api.app import create_app

    return TestClient(create_app(), raise_server_exceptions=False)


def _store(state, run_id: str, body: dict, mtime: float) -> bytes:
    text = json.dumps(body, indent=1).encode("utf-8")
    file = state / "profiles" / f"{run_id}.json"
    file.write_bytes(text)
    os.utime(file, (mtime, mtime))
    return text


def test_profiles_router_lists_and_returns(client, state):
    assert client.get("/profiles", headers=ANALYST).json() == {"profiles": []}
    older = _store(state, "older_run", {**PROFILE, "tables": []}, 1_700_000_000)
    stored = _store(state, RUN_ID, PROFILE, 1_800_000_000)
    (state / "profiles" / "notes.txt").write_text("not a profile", encoding="utf-8")

    r = client.get("/profiles", headers=ANALYST)
    assert r.status_code == 200, r.text
    assert r.json() == {"profiles": [RUN_ID, "older_run"]}  # newest first, .json files only

    r = client.get(f"/profiles/{RUN_ID}", headers=ANALYST)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("application/json")
    assert r.content == stored  # unchanged, byte for byte
    assert r.json()["tables"][0]["columns"][1]["pii"] is True
    assert client.get("/profiles/older_run", headers=ANALYST).content == older

    r = client.get("/profiles/missing_run", headers=ANALYST)
    assert r.status_code == 404
    assert r.json()["code"] == "not_found"


def test_profiles_router_lists_at_most_100(client, state):
    for i in range(105):
        _store(state, f"run_{i:03d}", PROFILE, 1_700_000_000 + i)
    ids = client.get("/profiles", headers=ANALYST).json()["profiles"]
    assert len(ids) == 100
    assert ids[0] == "run_104" and ids[-1] == "run_005"


@pytest.mark.parametrize("run_id", ["bad id", "a;b", "a%5Cb", "a:b", "x" * 129, "%2E%2E%5Csecret"])
def test_profiles_router_rejects_traversal(client, state, run_id):
    (state / "secret.json").write_text('{"secret": "outside the profiles folder"}', encoding="utf-8")
    r = client.get(f"/profiles/{run_id}", headers=ANALYST)
    assert r.status_code == 422, r.text
    assert r.json()["code"] == "invalid_request"
    assert "outside the profiles folder" not in r.text


@pytest.mark.parametrize("path", ["/profiles/..%2Fsecret", "/profiles/../secret", "/profiles/%2E%2E/secret"])
def test_profiles_router_never_leaves_the_folder(client, state, path):
    (state / "secret.json").write_text('{"secret": "outside the profiles folder"}', encoding="utf-8")
    r = client.get(path, headers=ANALYST)
    assert r.status_code in (404, 422), r.text
    assert "outside the profiles folder" not in r.text


@pytest.mark.parametrize("headers", [{}, {"Authorization": "Bearer nope"}, {"Authorization": "Basic test-analyst-token"}])
def test_profiles_router_requires_auth(client, state, headers):
    _store(state, RUN_ID, PROFILE, 1_800_000_000)
    for path in ("/profiles", f"/profiles/{RUN_ID}", "/profiles/bad%20id"):
        r = client.get(path, headers=headers)
        assert r.status_code == 401, (path, r.text)
        assert r.json()["code"] == "unauthorized"
        assert "customers" not in r.text
