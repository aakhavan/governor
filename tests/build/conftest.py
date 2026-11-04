"""Shared build fixtures: an offline profile of the synthetic sample and the sample design."""
import copy
import csv
import json
from pathlib import Path

import pytest

from governor.build.models import Profile
from governor.build.profile import infer_type, load_policy

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "testbed" / "sample"
POLICY = ROOT / "knowledge" / "shop" / "policy.yaml"
FIXTURES = ROOT / "tests" / "fixtures" / "build"


def sample_profile() -> dict:
    """A section 5 profile computed in Python from testbed/sample (names, types, counts and PII flags)."""
    policy = load_policy(POLICY)
    tables = []
    for f in sorted(SAMPLE.glob("*.csv")):
        with f.open(newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
            names = list(rows[0].keys()) if rows else []
        cols, keys = [], []
        for name in names:
            values = [(r[name] or "").strip() or None for r in rows]
            nonnull = [v for v in values if v is not None]
            pii = name in policy or f"{f.stem}.{name}" in policy
            cols.append({"name": name, "inferred_type": infer_type(values),
                         "null_rate": round(1 - len(nonnull) / len(rows), 6) if rows else 0.0,
                         "distinct": len(set(nonnull)), "pii": pii, "min": None, "max": None})
            if rows and len(nonnull) == len(rows) and len(set(nonnull)) == len(rows):
                keys.append([name])
        tables.append({"name": f.stem, "rows": len(rows), "columns": cols, "candidate_keys": keys})
    return Profile.model_validate({"schema": "raw", "profiled_at_rows": True, "tables": tables,
                                   "relationships": []}).to_json_dict()


@pytest.fixture(scope="session")
def profile_dict() -> dict:
    return sample_profile()


@pytest.fixture
def profile(profile_dict) -> dict:
    return copy.deepcopy(profile_dict)


@pytest.fixture(scope="session")
def _good() -> dict:
    return json.loads((FIXTURES / "sample_design.json").read_text(encoding="utf-8"))


@pytest.fixture
def good(_good) -> dict:
    return copy.deepcopy(_good)


@pytest.fixture(scope="session")
def policy() -> dict:
    return load_policy(POLICY)
