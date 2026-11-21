"""Helpers for batch-4 acceptance (console front end). Stdlib only."""
from __future__ import annotations

import json
import os
import re
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from _common import ROOT, check, run

APP = ROOT / "apps" / "console"


def env_clean() -> None:
    """Pin the test bed to the empty acceptance port and drop secrets/targets, as in batch 3."""
    for k, v in {"GOVERNOR_PG_PORT": "55433", "GOVERNOR_PG_HOST": "localhost"}.items():
        os.environ[k] = v
    for k in ("GOVERNOR_PG_DSN", "GOVERNOR_PG_ADMIN_DSN", "GOVERNOR_BUILD_DSN", "GOVERNOR_BUILD_PASSWORD",
              "GOVERNOR_DEPLOY_PASSWORD", "GOVERNOR_ROOT", "GOVERNOR_TENANTS", "GOVERNOR_SLACK_TARGETS",
              "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "GOVERNOR_CONSOLE_OPEN", "GOVERNOR_RUNTRACE"):
        os.environ.pop(k, None)


def npm() -> str | None:
    return shutil.which("npm") or shutil.which("npm.cmd")


def node() -> str | None:
    return shutil.which("node") or shutil.which("node.exe")


def node_ok() -> bool:
    n = node()
    if not n:
        return check("node 20+ on PATH", False, "node not found: install Node.js 20 LTS")
    r = run([n, "--version"], timeout=30)
    m = re.match(r"v(\d+)", (r.stdout or "").strip())
    return check("node 20+ on PATH", bool(m and int(m.group(1)) >= 20), (r.stdout or r.stderr).strip())


def npm_step(name: str, args: list[str], timeout: float = 900, env: dict | None = None) -> bool:
    exe = npm()
    if not exe:
        return check(name, False, "npm not found")
    r = subprocess.run([exe, *args], cwd=APP, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, env=env)
    lines = ((r.stdout or "") + "\n" + (r.stderr or "")).strip().splitlines()
    return check(name, r.returncode == 0, " | ".join(lines[-3:])[:240])


def package() -> dict:
    p = APP / "package.json"
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def deps_present(names: list[str]) -> None:
    pkg = package()
    allp = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
    missing = [n for n in names if n not in allp]
    check("console dependencies", not missing, f"missing: {missing}" if missing else "ok")


def scripts_present(names: list[str]) -> None:
    s = package().get("scripts", {})
    missing = [n for n in names if n not in s]
    check("npm scripts", not missing, f"missing: {missing}" if missing else "ok")


def test_titles_present(titles: list[str]) -> None:
    text = ""
    for p in list((APP / "src").rglob("*.test.ts")) + list((APP / "src").rglob("*.test.tsx")):
        text += p.read_text(encoding="utf-8", errors="replace")
    missing = [t for t in titles if t not in text]
    check("required console tests present", not missing, f"missing: {missing}" if missing else f"{len(titles)} found")


def front_end_checks() -> bool:
    """npm ci, lint, typecheck, test, build. Returns True when all pass."""
    if not node_ok() or not (APP / "package.json").is_file():
        check("apps/console/package.json", (APP / "package.json").is_file(), "missing")
        return False
    ok = npm_step("npm ci", ["ci", "--no-audit", "--no-fund"], timeout=1200)
    ok = npm_step("npm run lint", ["run", "lint"]) and ok
    ok = npm_step("npm run typecheck", ["run", "typecheck"]) and ok
    ok = npm_step("npm test", ["run", "test", "--", "--run"]) and ok
    ok = npm_step("npm run build", ["run", "build"]) and ok
    return ok


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def no_tracked_build_output() -> None:
    gi = APP / ".gitignore"
    text = gi.read_text(encoding="utf-8") if gi.is_file() else ""
    check("console .gitignore covers node_modules and dist", "node_modules" in text and "dist" in text, "missing entries")
