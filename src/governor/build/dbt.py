"""Run dbt as a subprocess for a target project and read its run_results.json."""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class DbtResult:
    ok: bool
    returncode: int
    results: list[dict] = field(default_factory=list)  # {unique_id, status, message}
    log_tail: str = ""


def dbt_executable() -> Path:
    """The dbt next to sys.executable; symlinks are not resolved (a venv python links to the base one)."""
    scripts = Path(sys.executable).parent
    for name in ("dbt.exe", "dbt"):
        candidate = scripts / name
        if candidate.is_file():
            return candidate
    raise FileNotFoundError(f"dbt is not installed next to {sys.executable}")


def _read_results(target: Path) -> list[dict]:
    path = target / "target" / "run_results.json"
    if not path.is_file():
        return []
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("results", [])
    except (OSError, ValueError):
        return []
    return [{"unique_id": r.get("unique_id"), "status": r.get("status"), "message": r.get("message")} for r in raw]


def run_dbt(target: Path, args: list[str], timeout_s: int = 600, env: dict[str, str] | None = None) -> DbtResult:
    """``env``: the full environment for dbt (certify passes the deploy login); default the caller's."""
    target = Path(target)
    stale = target / "target" / "run_results.json"
    if stale.is_file():
        stale.unlink()  # a command that writes none (parse) must not report an old run
    command = [
        str(dbt_executable()),
        *args,
        "--project-dir", str(target),
        "--profiles-dir", str(target / "profiles"),
        "--no-use-colors",
    ]
    try:
        proc = subprocess.run(
            command, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout_s, env=env
        )
    except subprocess.TimeoutExpired as e:
        out = e.stdout if isinstance(e.stdout, str) else (e.stdout or b"").decode("utf-8", "replace")
        return DbtResult(False, -1, [], (out + f"\ndbt timed out after {timeout_s}s")[-4000:])
    log = ((proc.stdout or "") + (proc.stderr or ""))[-4000:]
    return DbtResult(proc.returncode == 0, proc.returncode, _read_results(target), log)
