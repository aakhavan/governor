"""C3 acceptance: Postgres test bed, header-checked idempotent Olist loader, synthetic sample with the edge cases."""
import csv
import shutil
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, pytest_check, run, tail  # noqa: E402
import _testbed as tb  # noqa: E402


def files_present():
    for rel in ("testbed/docker-compose.yml", "testbed/load_olist.py", "testbed/README.md"):
        check(f"{rel} exists", (ROOT / rel).is_file(), "missing")
    gi = (ROOT / ".gitignore").read_text(encoding="utf-8") if (ROOT / ".gitignore").is_file() else ""
    check(".gitignore keeps testbed/data/ out of git", "testbed/data" in gi, "")
    pp = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    check("psycopg is a dependency", "psycopg" in pp, "")
    readme = (ROOT / "testbed" / "README.md")
    if readme.is_file():
        check("README marks the licence check as TODO or states the licence", "licen" in readme.read_text(encoding="utf-8").lower(), "")


def sample_rows():
    rows = {}
    for name, header in tb.EXPECTED.items():
        p = ROOT / "testbed" / "sample" / name
        if not check(f"sample {name} exists", p.is_file(), "missing"):
            continue
        with p.open(newline="", encoding="utf-8") as f:
            r = list(csv.reader(f))
        check(f"sample {name} header is exact", bool(r) and r[0] == header, str(r[0] if r else None)[:200])
        check(f"sample {name} has 1-30 rows", 1 <= len(r) - 1 <= 30, f"{len(r) - 1} rows")
        rows[name] = [dict(zip(r[0], x)) for x in r[1:]] if r else []
    return rows


def edge_cases():
    rows = sample_rows()
    cust = rows.get("olist_customers_dataset.csv", [])
    per = defaultdict(set)
    for c in cust:
        per[c.get("customer_unique_id")].add(c.get("customer_id"))
    check("edge: one customer_unique_id with two customer_ids", any(len(v) >= 2 for v in per.values()), "")
    orders = rows.get("olist_orders_dataset.csv", [])
    check("edge: a canceled order", any(o.get("order_status") == "canceled" for o in orders), "")
    late = [o for o in orders if o.get("order_delivered_customer_date") and o.get("order_estimated_delivery_date")
            and o["order_delivered_customer_date"][:10] > o["order_estimated_delivery_date"][:10]]
    check("edge: an order delivered after its estimated date", bool(late), "")
    rev = Counter(r.get("order_id") for r in rows.get("olist_order_reviews_dataset.csv", []))
    check("edge: an order with two reviews", any(n >= 2 for n in rev.values()), "")
    pay = Counter(p.get("order_id") for p in rows.get("olist_order_payments_dataset.csv", []))
    check("edge: an order with two payments", any(n >= 2 for n in pay.values()), "")
    missing = {o.get("customer_id") for o in orders} - {c.get("customer_id") for c in cust}
    check("every order's customer exists in the customers sample", not missing, str(sorted(missing))[:200])


def database():
    if not tb.docker_ok() or not tb.up():
        return
    try:
        tb.load_sample("sample loads into raw with the right row counts")
        tb.load_sample("a second load gives the same counts (idempotent)")
        with tempfile.TemporaryDirectory() as d:
            bad = Path(d) / "bad"
            shutil.copytree(ROOT / "testbed" / "sample", bad)
            p = bad / "olist_orders_dataset.csv"
            text = p.read_text(encoding="utf-8").splitlines()
            text[0] = text[0].replace("order_status", "status")
            p.write_text("\n".join(text) + "\n", encoding="utf-8")
            r = run([sys.executable, "testbed/load_olist.py", "--source", str(bad), "--dsn", tb.ADMIN_DSN], timeout=300, env=tb.env())
            msg = (r.stdout or "") + (r.stderr or "")
            check("a wrong header is refused and the file is named", r.returncode != 0 and "olist_orders_dataset" in msg, tail(r))
    finally:
        tb.down()


guarded("files", files_present)
guarded("sample", edge_cases)
guarded("database", database)
pytest_check("tests/testbed", required=["test_headers_validated", "test_sample_edge_cases_present"])
finish("C3")
