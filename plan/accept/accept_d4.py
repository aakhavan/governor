"""D4 acceptance: silver written (staging by code, intermediate by the fake write model), checked, built in
dev_governor with key tests, a bad draft repaired, a hopeless one escalated, nothing written outside dev_governor."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import check, finish, guarded, pytest_check  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402


def full_script(work: Path, name: str, design, silver) -> str:
    return bd.script(work / name, propose=[json.dumps(design)], **silver)


def database():
    design, silver = bd.fixture("sample_design.json"), bd.fixture("sample_silver.json")
    if not check("sample design and silver fixtures exist", design is not None and isinstance(silver, dict), "tests/fixtures/build/"):
        return
    work = bd.workdir()
    e = bd.env(work / "state")
    if not bd.testbed_ready():
        return
    try:
        target = bd.init_target(work, e)
        if target is None:
            return
        s = full_script(work, "s.json", design, silver)
        d, err = bd.cli(["run", "--target", str(target), "--project-name", "shop", "--llm", s], e)
        if not check("run pauses at the design gate", d is not None and d.get("status") == "awaiting_design_approval", err or str(d)):
            return
        d2, err2 = bd.cli(["approve", d["thread_id"], "--by", "amir", "--llm", s], e, timeout=1800)
        ok = d2 is not None and d2.get("status") == "silver_built"
        if not check("approve builds silver", ok, err2 or str(d2)[:200]):
            return
        check("tests ran and passed", int(d2.get("tests_passed") or 0) > 0, str(d2.get("tests_passed")))
        check("the scripted bad draft was repaired", int(d2.get("repairs") or 0) >= 1, str(d2.get("repairs")))
        names = [m["name"] for m in design["silver_models"]]
        rows, qerr = bd.admin_query("select table_name from information_schema.tables where table_schema='dev_governor'", e)
        built = {r[0] for r in rows or []}
        check("every silver model exists in dev_governor", set(names) <= built, qerr or str(sorted(set(names) - built)))
        rows2, _ = bd.admin_query("select table_schema, table_name from information_schema.tables where table_schema not in "
                                  "('raw','dev_governor','private','pg_catalog','information_schema')", e)
        check("nothing written outside dev_governor", rows2 == [], str(rows2)[:200])
        yml = "".join(p.read_text(encoding="utf-8") for p in (target / "models").rglob("_*.yml"))
        check("silver yml tags PII columns", "pii: true" in yml.replace("'", "").replace('"', "").lower(), "")
        check("silver yml has unique and not_null key tests", "unique" in yml and "not_null" in yml, "")
        composite = [m for m in design["silver_models"] if len(m.get("primary_key", [])) > 1]
        if composite:
            check("composite keys have singular tests", any((target / "tests").glob("*.sql")), "")

        hopeless = copy.deepcopy(silver)
        bad_sql = "select nope from {{ ref('stg_orders') }}"
        hopeless.setdefault("intermediate", {})["int_order_lines"] = [bad_sql]
        hopeless.setdefault("repair", {})["int_order_lines"] = [bad_sql] * 4
        t2 = work / "hopeless"
        bd.cli(["init", "--target", str(t2), "--project-name", "shop"], e)
        s2 = full_script(work, "h.json", design, hopeless)
        d3, err3 = bd.cli(["run", "--target", str(t2), "--project-name", "shop", "--llm", s2], e)
        if d3 and d3.get("thread_id"):
            d4, err4 = bd.cli(["approve", d3["thread_id"], "--by", "amir", "--llm", s2], e, timeout=1800)
            check("a model that cannot be repaired ends escalated", d4 is not None and d4.get("status") == "escalated"
                  and "int_order_lines" in json.dumps(d4), err4 or str(d4)[:200])
        else:
            check("a model that cannot be repaired ends escalated", False, err3 or str(d3))
    finally:
        tb.down()


guarded("database", database)
pytest_check("tests/build")
finish("D4")
