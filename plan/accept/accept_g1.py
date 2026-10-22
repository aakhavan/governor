"""G1 acceptance: foundation package, green build, fct_invoices, metadata store, provenance."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, load_yaml, py_json, pytest_check, run, tail  # noqa: E402

MARTS = ["dim_accounts", "fct_invoices", "fct_revenue_daily", "mrr_monthly"]
FCT_INVOICES = ["invoice_id", "account_id", "subscription_id", "country", "issued_at", "amount_eur", "status",
                "paid_amount_eur", "last_paid_at", "is_fully_paid", "days_outstanding"]
DIM_ACCOUNTS = ["account_id", "company_name", "contact_name", "contact_email", "country"]


def paths_module():
    data, err = py_json("import json; from governor.core import paths as p; "
                        "print(json.dumps({k: str(getattr(p, k)) for k in "
                        "['ROOT','ARTIFACTS','GREEN','WAREHOUSE','META','KNOWLEDGE','TRACES']}))")
    ok = data is not None and Path(data["ROOT"]).resolve() == ROOT.resolve()
    check("governor.core.paths resolves the repo root", ok, err or data)


def no_foreign_paths():
    hits = grep(["src", "fixture", "tests"], r"sprint-04|turing college|from triage|import triage|[A-Za-z]:\\\\Users")
    check("no Sprint 4 / absolute paths in src, fixture, tests", not hits, ", ".join(hits[:6]))


def provenance():
    p = ROOT / "PROVENANCE.md"
    if not check("PROVENANCE.md exists", p.is_file(), ""):
        return
    text = p.read_text(encoding="utf-8")
    core = sorted(f.name for f in (ROOT / "src/governor/core").glob("*.py") if f.name != "__init__.py")
    missing = [n for n in core if n not in text]
    check("every core module listed in PROVENANCE.md", not missing, f"missing: {missing}" if missing else f"{len(core)} listed")
    check("PROVENANCE.md has a 'New in G1' section", "new in g1" in text.lower(), "")


def green_build():
    r = run([sys.executable, "fixture/build_green.py"], timeout=600)
    if not check("fixture/build_green.py exits 0", r.returncode == 0, tail(r)):
        return False
    g = ROOT / "artifacts/green"
    need = ["manifest.json", "run_results.json", "sources.json", "catalog.json", "warehouse.duckdb", "as_of.txt"]
    miss = [n for n in need if not (g / n).is_file()]
    check("artifacts/green complete", not miss, f"missing: {miss}" if miss else "6 files")
    rr = json.loads((g / "run_results.json").read_text(encoding="utf-8"))
    bad = [x.get("unique_id") for x in rr.get("results", []) if x.get("status") not in ("pass", "success")]
    check("green run: every node passes", not bad, f"{len(bad)} not passing: {bad[:4]}")
    return True


def mart_counts():
    code = ("import duckdb, json; from governor.core import paths as p; c=duckdb.connect(str(p.WAREHOUSE), read_only=True)\n"
            "out={}\n"
            f"for m in {MARTS!r}:\n"
            "    r=c.execute(\"select table_schema from information_schema.tables where table_name=?\",[m]).fetchone()\n"
            "    out[m]=None if r is None else c.execute(f'select count(*) from \"{r[0]}\".\"{m}\"').fetchone()[0]\n"
            "cols={}\n"
            "for m in ['fct_invoices','dim_accounts']:\n"
            "    cols[m]=[x[0] for x in c.execute(\"select column_name from information_schema.columns where table_name=?\",[m]).fetchall()]\n"
            "c.close(); print(json.dumps({'counts':out,'cols':cols}))")
    return py_json(code)


def warehouse():
    data, err = mart_counts()
    if not check("warehouse readable", data is not None, err):
        return None
    empty = [m for m, n in data["counts"].items() if not n]
    check("marts exist and are non-empty", not empty, f"empty/missing: {empty}" if empty else str(data["counts"]))
    fi = set(data["cols"].get("fct_invoices", []))
    check("fct_invoices has the required columns", set(FCT_INVOICES) <= fi, f"missing: {sorted(set(FCT_INVOICES) - fi)}")
    da = set(data["cols"].get("dim_accounts", []))
    check("dim_accounts has the required columns", set(DIM_ACCOUNTS) <= da, f"missing: {sorted(set(DIM_ACCOUNTS) - da)}")
    return data["counts"]


def warehouse_connect():
    data, err = py_json("import json; from governor.core.warehouse import connect\n"
                        "c = connect(); n = c.execute('select count(*) from dim_accounts').fetchone()[0]\n"
                        "try:\n    c.execute('create table zz_accept as select 1 as a'); w = 'allowed'\n"
                        "except Exception as e:\n    w = type(e).__name__\n"
                        "c.close(); print(json.dumps({'n': n, 'write': w}))")
    ok = data is not None and data["n"] > 0 and data["write"] != "allowed"
    check("warehouse.connect(): unqualified mart names, read-only", ok, err or data)


def fct_invoices_time():
    files = list((ROOT / "fixture").rglob("fct_invoices.sql"))
    if not check("fct_invoices.sql exists", bool(files), ""):
        return
    text = files[0].read_text(encoding="utf-8").lower()
    bad = [w for w in ("now()", "current_date", "current_timestamp", "get_current_timestamp") if w in text]
    check("fct_invoices pins time to as_of (no now()/current_date)", not bad and "as_of" in text,
          f"found {bad}" if bad else ("as_of not referenced" if "as_of" not in text else "ok"))


def harvest():
    r = run([sys.executable, "-m", "governor.core.harvest", "artifacts/green", "--out", "artifacts/meta.duckdb"], timeout=300)
    if not check("harvest CLI exits 0", r.returncode == 0, tail(r)):
        return
    code = ("import duckdb, json; c=duckdb.connect('artifacts/meta.duckdb', read_only=True)\n"
            "t={n: c.execute(f'select count(*) from {n}').fetchone()[0] for n in ['nodes','columns','edges','tests','exposures']}\n"
            "names=[r[0] for r in c.execute(\"select name from nodes where resource_type='model'\").fetchall()]\n"
            "pii=c.execute(\"select unique_id, \\\"column\\\", pii_tag from columns where pii_tag is not null and pii_tag<>''\").fetchall()\n"
            "c.close(); print(json.dumps({'t':t,'names':names,'pii':[[a,b,cc] for a,b,cc in pii]}))")
    data, err = py_json(code)
    if not check("meta.duckdb readable", data is not None, err):
        return
    t = data["t"]
    check("meta tables populated", t["nodes"] >= 14 and all(t[k] > 0 for k in t), str(t))
    miss = [m for m in MARTS if m not in data["names"]]
    check("meta has the four marts", not miss, f"missing: {miss}")
    pii = {(u.split(".")[-1], c) for u, c, _ in data["pii"]}
    need = {("dim_accounts", "contact_email"), ("dim_accounts", "contact_name")}
    check("PII tags propagated to dim_accounts", need <= pii, f"missing: {sorted(need - pii)}")
    access = load_yaml(ROOT / "knowledge/access.yaml")
    am = set(access["allowlist"]["models"])
    check("access.yaml allowlist matches the marts", am == set(MARTS) or am <= set(data["names"]), str(sorted(am)))
    grants = [g for r in access["roles"].values() for g in r.get("grants", [])]
    bad = [g for g in grants if tuple(g.split(".", 1)) not in pii]
    check("access.yaml grants point at PII-tagged columns", not bad, f"bad: {bad}")
    check("access.yaml roles unchanged", sorted(access["roles"]) == ["analyst", "finance_admin"]
          and access["roles"]["analyst"]["pii"] == "aggregate_only" and access["roles"]["finance_admin"]["pii"] == "mask", "")


guarded("paths", paths_module)
guarded("foreign paths", no_foreign_paths)
guarded("provenance", provenance)
built = False
try:
    built = green_build()
except Exception as exc:  # noqa: BLE001
    check("green build", False, f"{type(exc).__name__}: {exc}")
if built:
    counts = None
    try:
        counts = warehouse()
    except Exception as exc:  # noqa: BLE001
        check("warehouse", False, f"{type(exc).__name__}: {exc}")
    guarded("warehouse.connect", warehouse_connect)
    guarded("fct_invoices time", fct_invoices_time)
    guarded("harvest", harvest)
    # determinism: a second build gives identical mart row counts
    try:
        r = run([sys.executable, "fixture/build_green.py"], timeout=600)
        again, err = mart_counts()
        check("second build gives identical mart counts", r.returncode == 0 and again and again["counts"] == counts,
              err or f"{counts} vs {again and again['counts']}")
    except Exception as exc:  # noqa: BLE001
        check("determinism", False, f"{type(exc).__name__}: {exc}")
pytest_check("tests/core")
finish("G1")
