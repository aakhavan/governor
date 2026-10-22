"""paths: one repo root, overridable, and as_of read from the green build."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from governor.core import paths


def test_root_is_the_repo_and_children_hang_off_it():
    assert (paths.ROOT / "pyproject.toml").is_file()
    assert (paths.ROOT / "src" / "governor" / "core" / "paths.py").is_file()
    assert paths.ARTIFACTS == paths.ROOT / "artifacts"
    assert paths.GREEN == paths.ROOT / "artifacts" / "green"
    assert paths.WAREHOUSE == paths.GREEN / "warehouse.duckdb"
    assert paths.META == paths.ROOT / "artifacts" / "meta.duckdb"
    assert paths.TRACES == paths.ROOT / "artifacts" / "traces.duckdb"
    assert paths.KNOWLEDGE == paths.ROOT / "knowledge"


def test_governor_root_env_overrides_the_root(tmp_path: Path):
    # A fresh interpreter, so the override is seen at import time and this
    # process keeps its own paths.
    env = {**os.environ, "GOVERNOR_ROOT": str(tmp_path)}
    code = (
        "import json; from governor.core import paths as p; "
        "print(json.dumps({'root': str(p.ROOT), 'warehouse': str(p.WAREHOUSE)}))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], env=env, capture_output=True, text=True, check=True
    ).stdout
    data = json.loads(out.strip().splitlines()[-1])
    assert Path(data["root"]) == tmp_path.resolve()
    assert Path(data["warehouse"]) == tmp_path.resolve() / "artifacts" / "green" / "warehouse.duckdb"


def test_as_of_reads_the_green_file(tmp_path: Path):
    (tmp_path / "as_of.txt").write_text("2026-10-01T06:30:00+00:00\n", encoding="utf-8")
    assert paths.as_of(tmp_path) == datetime(2026, 10, 1, 6, 30, tzinfo=timezone.utc)


def test_as_of_names_the_build_command_when_missing(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="build_green.py"):
        paths.as_of(tmp_path)
