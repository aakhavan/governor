"""V6 acceptance: Docker, screenshots, docs and README (docs/capstone/batch4.md section 39).

Builds the console against an API started here in open mode (demo runs only, empty state dir), serves it with
`vite preview`, installs Playwright's Chromium if needed and runs the screenshot script.
"""
import os
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _console import APP, env_clean, free_port, node, npm_step, front_end_checks  # noqa: E402

env_clean()
from _common import ROOT, check, finish, guarded, pytest_check  # noqa: E402

SHOTS = ["console-runs.png", "console-build-live.png", "console-build-lineage.png", "console-ask-guard.png"]


def static():
    dc = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    check("compose console service", "console:" in dc and "8080" in dc, "missing console service on 8080")
    check("compose keeps console closed by default", "GOVERNOR_CONSOLE_OPEN=1" not in dc and "GOVERNOR_CONSOLE_OPEN: \"1\"" not in dc
          and "GOVERNOR_CONSOLE_OPEN: 1" not in dc, "open mode set by default")
    check("console Dockerfile", (APP / "Dockerfile").is_file() and "nginx" in (APP / "Dockerfile").read_text(encoding="utf-8"), "missing")
    check("nginx config", (APP / "nginx.conf").is_file(), "missing")
    doc = ROOT / "docs/console.md"
    t = doc.read_text(encoding="utf-8") if doc.is_file() else ""
    check("docs/console.md", "LangGraph Studio" in t and "replay" in t.lower(), "missing or incomplete")
    check("README run console section", "Run console" in (ROOT / "README.md").read_text(encoding="utf-8"), "missing")
    check("screenshot script", (APP / "scripts/screenshots.mjs").is_file(), "missing")


def _wait(url: str, secs: float = 60) -> bool:
    end = time.time() + secs
    while time.time() < end:
        try:
            with urllib.request.urlopen(url, timeout=3) as r:
                if r.status < 500:
                    return True
        except Exception:  # noqa: BLE001
            time.sleep(0.5)
    return False


def _kill(p) -> None:
    if p is None or p.poll() is not None:
        return
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(p.pid), "/T", "/F"], capture_output=True)
    else:
        p.terminate()
        try:
            p.wait(10)
        except subprocess.TimeoutExpired:
            p.kill()


def screenshots():
    api_port, ui_port = free_port(), free_port()
    origin = f"http://127.0.0.1:{ui_port}"
    state = tempfile.mkdtemp(prefix="governor-v6-")
    env = {**os.environ, "GOVERNOR_CONSOLE_OPEN": "1", "GOVERNOR_CONSOLE_ORIGINS": origin, "GOVERNOR_STATE_DIR": state}
    env.pop("OPENROUTER_API_KEY", None)
    api = ui = None
    out_dir = ROOT / "docs" / "showcase"
    started = time.time()
    try:
        api = subprocess.Popen([sys.executable, "-m", "uvicorn", "governor.api.app:app", "--host", "127.0.0.1",
                                "--port", str(api_port)], cwd=ROOT, env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not check("API up in open mode", _wait(f"http://127.0.0.1:{api_port}/v1/console/runs"), f"port {api_port}"):
            return
        benv = {**os.environ, "VITE_API_BASE": f"http://127.0.0.1:{api_port}/"}
        if not npm_step("build against the test API", ["run", "build"], env=benv):
            return
        n = node()
        ui = subprocess.Popen([n, "node_modules/vite/bin/vite.js", "preview", "--host", "127.0.0.1", "--port",
                               str(ui_port), "--strictPort"], cwd=APP, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if not check("vite preview up", _wait(origin), origin):
            return
        npm_step("playwright chromium", ["exec", "--", "playwright", "install", "chromium"], timeout=1200)
        npm_step("screenshots", ["run", "screenshots", "--", "--url", origin, "--out", str(out_dir)], timeout=600)
        for s in SHOTS:
            p = out_dir / s
            fresh = p.is_file() and p.stat().st_mtime >= started - 5
            check(f"screenshot {s}", fresh and p.stat().st_size > 30_000, "missing, stale or tiny" if not fresh else f"{p.stat().st_size} bytes")
    finally:
        _kill(ui)
        _kill(api)


guarded("static", static)
front_end_checks()
guarded("screenshots", screenshots)
pytest_check("tests")
pytest_check("tests/build")
finish("V6")
