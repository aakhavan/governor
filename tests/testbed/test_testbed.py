"""Test bed tests. Offline except the database test, which skips when GOVERNOR_PG_DSN is unset."""
import csv
import importlib.util
import json
import os
import shutil
from collections import Counter, defaultdict
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "testbed" / "sample"

_spec = importlib.util.spec_from_file_location("load_olist", ROOT / "testbed" / "load_olist.py")
load_olist = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_olist)


def _rows(name):
    with (SAMPLE / name).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_headers_validated(tmp_path):
    load_olist.validate_source(SAMPLE)  # the sample is valid
    bad = tmp_path / "bad"
    shutil.copytree(SAMPLE, bad)
    p = bad / "olist_orders_dataset.csv"
    lines = p.read_text(encoding="utf-8").splitlines()
    lines[0] = lines[0].replace("order_status", "status")
    p.write_text("\n".join(lines) + "\n", encoding="utf-8")
    with pytest.raises(load_olist.HeaderError) as e:
        load_olist.validate_source(bad)
    msg = str(e.value)
    assert "olist_orders_dataset.csv" in msg and "order_status" in msg and "status" in msg

    (bad / "olist_sellers_dataset.csv").unlink()
    with pytest.raises(load_olist.HeaderError, match="olist_sellers_dataset.csv: file missing"):
        load_olist.validate_source(bad)


def test_sample_edge_cases_present():
    cust = _rows("olist_customers_dataset.csv")
    per = defaultdict(set)
    for c in cust:
        per[c["customer_unique_id"]].add(c["customer_id"])
    assert any(len(v) >= 2 for v in per.values())
    orders = _rows("olist_orders_dataset.csv")
    assert any(o["order_status"] == "canceled" for o in orders)
    assert any(o["order_delivered_customer_date"] and o["order_delivered_customer_date"][:10] > o["order_estimated_delivery_date"][:10] for o in orders)
    assert any(n >= 2 for n in Counter(r["order_id"] for r in _rows("olist_order_reviews_dataset.csv")).values())
    assert any(n >= 2 for n in Counter(r["order_id"] for r in _rows("olist_order_payments_dataset.csv")).values())
    assert {o["customer_id"] for o in orders} <= {c["customer_id"] for c in cust}
    for name in load_olist.EXPECTED:
        assert len(_rows(name)) <= 30


@pytest.mark.skipif(not os.environ.get("GOVERNOR_PG_DSN"), reason="GOVERNOR_PG_DSN unset")
def test_load_sample_idempotent():
    dsn = os.environ["GOVERNOR_PG_DSN"]
    first = load_olist.load(SAMPLE, dsn)
    second = load_olist.load(SAMPLE, dsn)
    assert first == second
    assert first["olist_orders_dataset"] == len(_rows("olist_orders_dataset.csv"))
    json.dumps(first)
