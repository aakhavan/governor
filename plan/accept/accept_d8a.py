"""D8a acceptance: build evaluation harness with the fake LLM on the sample: agent runs approved by the harness score
6/6 gold checks; a deliberately partial one-shot baseline scores what it built; report shape and frozen ground truth."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, last_json, pytest_check, run, tail  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402
import _build2 as b2  # noqa: E402
from _frozen2 import frozen_capstone_ok  # noqa: E402

GOLD = "evaluation/build_gold/sample_gold.yaml"
BASELINE_GMV = ("select date_trunc('month', cast(o.order_purchase_timestamp as timestamp)) as month, "
                "sum(cast(i.price as numeric) + cast(i.freight_value as numeric)) as gmv "
                "from {{ source('raw', 'olist_order_items_dataset') }} i join {{ source('raw', 'olist_orders_dataset') }} o using (order_id) "
                "where o.order_status not in ('canceled', 'unavailable') group by 1")


def static():
    ok, detail = frozen_capstone_ok()
    check("capstone ground truth frozen and unchanged", ok, detail)
    check("baseline prompt exists", (ROOT / "src/governor/eval/prompts/baseline_build.md").is_file(), "")


def harness(args, e):
    r = run([sys.executable, "-m", "governor.eval.build_eval", *args], timeout=3600, env=e)
    return last_json(r.stdout), tail(r)


def database():
    design, silver = bd.fixture("sample_design.json"), bd.fixture("sample_silver.json")
    if design is None or not isinstance(silver, dict):
        check("sample fixtures exist", False, "")
        return
    work = bd.workdir()
    e = b2.env(work / "state")
    if not bd.testbed_ready():
        return
    try:
        agent_script = work / "agent.json"
        agent_script.write_text(json.dumps({"propose": [json.dumps(design)] * 2, **{k: {m: v * 2 for m, v in d.items()} for k, d in silver.items()}}), encoding="utf-8")
        out = work / "agent_report.json"
        _, err = harness(["--system", "agent", "--runs", "2", "--gold", GOLD, "--out", str(out), "--llm", f"fake:{agent_script}"], e)
        rep = json.loads(out.read_text(encoding="utf-8")) if out.is_file() else None
        if not check("agent report written", rep is not None, err):
            return
        runs = rep.get("runs") or []
        check("two agent runs recorded", len(runs) == 2, str(len(runs)))
        check("every agent run built and passed 6/6 gold checks",
              all(r.get("status") == "built" and r.get("gold_passed") == 6 and r.get("gold_total") == 6 for r in runs), json.dumps(runs)[:240])
        check("agent approvals recorded as eval-harness", "eval-harness" in json.dumps(rep), "")
        check("report has a summary and the gold file hash", "summary" in rep and len(str(rep.get("gold_sha256", ""))) == 64, "")

        base_script = work / "baseline.json"
        files = {"files": [{"path": "models/marts/kpi_gmv.sql", "content": BASELINE_GMV}]}
        base_script.write_text(json.dumps({"baseline": [json.dumps(files)]}), encoding="utf-8")
        out2 = work / "baseline_report.json"
        _, err2 = harness(["--system", "baseline", "--runs", "1", "--gold", GOLD, "--out", str(out2), "--llm", f"fake:{base_script}"], e)
        rep2 = json.loads(out2.read_text(encoding="utf-8")) if out2.is_file() else None
        r2 = (rep2 or {}).get("runs") or [{}]
        check("partial baseline scores exactly the one KPI it built", rep2 is not None and r2[0].get("gold_passed") == 1 and r2[0].get("gold_total") == 6,
              err2 or json.dumps(r2)[:240])
        check("baseline was never repaired", rep2 is not None and int(r2[0].get("dbt_repairs") or 0) == 0, json.dumps(r2)[:200])
    finally:
        tb.down()


guarded("static", static)
guarded("database", database)
pytest_check("tests/eval")
finish("D8a")
