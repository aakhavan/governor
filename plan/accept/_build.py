"""Helpers for the batch 2 (D-step) acceptance scripts: test bed on the acceptance port, target dir, build CLI.
Stdlib only at import time."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

from _common import ROOT, check, last_json, py_json, run, tail
import _testbed as tb

FIXTURES = ROOT / "tests" / "fixtures" / "build"
CATALOGUE_KPIS = ["gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purchase_rate",
                  "cohort_retention", "historical_clv", "conversion_rate", "gross_margin"]
BUILD_KPIS = CATALOGUE_KPIS[:8]
DECLINED = ["conversion_rate", "gross_margin"]


def workdir() -> Path:
    return Path(tempfile.mkdtemp(prefix="governor_accept_"))


def env(state_dir: Path) -> dict:
    return tb.env(GOVERNOR_STATE_DIR=str(state_dir))


def testbed_ready() -> bool:
    """Docker up on the acceptance port, sample loaded, roles applied."""
    if not tb.docker_ok() or not tb.up():
        return False
    if tb.load_sample() is None:
        return False
    return tb.apply_roles()


def cli(args: list[str], e: dict, timeout: float = 900) -> tuple[dict | None, str]:
    r = run([sys.executable, "-m", "governor.build", *args], timeout=timeout, env=e)
    d = last_json(r.stdout)
    return (d if isinstance(d, dict) else None), tail(r)


def script(path: Path, **parts) -> str:
    path.write_text(json.dumps(parts), encoding="utf-8")
    return f"fake:{path}"


def fixture(name: str):
    p = FIXTURES / name
    if not p.is_file():
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def init_target(work: Path, e: dict) -> Path | None:
    target = work / "olist-dbt"
    d, err = cli(["init", "--target", str(target), "--project-name", "shop"], e)
    ok = isinstance(d, dict) and len(d.get("tables") or []) == 9
    check("build init lists the 9 raw tables", ok, err if not ok else "")
    return target if ok else None


def admin_query(sql: str, e: dict):
    code = ("import json,os,psycopg\n"
            "with psycopg.connect(os.environ['GOVERNOR_PG_ADMIN_DSN']) as c:\n"
            f"    rows=c.execute({sql!r}).fetchall()\n"
            "print(json.dumps([[str(v) if v is not None else None for v in r] for r in rows]))")
    return py_json(code, env=e)
