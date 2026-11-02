"""C1 acceptance: no question text left in stored state after a run, OpenAPI hidden by default,
dry-run respects the timeout, the Docker image builds and runs as non-root."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import check, finish, guarded, last_json, py_json, pytest_check, run, tail  # noqa: E402

MARKER = "zqxjkmarker"


def _cli(args, env):
    return run([sys.executable, "-m", "governor.ask.run", *args, "--llm", "fake"], timeout=300, env=env)


def checkpoint_privacy():
    with tempfile.TemporaryDirectory() as d:
        env = dict(os.environ, GOVERNOR_STATE_DIR=d)
        env.pop("GOVERNOR_TRACE_TEXT", None)
        r = _cli([f"how many accounts are there {MARKER}", "--role", "analyst"], env)
        out = last_json(r.stdout) or {}
        if not check("CLI runs with the fake LLM", r.returncode == 0 and "outcome" in out, tail(r)):
            return
        if out.get("outcome") == "clarify":
            r = _cli(["--resume", out["thread_id"], "--answer", "all accounts"], env)
            check("paused thread resumes", r.returncode == 0, tail(r))
        files = [p for p in Path(d).rglob("*") if p.is_file()]
        check("state files written", bool(files), f"{len(files)} files")
        leaked = sorted({p.name for p in files if MARKER.encode() in p.read_bytes()})
        check("no stored file still contains the question text after the run", not leaked, ", ".join(leaked))


APP = ("import json\nfrom fastapi.testclient import TestClient\nfrom governor.api.app import create_app\n"
       "c = TestClient(create_app(tokens='analyst:t0k3n-accept-c1'))\n"
       "print(json.dumps({'openapi': c.get('/openapi.json').status_code, 'health': c.get('/health').status_code}))")


def openapi_hidden():
    base = dict(os.environ, GOVERNOR_LLM="fake")
    base.pop("GOVERNOR_API_DOCS", None)
    d, err = py_json(APP, env=base)
    if check("app starts", d is not None, err):
        check("/openapi.json is 404 by default", d["openapi"] == 404, str(d))
        check("/health still answers", d["health"] == 200, str(d))
    d, err = py_json(APP, env=dict(base, GOVERNOR_API_DOCS="1"))
    if check("app starts with GOVERNOR_API_DOCS=1", d is not None, err):
        check("/openapi.json is served when GOVERNOR_API_DOCS=1", d["openapi"] == 200, str(d))


def dry_run_timeout():
    d, err = py_json("import inspect, json\nfrom governor.ask import executor as e\n"
                     "print(json.dumps({'p': 'timeout_s' in inspect.signature(e.dry_run).parameters}))")
    if check("executor imports", d is not None, err):
        check("dry_run takes timeout_s", d["p"], str(d))


def docker_image():
    r = run(["docker", "version", "--format", "{{.Server.Version}}"], timeout=60)
    if not check("Docker is running", r.returncode == 0, tail(r)):
        return
    r = run(["docker", "build", "-q", "-t", "governor-accept:c1", "."], timeout=1800)
    if not check("docker build succeeds", r.returncode == 0, tail(r)):
        return
    r = run(["docker", "run", "--rm", "--entrypoint", "id", "governor-accept:c1", "-u"], timeout=120)
    uid = (r.stdout or "").strip()
    check("container runs as a non-root user", r.returncode == 0 and uid not in ("", "0"), f"uid {uid!r} {tail(r)}")


guarded("checkpoint privacy", checkpoint_privacy)
guarded("openapi", openapi_hidden)
guarded("dry-run timeout", dry_run_timeout)
guarded("docker image", docker_image)
pytest_check("tests", required=["test_checkpoints_deleted_after_answer", "test_paused_thread_kept_until_resume",
                                "test_openapi_hidden_by_default", "test_dry_run_respects_timeout"])
finish("C1")
