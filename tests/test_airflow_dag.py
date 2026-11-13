"""The Airflow DAG airflow/dags/governor_profile_raw.py, checked statically (Airflow is not installed here)."""

from __future__ import annotations

import ast
import re
from pathlib import Path

DAG_FILE = Path(__file__).resolve().parents[1] / "airflow" / "dags" / "governor_profile_raw.py"
ALLOWED = {"airflow", "docker", "datetime", "pendulum", "json", "os", "pathlib", "typing", "__future__"}


def _tree() -> ast.Module:
    return ast.parse(DAG_FILE.read_text(encoding="utf-8"))


def _call_kwargs(name: str) -> dict[str, ast.expr]:
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Call) and getattr(node.func, "id", None) == name:
            return {k.arg: k.value for k in node.keywords if k.arg}
    raise AssertionError(f"no {name}(...) call")


def test_dag_imports_no_governor():
    mods = set()
    for node in ast.walk(_tree()):
        if isinstance(node, ast.Import):
            mods |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, "no relative imports"
            mods.add((node.module or "").split(".")[0])
    assert "governor" not in mods
    assert mods <= ALLOWED, mods - ALLOWED


def test_dag_has_no_literal_password():
    src = DAG_FILE.read_text(encoding="utf-8")
    assert "governor_build_local" not in src
    assert not re.search(r"PASSWORD[\"']?\s*:\s*[\"'][^{]", src)
    env = _call_kwargs("_RenderedDockerOperator")["environment"]
    assert isinstance(env, ast.Dict)
    values = {ast.literal_eval(k): ast.literal_eval(v) for k, v in zip(env.keys, env.values)}
    assert set(values) == {"GOVERNOR_PG_HOST", "GOVERNOR_PG_PORT", "GOVERNOR_PG_DB", "GOVERNOR_BUILD_USER",
                           "GOVERNOR_BUILD_PASSWORD"}
    for value in values.values():  # every value is a Variable rendered at run time
        assert re.fullmatch(r"\{\{ var\.value\.get\('[a-z_]+'(, '[^']*')?\) \}\}", value), value
    assert values["GOVERNOR_BUILD_PASSWORD"] == "{{ var.value.get('governor_build_password') }}"


def test_dag_is_manual_only():
    kw = _call_kwargs("DAG")
    assert ast.literal_eval(kw["dag_id"]) == "governor_profile_raw"
    assert isinstance(kw["schedule"], ast.Constant) and kw["schedule"].value is None
    assert ast.literal_eval(kw["catchup"]) is False
    assert ast.literal_eval(kw["tags"]) == ["governor"]
    task = _call_kwargs("_RenderedDockerOperator")
    assert ast.literal_eval(task["task_id"]) == "profile"
    assert ast.literal_eval(task["image"]) == "governor:local"
    assert ast.literal_eval(task["mount_tmp_dir"]) is False
    assert ast.literal_eval(task["auto_remove"]) == "success"
    assert "/data/profiles/{{ run_id | replace(':', '_') }}.json" in ast.literal_eval(task["command"])
