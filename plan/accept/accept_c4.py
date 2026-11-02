"""C4 acceptance: Postgres adapter through the read-only ask login; roles isolated at the database level."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, py_json, pytest_check  # noqa: E402
import _testbed as tb  # noqa: E402

SETUP = r'''
import json, os, psycopg
with psycopg.connect(os.environ["GOVERNOR_PG_ADMIN_DSN"], autocommit=True) as c:
    c.execute("CREATE SCHEMA IF NOT EXISTS conformance")
    c.execute("DROP TABLE IF EXISTS conformance.t")
    c.execute("CREATE TABLE conformance.t AS SELECT g AS id, 'v' || g AS v, (g / 2.0)::numeric AS amount FROM generate_series(1, 2000) g")
    c.execute("GRANT USAGE ON SCHEMA conformance TO governor_ask")
    c.execute("GRANT SELECT ON conformance.t TO governor_ask")
    cfg = c.execute("SELECT rolconfig FROM pg_roles WHERE rolname = 'governor_ask'").fetchone()[0] or []
print(json.dumps({"rolconfig": cfg}))
'''

ADAPTER = r'''
import json
from governor.core.adapters import get_adapter, QueryTimeout, QueryError
a = get_adapter("postgres", allowed_roles=["governor_analyst", "governor_finance_admin"])
out = {"name": a.name, "dialect": a.dialect}
def attempt(key, fn, expect):
    try:
        fn(); out[key] = "none"
    except expect:
        out[key] = expect.__name__
    except Exception as e:
        out[key] = type(e).__name__
out["dry_good"] = bool(a.dry_run("SELECT v FROM conformance.t", timeout_s=5).ok)
out["dry_bad"] = bool(a.dry_run("SELECT nope FROM conformance.t", timeout_s=5).ok)
cols, rows = a.run("SELECT id, v, amount FROM conformance.t ORDER BY id", timeout_s=10, row_cap=1000)
out["row_cap"] = len(rows)
try:
    json.dumps(rows); out["json_safe"] = True
except TypeError:
    out["json_safe"] = False
attempt("timeout", lambda: a.run("SELECT pg_sleep(5)", timeout_s=1, row_cap=1), QueryTimeout)
attempt("write", lambda: a.run("CREATE TABLE conformance.x AS SELECT 1 AS a", timeout_s=5, row_cap=1), QueryError)
attempt("raw", lambda: a.run("SELECT count(*) FROM raw.olist_orders_dataset", timeout_s=5, row_cap=1), QueryError)
attempt("bad_role", lambda: a.run("SELECT 1", timeout_s=5, row_cap=1, role="governor_admin"), QueryError)
try:
    a.run("SELECT 1 AS one", timeout_s=5, row_cap=1, role="governor_analyst"); out["good_role"] = "ok"
except Exception as e:
    out["good_role"] = type(e).__name__
out["has_v"] = any(c.schema == "conformance" and c.table == "t" and c.column == "v" for c in a.list_columns(["conformance"]))
a.close()
print(json.dumps(out))
'''

BUILD = r'''
import json, os, psycopg
out = {}
with psycopg.connect(os.environ["BUILD_DSN"], autocommit=True) as c:
    try:
        c.execute("CREATE TABLE dev_governor.zz_c4 AS SELECT 1 AS a"); c.execute("DROP TABLE dev_governor.zz_c4"); out["dev"] = "ok"
    except Exception as e:
        out["dev"] = type(e).__name__
    try:
        c.execute("CREATE TABLE raw.zz_c4 AS SELECT 1 AS a"); out["raw"] = "created"
    except Exception as e:
        out["raw"] = type(e).__name__
print(json.dumps(out))
'''


def files_present():
    for rel in ("src/governor/core/adapters/postgres.py", "testbed/sql/roles.sql", "testbed/apply_roles.py"):
        check(f"{rel} exists", (ROOT / rel).is_file(), "missing")


def database():
    if not tb.docker_ok() or not tb.up():
        return
    try:
        if not tb.load_sample() or not tb.apply_roles("roles applied"):
            return
        tb.apply_roles("roles applied a second time (idempotent)")
        d, err = py_json(SETUP, env=tb.env())
        if check("conformance schema set up as admin", d is not None, err):
            cfg = " ".join(d["rolconfig"])
            check("governor_ask defaults to read-only transactions", "default_transaction_read_only=on" in cfg, cfg)
            check("governor_ask has a 10s statement timeout", "statement_timeout=10s" in cfg or "statement_timeout=10000" in cfg, cfg)
        d, err = py_json(ADAPTER, env=tb.env(GOVERNOR_PG_DSN=tb.ASK_DSN))
        if check("Postgres adapter runs as governor_ask", d is not None, err):
            check("adapter named postgres with dialect postgres", (d["name"], d["dialect"]) == ("postgres", "postgres"), str(d)[:200])
            check("dry_run passes a good query and fails a bad column", d["dry_good"] is True and d["dry_bad"] is False, str(d)[:200])
            check("run honours row_cap", d["row_cap"] == 1000, str(d["row_cap"]))
            check("run returns JSON-safe values (numeric included)", d["json_safe"] is True, "")
            check("statement timeout raises QueryTimeout", d["timeout"] == "QueryTimeout", d["timeout"])
            check("a write is refused by the database with QueryError", d["write"] == "QueryError", d["write"])
            check("governor_ask cannot read raw tables", d["raw"] == "QueryError", d["raw"])
            check("a role outside allowed_roles is refused with QueryError", d["bad_role"] == "QueryError", d["bad_role"])
            check("an allowed role can be set", d["good_role"] == "ok", d["good_role"])
            check("list_columns returns real columns", d["has_v"] is True, "")
        d, err = py_json(BUILD, env=tb.env(BUILD_DSN=tb.BUILD_DSN))
        if check("governor_build can log in", d is not None, err):
            check("governor_build can create tables in dev_governor", d["dev"] == "ok", d["dev"])
            check("governor_build cannot create tables in raw", d["raw"] != "created", d["raw"])
    finally:
        tb.down()


guarded("files", files_present)
guarded("database", database)
pytest_check("tests")
finish("C4")
