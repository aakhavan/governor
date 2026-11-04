"""D5 acceptance: full sample build (fake LLM): gold from catalogue templates in dev_governor, values equal to an
independent computation from the sample CSVs, blueprint checks clean and catching violations, gap report written."""
import csv
import json
import shutil
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, py_json, pytest_check  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402

INVALID = {"canceled", "unavailable"}


def read(name):
    with (ROOT / "testbed" / "sample" / f"{name}.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def expected():
    orders = {o["order_id"]: o for o in read("olist_orders_dataset")}
    cust = {c["customer_id"]: c["customer_unique_id"] for c in read("olist_customers_dataset")}
    month = lambda ts: ts[:7]  # noqa: E731
    gmv, net, aov_sum, aov_orders = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(set)
    for it in read("olist_order_items_dataset"):
        o = orders.get(it["order_id"])
        if not o:
            continue
        m, price, freight = month(o["order_purchase_timestamp"]), float(it["price"]), float(it["freight_value"])
        if o["order_status"] not in INVALID:
            gmv[m] += price + freight
            aov_sum[m] += price
            aov_orders[m].add(o["order_id"])
        if o["order_status"] == "delivered":
            net[m] += price
    aov = {m: aov_sum[m] / len(aov_orders[m]) for m in aov_sum}
    ontime_n, ontime_d = defaultdict(int), defaultdict(int)
    for o in orders.values():
        dl, est = o["order_delivered_customer_date"], o["order_estimated_delivery_date"]
        if o["order_status"] == "delivered" and dl and est:
            m = month(o["order_purchase_timestamp"])
            ontime_d[m] += 1
            ontime_n[m] += 1 if dl[:10] <= est[:10] else 0
    ontime = {m: ontime_n[m] / ontime_d[m] for m in ontime_d}
    latest = {}
    for r in read("olist_order_reviews_dataset"):
        prev = latest.get(r["order_id"])
        if prev is None or (r["review_answer_timestamp"], r["review_id"]) > (prev["review_answer_timestamp"], prev["review_id"]):
            latest[r["order_id"]] = r
    rev_sum, rev_n = defaultdict(float), defaultdict(int)
    for oid, r in latest.items():
        if oid in orders:
            m = month(orders[oid]["order_purchase_timestamp"])
            rev_sum[m] += int(r["review_score"])
            rev_n[m] += 1
    review = {m: rev_sum[m] / rev_n[m] for m in rev_n}
    per = defaultdict(set)
    for o in orders.values():
        if o["order_status"] not in INVALID and o["customer_id"] in cust:
            per[cust[o["customer_id"]]].add(o["order_id"])
    repeat = sum(1 for v in per.values() if len(v) >= 2) / len(per)
    return {"gmv": gmv, "net_revenue": dict(net), "aov": aov, "on_time_delivery_rate": ontime, "avg_review_score": review}, repeat


def database():
    design, silver = bd.fixture("sample_design.json"), bd.fixture("sample_silver.json")
    if not check("sample design and silver fixtures exist", design is not None and isinstance(silver, dict), ""):
        return
    work = bd.workdir()
    e = bd.env(work / "state")
    if not bd.testbed_ready():
        return
    try:
        target = bd.init_target(work, e)
        if target is None:
            return
        s = bd.script(work / "s.json", propose=[json.dumps(design)], **silver)
        d, err = bd.cli(["run", "--target", str(target), "--project-name", "shop", "--llm", s], e)
        if not check("run pauses at the design gate", d is not None and d.get("thread_id"), err or str(d)):
            return
        d2, err2 = bd.cli(["approve", d["thread_id"], "--by", "amir", "--llm", s], e, timeout=2400)
        if not check("approve builds silver and gold", d2 is not None and d2.get("status") == "built", err2 or str(d2)[:200]):
            return
        check("all eight buildable KPIs built", sorted(d2.get("kpis_built") or []) == sorted(bd.BUILD_KPIS) or
              sorted(k.get("id") if isinstance(k, dict) else k for k in d2.get("kpis_built") or []) == sorted(bd.BUILD_KPIS), str(d2.get("kpis_built"))[:200])
        check("gaps list conversion_rate and gross_margin", all(i in json.dumps(d2.get("gaps")) for i in bd.DECLINED), "")
        for rel in ("governor/gaps.md", "governor/build.json"):
            check(f"target has {rel}", (target / rel).is_file(), "")
        yml = "".join(p.read_text(encoding="utf-8") for p in (target / "models" / "marts").rglob("_*.yml"))
        check("gold yml carries owner, source tier and template hash", all(w in yml for w in ("owner", "source_tier", "template_sha256")), "")

        want, repeat = expected()
        for kpi, col in [("gmv", "gmv"), ("net_revenue", "net_revenue"), ("aov", "aov"),
                         ("on_time_delivery_rate", "on_time_delivery_rate"), ("avg_review_score", "avg_review_score")]:
            rows, qerr = bd.admin_query(f"select to_char(month, 'YYYY-MM'), {col}::float8 from dev_governor.kpi_{kpi}", e)
            got = {r[0]: float(r[1]) for r in rows or [] if r[1] is not None}
            exp = want[kpi]
            same = set(got) == set(exp) and all(abs(got[m] - exp[m]) < 1e-6 for m in exp)
            check(f"{kpi} equals the independent computation", same, qerr or f"got {got} want {dict(exp)}"[:240])
        rows, qerr = bd.admin_query("select repeat_purchase_rate::float8 from dev_governor.kpi_repeat_purchase_rate", e)
        check("repeat_purchase_rate equals the independent computation",
              bool(rows) and abs(float(rows[0][0]) - repeat) < 1e-6, qerr or f"got {rows} want {repeat}")

        code = ("import json\nfrom pathlib import Path\nfrom governor.build.gold import check_project\n"
                "from governor.core.catalogue import load_kpis\nimport yaml\n"
                "pol=yaml.safe_load(open('knowledge/shop/policy.yaml',encoding='utf-8'))\n"
                "def run(t):\n"
                "    f=check_project(Path(t), load_kpis('knowledge/kpis.yaml'), pol)\n"
                "    return [x.model_dump() if hasattr(x,'model_dump') else (x.__dict__ if hasattr(x,'__dict__') else x) for x in f]\n"
                "import sys\nprint(json.dumps(run(sys.argv[1]), default=str))")
        clean, cerr = py_json(code.replace("sys.argv[1]", repr(str(target))), env=e)
        highs = [f for f in clean or [] if str(f.get("severity")) == "high"]
        check("blueprint check is clean on the built project", clean is not None and not highs, cerr or str(highs)[:200])
        broken = work / "broken"
        shutil.copytree(target, broken)
        kpi_file = next((broken / "models" / "marts").rglob("kpi_gmv.sql"), None)
        if kpi_file:
            kpi_file.write_text(kpi_file.read_text(encoding="utf-8").replace("SELECT", "SELECT CAST(1 AS int) AS x,", 1), encoding="utf-8")
        found, ferr = py_json(code.replace("sys.argv[1]", repr(str(broken))), env=e)
        rules = json.dumps(found or [])
        check("blueprint check catches a cast in gold (L9) and a changed template (L8)", '"L9"' in rules and '"L8"' in rules, ferr or rules[:200])
    finally:
        tb.down()


guarded("database", database)
pytest_check("tests/build")
finish("D5")
