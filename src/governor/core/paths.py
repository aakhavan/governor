"""Every filesystem location governor uses, relative to one repo root.

ROOT is the repo root. Set GOVERNOR_ROOT to point the package at another
checkout (tests, deployments). Nothing else in the package builds a path
from ``__file__``.
"""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path


def _root() -> Path:
    override = os.environ.get("GOVERNOR_ROOT")
    if override:
        return Path(override).resolve()
    return Path(__file__).resolve().parents[3]


ROOT = _root()
ARTIFACTS = ROOT / "artifacts"
GREEN = ARTIFACTS / "green"
WAREHOUSE = GREEN / "warehouse.duckdb"
META = ARTIFACTS / "meta.duckdb"
KNOWLEDGE = ROOT / "knowledge"
TRACES = ARTIFACTS / "traces.duckdb"
LOGS = ROOT / "logs"
STATE = ROOT / ".state"
FIXTURE = ROOT / "fixture"
DBT_PROJECT = FIXTURE / "billing_mart"


def as_of(green: Path | None = None) -> datetime:
    """The instant the green build was taken, from ``GREEN/as_of.txt``.

    Relative dates ("last month", "overdue") resolve against this, never
    against the wall clock.
    """
    path = (green or GREEN) / "as_of.txt"
    if not path.is_file():
        raise FileNotFoundError(f"{path} is missing. run: uv run python fixture/build_green.py")
    return datetime.fromisoformat(path.read_text(encoding="utf-8").strip())
