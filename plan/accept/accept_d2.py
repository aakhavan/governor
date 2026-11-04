"""D2 acceptance: deterministic profile of raw on the synthetic sample; keys, types, relationships; no PII values."""
import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, pytest_check  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402

PII_VALUE_COLS = {"olist_customers_dataset.csv": ["customer_unique_id", "customer_city", "customer_zip_code_prefix"],
                  "olist_order_reviews_dataset.csv": ["review_comment_title", "review_comment_message"],
                  "olist_sellers_dataset.csv": ["seller_city", "seller_zip_code_prefix"]}


def pii_values() -> set[str]:
    vals = set()
    for name, cols in PII_VALUE_COLS.items():
        with (ROOT / "testbed" / "sample" / name).open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                for c in cols:
                    v = (row.get(c) or "").strip()
                    if len(v) >= 4:
                        vals.add(v)
    return vals


def database():
    work = bd.workdir()
    e = bd.env(work / "state")
    if not bd.testbed_ready():
        return
    try:
        out = work / "profile.json"
        d, err = bd.cli(["profile", "--schema", "raw", "--policy", "knowledge/shop/policy.yaml", "--out", str(out)], e)
        if not check("profile CLI writes the profile", d is not None and out.is_file(), err):
            return
        text = out.read_text(encoding="utf-8")
        p = json.loads(text)
        tables = {t["name"]: t for t in p.get("tables", [])}
        check("all 9 raw tables profiled", len(tables) == 9, str(sorted(tables)))
        want = tb.sample_counts()
        check("row counts match the sample", all(tables.get(k, {}).get("rows") == v for k, v in want.items()), "")
        cols = {(t, c["name"]): c for t, tt in tables.items() for c in tt.get("columns", [])}
        check("loader columns starting with _ are left out", not any(c.startswith("_") for _, c in cols), "")
        orders = tables.get("olist_orders_dataset", {})
        check("orders key is order_id", ["order_id"] in orders.get("candidate_keys", []), str(orders.get("candidate_keys")))
        cust = tables.get("olist_customers_dataset", {})
        keys = cust.get("candidate_keys", [])
        check("customer_id is a key and customer_unique_id is not", ["customer_id"] in keys and ["customer_unique_id"] not in keys, str(keys))
        rel = {(r["from"], r["to"]) for r in p.get("relationships", [])}
        check("orders.customer_id relates to customers.customer_id",
              ("olist_orders_dataset.customer_id", "olist_customers_dataset.customer_id") in rel, str(sorted(rel))[:200])
        ts = cols.get(("olist_orders_dataset", "order_purchase_timestamp"), {})
        price = cols.get(("olist_order_items_dataset", "price"), {})
        check("purchase timestamp inferred as timestamp", ts.get("inferred_type") == "timestamp", str(ts))
        check("price inferred as numeric", price.get("inferred_type") == "numeric", str(price))
        cu = cols.get(("olist_customers_dataset", "customer_unique_id"), {})
        check("customer_unique_id is flagged PII with no min or max", cu.get("pii") is True and cu.get("min") is None and cu.get("max") is None, str(cu))
        leaked = sorted(v for v in pii_values() if v in text)
        check("no PII value appears in the profile", not leaked, str(leaked[:3]))
    finally:
        tb.down()


guarded("database", database)
pytest_check("tests/build")
finish("D2")
