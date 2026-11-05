"""D6 acceptance: mapping pairs, events, publish (init, branch, commit, pr.md, push), certify refuses before the merge
and deploys after it (analytics, registry, gaps, serving views), governor_deploy writes only analytics."""
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, py_json, pytest_check, run  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402
import _build2 as b2  # noqa: E402


def offline():
    code = ("import json\nfrom governor.build import models\n"
            "src=[m for m in dir(models)]\nprint(json.dumps({'ok': True}))")
    d, err = py_json(code)
    check("build models import", d is not None, err)
    for rel in ("src/governor/build/events.py", "src/governor/build/publish.py", "src/governor/build/certify.py"):
        check(f"{rel} exists", (ROOT / rel).is_file(), "missing")
    roles = (ROOT / "testbed" / "sql" / "roles.sql").read_text(encoding="utf-8")
    check("roles.sql defines governor_deploy", "governor_deploy" in roles, "")


def database():
    work = bd.workdir()
    state = work / "state"
    e = b2.env(state)
    if not bd.testbed_ready():
        return
    try:
        target = b2.built_sample(work, e)
        if target is None:
            return
        events = state / "events.jsonl"
        kinds = [json.loads(l).get("kind") for l in events.read_text(encoding="utf-8").splitlines() if l.strip()] if events.is_file() else []
        check("events log has the build stages", all(k in kinds for k in ("run_started", "design_gate", "approved", "built")), str(kinds)[:200])
        sample_vals = [v for v in ("cust-0001", "ord-0001") if events.is_file() and v in events.read_text(encoding="utf-8")]
        check("events carry no data values", not sample_vals, str(sample_vals))

        pushed = work / "pushed"
        shutil.copytree(target, pushed)
        origin = work / "origin.git"
        run(["git", "init", "--bare", "-b", "main", str(origin)], timeout=60, env=e)
        run(["git", "-C", str(pushed), "init", "-b", "main"], timeout=60, env=e)
        run(["git", "-C", str(pushed), "remote", "add", "origin", str(origin)], timeout=60, env=e)

        d, err = bd.cli(["publish", "--target", str(target)], e)
        ok = d is not None and d.get("status") == "published" and str(d.get("branch", "")).startswith("governor/build-")
        if not check("publish creates a governor/build-* branch", ok, err or str(d)):
            return
        branch = d["branch"]
        log = b2.git(target, "log", "--format=%an|%s", "-1", branch, e=e).stdout.strip()
        check("commit by governor with a summary message", log.startswith("governor|governor: build"), log)
        files = b2.git(target, "ls-tree", "-r", "--name-only", branch, e=e).stdout
        check("branch contains models, tests and governor files",
              all(p in files for p in ("models/marts", "models/staging", "governor/design.md", "governor/pr.md")), "")
        check("main holds only the scaffold", "models/marts" not in b2.git(target, "ls-tree", "-r", "--name-only", "main", e=e).stdout, "")
        pr = (target / "governor" / "pr.md").read_text(encoding="utf-8") if (target / "governor" / "pr.md").is_file() else ""
        check("pr.md has KPIs, gaps, tests and a reviewer checklist",
              all(w in pr.lower() for w in ("gmv", "conversion_rate", "test", "- [ ]")), "")

        d2, err2 = bd.cli(["publish", "--target", str(pushed)], e)
        heads = run(["git", "--git-dir", str(origin), "branch", "--list", "governor/build-*"], timeout=60, env=e).stdout
        check("publish pushes the branch when origin exists", d2 is not None and "governor/build-" in heads, err2 or heads)

        d3, err3 = bd.cli(["certify", "--target", str(target), "--by", "amir"], e)
        check("certify refuses before the merge", d3 is not None and d3.get("status") == "not_merged", err3 or str(d3))

        if not b2.merge(target, branch, e):
            return
        d4, err4 = bd.cli(["certify", "--target", str(target), "--by", "amir"], e, timeout=2400)
        if not check("certify deploys after the merge", d4 is not None and d4.get("status") == "certified", err4 or str(d4)[:200]):
            return
        rows, qerr = bd.admin_query("select kpi_id, certified_by from analytics.governor_certified order by 1", e)
        ids = [r[0] for r in rows or []]
        check("registry lists the 8 certified KPIs, certified by amir",
              sorted(ids) == sorted(bd.BUILD_KPIS) and all(r[1] == "amir" for r in rows), qerr or str(ids))
        rows2, _ = bd.admin_query("select kpi_id from analytics.governor_gaps order by 1", e)
        check("gaps table lists the declined KPIs", sorted(r[0] for r in rows2 or []) == sorted(bd.DECLINED), str(rows2))
        rows3, _ = bd.admin_query("select count(*) from information_schema.views where table_schema = 'serve_analyst' and table_name like 'kpi_%'", e)
        check("serving views exist for the gold tables", rows3 and int(rows3[0][0]) == len(bd.BUILD_KPIS), str(rows3))
        rows4, _ = bd.admin_query("select table_schema, table_name from information_schema.tables t join pg_tables p on p.schemaname = t.table_schema "
                                  "and p.tablename = t.table_name where p.tableowner = 'governor_deploy' and t.table_schema <> 'analytics'", e)
        check("governor_deploy owns nothing outside analytics", rows4 == [], str(rows4)[:200])
    finally:
        tb.down()


guarded("offline", offline)
guarded("database", database)
pytest_check("tests/build")
finish("D6")
