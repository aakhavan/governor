"""D3 acceptance: proposal -> validation (with repair) -> design report -> design gate (interrupt), reject and approve
across processes, approved decisions recorded in the target. Fake LLM only."""
import copy
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, py_json, pytest_check  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402


def static():
    check("build never imports ask", not grep(["src/governor/build"], r"governor\.ask|from \.\.ask"), "")
    check("prompts/propose.md exists", (ROOT / "src/governor/build/prompts/propose.md").is_file(), "missing")
    check("sample design fixture exists", bd.fixture("sample_design.json") is not None, "tests/fixtures/build/sample_design.json")


def mutate_unknown_column(good):
    bad = copy.deepcopy(good)
    for k in bad["kpis"]:
        if k["id"] == "gmv":
            k["mapping"]["item_price"] = "no_such_column"
    return bad


def mutate_build_declined(good):
    bad = copy.deepcopy(good)
    for k in bad["kpis"]:
        if k["id"] == "gross_margin":
            k.clear()
            k.update({"id": "gross_margin", "decision": "build", "domain": "finance",
                      "mapping": {"order_lines": "int_order_lines", "product_costs": "stg_product_costs",
                                  "purchased_at": "purchased_at", "item_price": "item_price", "product_key": "product_id",
                                  "delivered_order": "order_status = 'delivered'", "cost_product_key": "product_id",
                                  "unit_cost": "unit_cost"}})
    return bad


def mutate_pii(good):
    bad = copy.deepcopy(good)
    for m in bad["silver_models"]:
        if m.get("source_table") == "olist_customers_dataset":
            for c in m["columns"]:
                if "customer_unique_id" in (c.get("expr") or ""):
                    c["pii"] = False
    return bad


def database():
    good = bd.fixture("sample_design.json")
    if good is None:
        return
    work = bd.workdir()
    e = bd.env(work / "state")
    if not bd.testbed_ready():
        return
    try:
        target = bd.init_target(work, e)
        if target is None:
            return
        base = ["--target", str(target), "--project-name", "shop"]
        d, err = bd.cli(["run", *base, "--llm", bd.script(work / "s1.json", propose=[json.dumps(good)])], e)
        ok = d is not None and d.get("status") == "awaiting_design_approval" and d.get("thread_id")
        if not check("run pauses at the design gate", ok, err or str(d)):
            return
        tid = d["thread_id"]
        report = (target / "governor" / "design.md")
        rtext = report.read_text(encoding="utf-8") if report.is_file() else ""
        check("design report written", bool(rtext), str(report))
        check("report lists every catalogue KPI", all(k in rtext for k in bd.CATALOGUE_KPIS), "")
        check("report has a gap report section", "gap" in rtext.lower(), "")
        check("report shows the approve command with the thread id", "approve" in rtext and tid in rtext, "")
        dj = target / "governor" / "design.json"
        check("design.json written", dj.is_file(), "")
        if dj.is_file():
            dd = json.loads(dj.read_text(encoding="utf-8"))
            dec = {k["id"]: k for k in dd.get("kpis", [])}
            gaps_ok = all(dec.get(i, {}).get("decision") == "decline" and all(dec[i].get("gap", {}).get(f) for f in ("missing", "typical_sources", "next_step"))
                          for i in bd.DECLINED)
            check("conversion_rate and gross_margin declined with complete gaps", gaps_ok, "")

        cases = [("MAPPING_UNKNOWN_COLUMN", mutate_unknown_column(good), ["MAPPING_UNKNOWN_COLUMN"]),
                 ("unbuildable KPI marked build", mutate_build_declined(good), ["MAPPING_UNKNOWN_MODEL", "MAPPING_INCOMPLETE", "MAPPING_UNKNOWN_COLUMN"]),
                 ("PII_UNTAGGED", mutate_pii(good), ["PII_UNTAGGED"])]
        for i, (label, bad, codes) in enumerate(cases):
            t2 = work / f"bad{i}"
            bd.cli(["init", "--target", str(t2), "--project-name", "shop"], e)
            d2, err2 = bd.cli(["run", "--target", str(t2), "--project-name", "shop",
                               "--llm", bd.script(work / f"b{i}.json", propose=[json.dumps(bad)] * 3)], e)
            txt = (t2 / "governor" / "design.md").read_text(encoding="utf-8") if (t2 / "governor" / "design.md").is_file() else json.dumps(d2)
            check(f"invalid proposal stops as design_invalid ({label})",
                  d2 is not None and d2.get("status") == "design_invalid" and any(c in txt for c in codes), err2 or str(d2)[:200])

        t3 = work / "repair"
        bd.cli(["init", "--target", str(t3), "--project-name", "shop"], e)
        d3, err3 = bd.cli(["run", "--target", str(t3), "--project-name", "shop",
                           "--llm", bd.script(work / "r.json", propose=[json.dumps(mutate_unknown_column(good)), json.dumps(good)])], e)
        check("a bad first proposal is repaired", d3 is not None and d3.get("status") == "awaiting_design_approval", err3 or str(d3))

        d4, err4 = bd.cli(["reject", tid, "--note", "use int_orders for on-time delivery",
                           "--llm", bd.script(work / "s2.json", propose=[json.dumps(good)])], e)
        check("reject sends the design back and pauses again", d4 is not None and d4.get("status") == "awaiting_design_approval", err4 or str(d4))
        d5, err5 = bd.cli(["approve", tid, "--by", "amir", "--llm", bd.script(work / "s3.json", propose=[json.dumps(good)])], e)
        check("approve in a new process records the design", d5 is not None and d5.get("status") == "design_approved", err5 or str(d5))
        ap = target / "governor" / "approved.yaml"
        code = ("import json\nfrom governor.core.catalogue import load_approved\n"
                f"a=load_approved({str(ap)!r})\n"
                "print(json.dumps([[d.kind, d.approved_by] for d in a.decisions]))")
        d6, err6 = py_json(code, env=e)
        ok6 = isinstance(d6, list) and len(d6) >= len(bd.BUILD_KPIS) and all(k == "column_mapping" and by == "amir" for k, by in d6)
        check("approved column mappings recorded in the target's approved.yaml", ok6, err6 or str(d6)[:200])
    finally:
        tb.down()


guarded("static", static)
guarded("database", database)
pytest_check("tests/build")
finish("D3")
