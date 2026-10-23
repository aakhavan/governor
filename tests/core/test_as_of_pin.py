"""The build instant is pinned in fixture/AS_OF, never read from the clock."""

from __future__ import annotations

import re
import sys
from datetime import datetime, timezone

import pytest

from governor.core import paths

sys.path.insert(0, str(paths.FIXTURE))
import load_raw  # noqa: E402

PIN = "2026-10-22 14:11:26+00:00"


def test_fixture_as_of_holds_the_golden_instant():
    assert load_raw.AS_OF_FILE.read_text(encoding="utf-8").strip() == PIN


def test_pinned_as_of_reads_the_file(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(load_raw.AS_OF_ENV, raising=False)
    assert load_raw.pinned_as_of() == datetime(2026, 10, 22, 14, 11, 26, tzinfo=timezone.utc)
    assert load_raw.pinned_as_of().isoformat(sep=" ", timespec="seconds") == PIN


def test_env_overrides_the_file_and_naive_means_utc(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv(load_raw.AS_OF_ENV, "2026-01-02T03:04:05.678+02:00")
    assert load_raw.pinned_as_of() == datetime(2026, 1, 2, 1, 4, 5, tzinfo=timezone.utc)
    monkeypatch.setenv(load_raw.AS_OF_ENV, "2026-01-02 03:04:05")
    assert load_raw.pinned_as_of() == datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)


def test_build_scripts_never_read_the_wall_clock():
    clock = re.compile(r"datetime\.now|utcnow|date\.today|time\.time\(")
    for name in ("build_green.py", "load_raw.py", "generate_raw.py"):
        text = (paths.FIXTURE / name).read_text(encoding="utf-8")
        assert not clock.search(text), name


def test_green_build_was_stamped_with_the_pin(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv(load_raw.AS_OF_ENV, raising=False)
    if not (paths.GREEN / "as_of.txt").is_file():
        pytest.skip("no green build")
    assert (paths.GREEN / "as_of.txt").read_text(encoding="utf-8").strip() == PIN
    assert paths.as_of() == load_raw.pinned_as_of()
