"""pages/4_Profiles.py over the API (asgi): the list, the run_id query param, and PII flags as stored."""

from __future__ import annotations

import json

PROFILE = {
    "schema": "raw", "profiled_at_rows": True,
    "tables": [{"name": "customers", "rows": 3, "candidate_keys": [["customer_id"]], "columns": [
        {"name": "customer_id", "inferred_type": "text", "null_rate": 0.0, "distinct": 3, "pii": False, "min": None, "max": None},
        {"name": "email", "inferred_type": "text", "null_rate": 0.0, "distinct": 3, "pii": True, "min": None, "max": None},
    ]}, {"name": "orders", "rows": 5, "candidate_keys": [["order_id"]], "columns": [
        {"name": "order_id", "inferred_type": "text", "null_rate": 0.0, "distinct": 5, "pii": False, "min": None, "max": None},
        {"name": "customer_id", "inferred_type": "text", "null_rate": 0.0, "distinct": 3, "pii": False, "min": None, "max": None},
    ]}],
    "relationships": [{"from": "orders.customer_id", "to": "customers.customer_id", "coverage": 1.0}],
}


def _store(state, run_id: str) -> None:
    (state / "profiles").mkdir(exist_ok=True)
    (state / "profiles" / f"{run_id}.json").write_text(json.dumps(PROFILE), encoding="utf-8")


def test_profiles_page_empty(page, monkeypatch):
    monkeypatch.delenv("GOVERNOR_STATE_DIR", raising=False)
    at = page("pages/4_Profiles.py")
    at.run()
    assert not at.exception
    assert any("No profiles yet" in i.value for i in at.info)


def test_profiles_page_by_query_param(page, _state_dir, monkeypatch):
    monkeypatch.delenv("GOVERNOR_STATE_DIR", raising=False)
    _store(_state_dir, "run_a")
    at = page("pages/4_Profiles.py")
    at.query_params["run_id"] = "run_a"
    at.run()
    assert not at.exception
    metrics = {m.label: m.value for m in at.metric}
    assert metrics["Tables"] == "2" and metrics["Rows"] == "8" and metrics["Relationships"] == "1"
    frames = [d.value for d in at.dataframe]
    assert len(frames) == 4  # tables, relationships, one per raw table
    customers = frames[2]
    assert dict(zip(customers["name"], customers["pii"])) == {"customer_id": False, "email": True}


def test_profiles_page_unknown_run(page, _state_dir, monkeypatch):
    monkeypatch.delenv("GOVERNOR_STATE_DIR", raising=False)
    _store(_state_dir, "run_a")
    at = page("pages/4_Profiles.py")
    at.query_params["run_id"] = "nope"
    at.run()
    assert not at.exception
    assert not at.dataframe
