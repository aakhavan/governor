"""D1 acceptance: compose port from env (acceptance on its own port), governor_build reads raw and still writes only
dev_governor, target dbt workspace with env-only credentials, dbt runner."""
import hashlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, py_json, pytest_check, run, tail  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402


def static():
    compose = (ROOT / "testbed" / "docker-compose.yml").read_text(encoding="utf-8")
    check("compose maps the host port from GOVERNOR_PG_PORT", "GOVERNOR_PG_PORT" in compose, "")
    pp = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    check("dbt-postgres is a dependency", "dbt-postgres" in pp, "")
    for rel in ("src/governor/build/workspace.py", "src/governor/build/dbt.py", "src/governor/build/__main__.py"):
        check(f"{rel} exists", (ROOT / rel).is_file(), "missing")


def database():
    work = bd.workdir()
    e = bd.env(work / "state")
    if not bd.testbed_ready():
        return
    try:
        r = run(tb.COMPOSE + ["port", "postgres", "5432"], timeout=60, env=tb.env())
        check("acceptance stack listens on its own port", tb.PORT in (r.stdout or ""), tail(r))
        code = (
            "import json,psycopg\n"
            f"out={{}}\n"
            f"with psycopg.connect({tb.BUILD_DSN!r}, autocommit=True) as c:\n"
            "    out['reads_raw']=c.execute('select count(*) from raw.olist_orders_dataset').fetchone()[0]>0\n"
            "    try:\n"
            "        c.execute('create table raw.governor_probe(x int)'); out['create_raw']='allowed'\n"
            "    except Exception as ex: out['create_raw']=type(ex).__name__\n"
            "    try:\n"
            "        c.execute('create table dev_governor.governor_probe(x int)'); c.execute('drop table dev_governor.governor_probe'); out['create_dev']='ok'\n"
            "    except Exception as ex: out['create_dev']=type(ex).__name__\n"
            "    out['private']=c.execute(\"select has_schema_privilege('private','USAGE')\").fetchone()[0]\n"
            "print(json.dumps(out))")
        d, err = py_json(code, env=e)
        if check("build-role probe runs", d is not None, err):
            check("governor_build can read raw", d["reads_raw"] is True, str(d))
            check("governor_build cannot create in raw", d["create_raw"] == "InsufficientPrivilege", str(d))
            check("governor_build can create in dev_governor", d["create_dev"] == "ok", str(d))
            check("governor_build has no access to private", d["private"] is False, str(d))
        target = bd.init_target(work, e)
        if target is None:
            return
        for rel in ("dbt_project.yml", "profiles/profiles.yml", "models/sources.yml", "models/staging", "models/intermediate",
                    "models/marts", "tests", "governor"):
            check(f"target has {rel}", (target / rel).exists(), "missing")
        profiles = (target / "profiles" / "profiles.yml").read_text(encoding="utf-8")
        check("profiles.yml reads credentials through env_var", "env_var(" in profiles and "dev_governor" in profiles, "")
        leaked = [str(p.relative_to(target)) for p in target.rglob("*") if p.is_file()
                  and tb.BUILD_PW in p.read_text(encoding="utf-8", errors="replace")]
        check("no password written into the target", not leaked, str(leaked))
        sources = (target / "models" / "sources.yml").read_text(encoding="utf-8")
        check("sources.yml declares the raw tables with columns", "olist_orders_dataset" in sources and "order_purchase_timestamp" in sources, "")
        before = hashlib.sha256((target / "dbt_project.yml").read_bytes()).hexdigest()
        d2, err2 = bd.cli(["init", "--target", str(target), "--project-name", "shop"], e)
        after = hashlib.sha256((target / "dbt_project.yml").read_bytes()).hexdigest()
        check("init is idempotent", d2 is not None and before == after, err2)
        code = ("import json\nfrom pathlib import Path\nfrom governor.build.dbt import run_dbt\n"
                f"r=run_dbt(Path({str(target)!r}), ['parse'])\nprint(json.dumps({{'ok': r.ok, 'tail': r.log_tail[-300:]}}))")
        d3, err3 = py_json(code, env=e, timeout=600)
        check("dbt parse succeeds through run_dbt", d3 is not None and d3.get("ok") is True, err3 or str(d3))
    finally:
        tb.down()


guarded("static", static)
guarded("database", database)
pytest_check("tests/build")
finish("D1")
