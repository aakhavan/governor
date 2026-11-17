"""The F2 drift tests (tests/build/test_drift.py), also collected from ``tests``.

Pytest's default ``norecursedirs`` contains ``build``, so ``pytest tests`` never enters tests/build/. This module
loads that test file and its conftest by path and re-exports their tests and fixtures; the tests live in one place.
"""
import importlib.util
from pathlib import Path

_BUILD = Path(__file__).resolve().parents[1] / "build"


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


_conftest = _load("_governor_build_conftest_f2", _BUILD / "conftest.py")
_tests = _load("_governor_build_test_drift_f2", _BUILD / "test_drift.py")

# fixtures the drift tests use (the autouse state folder included)
_state_dir = _conftest._state_dir
profile_dict = _conftest.profile_dict
profile = _conftest.profile
_good = _conftest._good
good = _conftest.good

test_fingerprint_has_no_counts_or_values = _tests.test_fingerprint_has_no_counts_or_values
test_fingerprint_is_stable_across_order = _tests.test_fingerprint_is_stable_across_order
test_diff_empty_for_same_profile = _tests.test_diff_empty_for_same_profile
test_diff_reports_added_and_removed = _tests.test_diff_reports_added_and_removed
test_diff_reports_type_pii_and_key_changes = _tests.test_diff_reports_type_pii_and_key_changes
test_approval_writes_fingerprint = _tests.test_approval_writes_fingerprint
