"""C2 acceptance: warehouse adapter seam with DuckDB; the locked G5b acceptance still passes."""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, last_json, py_json, pytest_check, run, tail  # noqa: E402

CONTRACT = r'''
import json
from governor.core.adapters import get_adapter, QueryTimeout, QueryError
out = {}
a = get_adapter("duckdb")
out["name"], out["dialect"] = a.name, a.dialect
out["dry_good"] = bool(a.dry_run("SELECT country FROM dim_accounts", timeout_s=5).ok)
out["dry_bad"] = bool(a.dry_run("SELECT nope FROM dim_accounts", timeout_s=5).ok)
cols, rows = a.run("SELECT * FROM fct_invoices", timeout_s=10, row_cap=7)
out["row_cap"] = len(rows)
try:
    json.dumps(rows); out["json_safe"] = True
except TypeError:
    out["json_safe"] = False
try:
    a.run("SELECT count(*) FROM fct_invoices x, fct_invoices y, fct_invoices z WHERE x.amount_eur + y.amount_eur + z.amount_eur > -1", timeout_s=1.0, row_cap=1)
    out["timeout"] = "none"
except QueryTimeout:
    out["timeout"] = "QueryTimeout"
except Exception as e:
    out["timeout"] = type(e).__name__
try:
    a.run("CREATE TABLE zz_c2 AS SELECT 1 AS a", timeout_s=5, row_cap=1)
    out["write"] = "none"
except QueryError:
    out["write"] = "QueryError"
except Exception as e:
    out["write"] = type(e).__name__
out["has_amount"] = any(c.table == "fct_invoices" and c.column == "amount_eur" for c in a.list_columns())
a.close()
try:
    get_adapter("nosuch"); out["unknown"] = "no error"
except Exception as e:
    out["unknown"] = type(e).__name__
print(json.dumps(out))
'''


def adapter_contract():
    d, err = py_json(CONTRACT, env=dict(os.environ, GOVERNOR_WAREHOUSE="duckdb"))
    if not check("adapter contract runs", d is not None, err):
        return
    check("DuckDB adapter named duckdb with dialect duckdb", (d["name"], d["dialect"]) == ("duckdb", "duckdb"), str(d)[:200])
    check("dry_run passes a good query and fails a bad column", d["dry_good"] is True and d["dry_bad"] is False, str(d)[:200])
    check("run honours row_cap", d["row_cap"] == 7, str(d["row_cap"]))
    check("run returns JSON-safe values", d["json_safe"] is True, "")
    check("timeout raises QueryTimeout", d["timeout"] == "QueryTimeout", d["timeout"])
    check("a write raises QueryError", d["write"] == "QueryError", d["write"])
    check("list_columns returns real columns", d["has_amount"] is True, "")
    check("unknown adapter name raises", d["unknown"] != "no error", d["unknown"])


def no_direct_duckdb():
    files = ["src/governor/ask/executor.py", "src/governor/ask/validator.py"]
    check("executor and validator do not import duckdb", not grep(files, r"^\s*(import duckdb|from duckdb)"),
          ", ".join(grep(files, r"^\s*(import duckdb|from duckdb)")[:3]))
    hits = grep(["src/governor/ask/validator.py"], r"['\"]duckdb['\"]")
    check("validator has no hard-coded duckdb dialect", not hits, ", ".join(hits[:3]))


def g5b_regression():
    if not (ROOT / "plan" / "accept" / "accept_g5b.py").is_file():
        check("locked G5b acceptance present", False, "missing")
        return
    r = run([sys.executable, "plan/accept/accept_g5b.py"], timeout=1800)
    d = last_json(r.stdout) or {}
    check("locked G5b acceptance still passes", d.get("pass") is True, tail(r))


check("conformance suite exists", (ROOT / "tests" / "core" / "test_adapter_conformance.py").is_file(), "missing")
guarded("adapter contract", adapter_contract)
guarded("no direct duckdb", no_direct_duckdb)
guarded("G5b regression", g5b_regression)
pytest_check("tests")
finish("C2")
