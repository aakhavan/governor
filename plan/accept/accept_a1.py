"""A1 acceptance (governor worktree): additive-only diff, DAG contract, workload runs in governor:local, tests green."""
import ast
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, run, tail  # noqa: E402

DAG = ROOT / "airflow/dags/governor_profile_raw.py"
ALLOWED_TOP = {"airflow", "docker", "datetime", "pendulum", "json", "os", "pathlib", "typing", "__future__"}
EDITABLE = {"src/governor/api/app.py": 3, "apps/streamlit/client.py": 40}


def diff():
    base = run(["git", "merge-base", "HEAD", "main"]).stdout.strip() or "main"
    r = run(["git", "diff", "--numstat", base])
    tracked = {}
    for line in r.stdout.splitlines():
        a, d, path = line.split("\t", 2)
        tracked[path] = (int(a) if a.isdigit() else 0, int(d) if d.isdigit() else 0)
    for path, (a, d) in tracked.items():
        if path in EDITABLE:
            check(f"{path} only gains lines (<= {EDITABLE[path]})", d == 0 and a <= EDITABLE[path], f"+{a} -{d}")
        elif not path.startswith(("NOTES", "STATUS", "plan/", "plan-airflow.yaml")):
            check(f"{path} untouched (existing file)", False, f"+{a} -{d}")
    check("diff inspected", r.returncode == 0, tail(r))


def dag_static():
    if not check("DAG file exists", DAG.is_file(), str(DAG)):
        return
    src = DAG.read_text(encoding="utf-8")
    tree = ast.parse(src)
    mods = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.Import):
            mods |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom) and n.module:
            mods.add(n.module.split(".")[0])
    check("DAG imports allowed modules only", mods <= ALLOWED_TOP, ",".join(sorted(mods - ALLOWED_TOP)))
    check("dag_id governor_profile_raw", "governor_profile_raw" in src)
    check("manual only", re.search(r"schedule\s*=\s*None", src) is not None)
    check("no literal password", "governor_build_local" not in src and not re.search(r"PASSWORD[\"']?\s*:\s*[\"'][^{]", src))
    check("uses Variables for connection values", "var.value" in src or "Variable.get" in src)


def workload():
    b = run(["docker", "build", "-t", "governor:local", "."], timeout=2400)
    if not check("governor:local builds from the worktree", b.returncode == 0, tail(b)):
        return
    pg = run(["docker", "ps", "--filter", "publish=55432", "--format", "{{.Names}}"])
    if not check("test bed up on 55432", bool(pg.stdout.strip()), "start ../governor/testbed first"):
        return
    vols = run(["docker", "volume", "ls", "--format", "{{.Name}}"]).stdout.split()
    vol = next((v for v in vols if v.endswith("governor-data")), "governor_governor-data")
    r = run(["docker", "run", "--rm", "--add-host=host.docker.internal:host-gateway", "-e", "GOVERNOR_PG_HOST=host.docker.internal",
             "-v", f"{vol}:/data", "governor:local", "python", "-m", "governor.build", "profile", "--schema", "raw",
             "--policy", "knowledge/shop/policy.yaml", "--out", "/data/profiles/a1_probe.json"], timeout=600)
    out = None
    for line in reversed(r.stdout.strip().splitlines()):
        try:
            out = json.loads(line)
            break
        except ValueError:
            continue
    check("profile runs as a container against the test bed", r.returncode == 0 and bool(out) and out.get("tables", 0) > 0,
          tail(r) if not out else f"{out.get('tables')} tables")


def tests():
    r = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-m", "not llm", "tests"], timeout=1800)
    summary = next((l for l in reversed(r.stdout.strip().splitlines()) if "passed" in l or "failed" in l or "error" in l), tail(r))
    check("full offline test suite green", r.returncode == 0, summary)
    c = run([sys.executable, "-m", "pytest", "--collect-only", "-q", "-p", "no:cacheprovider", "tests"], timeout=600)
    names = set(re.findall(r"::(test_[A-Za-z0-9_]+)", c.stdout))
    need = ["test_profiles_router_lists_and_returns", "test_profiles_router_rejects_traversal", "test_profiles_router_requires_auth",
            "test_dag_imports_no_governor", "test_dag_has_no_literal_password", "test_dag_is_manual_only"]
    missing = [t for t in need if t not in names]
    check("required tests present", not missing, f"missing: {missing}" if missing else "6 found")


guarded("diff", diff)
guarded("dag_static", dag_static)
guarded("tests", tests)
guarded("workload", workload)
finish("A1")
