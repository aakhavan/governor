"""G5 acceptance: the locked security cases for the validator, masking, LIMIT rewrite and the read-only executor.

These cases are the contract (human-owned). A case passes when `ok` matches and, for rejects, one of the
expected codes is present.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import check, finish, grep, guarded, last_json, pytest_check, run, tail  # noqa: E402

PII = ["PII_FORBIDDEN"]
REJECT = [  # role, sql, acceptable codes
    ("analyst", "DROP TABLE dim_accounts", ["NOT_SELECT"]),
    ("analyst", "DELETE FROM fct_invoices", ["NOT_SELECT"]),
    ("analyst", "INSERT INTO fct_invoices (invoice_id) VALUES (1)", ["NOT_SELECT"]),
    ("analyst", "UPDATE dim_accounts SET country = 'DE'", ["NOT_SELECT"]),
    ("analyst", "CREATE TABLE x AS SELECT 1", ["NOT_SELECT"]),
    ("analyst", "ATTACH 'other.duckdb' AS o", ["NOT_SELECT", "PARSE_ERROR"]),
    ("analyst", "COPY dim_accounts TO 'out.csv'", ["NOT_SELECT", "PARSE_ERROR"]),
    ("analyst", "PRAGMA database_list", ["NOT_SELECT", "PARSE_ERROR"]),
    ("analyst", "SELECT 1; DROP TABLE dim_accounts", ["MULTI_STATEMENT"]),
    ("analyst", "SELECT a FROM read_csv('secrets.csv')", ["TABLE_FUNCTION"]),
    ("analyst", "SELECT x FROM 'data.parquet'", ["TABLE_FUNCTION", "TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT range FROM range(10)", ["TABLE_FUNCTION"]),
    ("analyst", "SELECT table_name FROM information_schema.tables", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT payment_id FROM raw.payments", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT account_id FROM stg_crm__accounts", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT n FROM (SELECT count(*) AS n FROM raw.accounts) t", ["TABLE_NOT_ALLOWED"]),
    ("analyst", "SELECT nonexistent_col FROM dim_accounts", ["COLUMN_UNKNOWN"]),
    ("analyst", "SELECT * FROM fct_invoices", ["STAR"]),
    ("analyst", "SELECT d.* FROM dim_accounts d", ["STAR"]),
    ("analyst", "SELECT contact_email FROM dim_accounts", PII),
    ("analyst", "SELECT contact_email AS e FROM dim_accounts", PII),
    ("analyst", "SELECT lower(contact_name) AS n FROM dim_accounts", PII),
    ("analyst", "WITH x AS (SELECT contact_name AS k FROM dim_accounts) SELECT k FROM x", PII),
    ("analyst", "SELECT count(*) AS n FROM dim_accounts WHERE contact_email LIKE '%@example.com'", PII),
    ("analyst", "SELECT contact_name, count(*) AS n FROM dim_accounts GROUP BY contact_name", PII),
    ("analyst", "SELECT account_id FROM dim_accounts ORDER BY contact_email", PII),
    ("analyst", "SELECT i.invoice_id FROM fct_invoices i JOIN dim_accounts a ON i.account_id = a.account_id "
                "AND a.contact_name = 'Max'", PII),
    ("analyst", "SELECT max(contact_email) AS m FROM dim_accounts", PII),
    ("analyst", "SELECT country FROM dim_accounts UNION SELECT contact_email FROM dim_accounts", PII),
    ("analyst", "SELECT (SELECT contact_email FROM dim_accounts LIMIT 1) AS e", PII),
    ("admin", "SELECT country FROM dim_accounts", ["UNKNOWN_ROLE"]),
    ("analyst", "SELEC country FROM dim_accounts", ["PARSE_ERROR"]),
]
ACCEPT = [  # role, sql, check on the executed result
    ("analyst", "SELECT country, count(*) AS n FROM dim_accounts GROUP BY country", "default_limit"),
    ("analyst", "SELECT count(DISTINCT contact_email) AS n FROM dim_accounts", "rows"),
    ("analyst", 'sElEcT "country" FROM "dim_accounts" LIMIT 5', "le5"),
    ("analyst", "SELECT invoice_id FROM fct_invoices LIMIT 5000", "row_cap"),
    ("analyst", "WITH o AS (SELECT account_id, sum(amount_eur) AS total FROM fct_invoices WHERE days_outstanding > 30 "
                "GROUP BY account_id) SELECT a.country, sum(o.total) AS overdue FROM o JOIN dim_accounts a "
                "ON a.account_id = o.account_id GROUP BY a.country", "rows"),
    ("analyst", "SELECT 1 AS one -- ; DROP TABLE dim_accounts", "rows"),
    ("analyst", "SELECT count(*) AS n FROM fct_invoices", "rows"),
    ("finance_admin", "SELECT account_id, contact_name FROM dim_accounts LIMIT 3", "mask:contact_name"),
    ("finance_admin", "SELECT contact_email FROM dim_accounts LIMIT 3", "email"),
    ("finance_admin", "SELECT lower(contact_name) AS n FROM dim_accounts LIMIT 3", "mask:n"),
    ("finance_admin", "WITH x AS (SELECT contact_name AS k FROM dim_accounts) SELECT k FROM x LIMIT 3", "mask:k"),
]

CODE = r'''
import json, sys
from governor.ask.validator import validate
from governor.ask.executor import execute
cases = json.loads(sys.stdin.read()); out = []
for role, sql in cases["validate"]:
    try:
        v = validate(sql, role); out.append({"ok": bool(v.ok), "codes": list(v.codes), "sql": v.sql})
    except Exception as e:
        out.append({"ok": None, "codes": [], "error": f"{type(e).__name__}: {e}"[:160]})
ex = []
for role, sql in cases["execute"]:
    try:
        r = execute(sql, role)
        ex.append({"ok": bool(r.ok), "codes": list(r.codes), "columns": list(r.columns or []),
                   "rows": [list(map(str, row)) for row in (r.rows or [])][:5], "row_count": r.row_count, "sql": r.sql})
    except Exception as e:
        ex.append({"ok": None, "error": f"{type(e).__name__}: {e}"[:160]})
print(json.dumps({"validate": out, "execute": ex}))
'''


def validator_and_masking():
    payload = {"validate": [[r, s] for r, s, _ in REJECT] + [[r, s] for r, s, _ in ACCEPT],
               "execute": [[r, s] for r, s, _ in ACCEPT] + [["analyst", "SELECT contact_email FROM dim_accounts"]]}
    r = run([sys.executable, "-c", CODE], timeout=300, stdin=json.dumps(payload))
    d = last_json(r.stdout)
    if not check("validator and executor run", d is not None, tail(r)):
        return
    v = d["validate"]
    wrong = []
    for (role, sql, codes), got in zip(REJECT, v[:len(REJECT)]):
        if got.get("ok") is not False or not set(codes) & set(got.get("codes", [])):
            wrong.append(f"{sql[:40]!r} -> {got.get('codes') or got.get('error')}")
    check(f"{len(REJECT)} locked rejects decided with the right code", not wrong, "; ".join(wrong[:4]))
    wrong = [f"{s[:40]!r} -> {g.get('codes') or g.get('error')}" for (_, s, _), g in zip(ACCEPT, v[len(REJECT):])
             if g.get("ok") is not True]
    check(f"{len(ACCEPT)} locked valid queries accepted", not wrong, "; ".join(wrong[:4]))

    ex = d["execute"]
    bad = []
    for (role, sql, want), got in zip(ACCEPT, ex[:len(ACCEPT)]):
        if not got.get("ok"):
            bad.append(f"{sql[:30]!r} not executed: {got.get('codes') or got.get('error')}"); continue
        rows, cols, low = got["rows"], got["columns"], (got.get("sql") or "").lower()
        if want == "default_limit" and ("limit" not in low or got["row_count"] > 100):
            bad.append("no default LIMIT injected")
        elif want == "le5" and got["row_count"] > 5:
            bad.append("LIMIT 5 not kept")
        elif want == "row_cap" and got["row_count"] != 1000:
            bad.append(f"row cap: {got['row_count']} rows, expected 1000")
        elif want == "rows" and got["row_count"] < 1:
            bad.append(f"{sql[:30]!r} returned no rows")
        elif want.startswith("mask:"):
            col = want.split(":", 1)[1]
            i = cols.index(col) if col in cols else None
            if i is None or not rows or any(row[i] != "***" for row in rows):
                bad.append(f"{col} not masked: {rows[:2]}")
            if col == "contact_name" and rows and any(row[cols.index("account_id")] == "***" for row in rows):
                bad.append("account_id masked although it is not PII")
        elif want == "email" and (not rows or not all("@" in row[0] for row in rows)):
            bad.append("granted contact_email was masked or missing")
    check("executed results: LIMIT rewrite, row cap, masking by lineage, grant honoured", not bad, "; ".join(bad[:4]))
    blocked = ex[-1]
    check("execute refuses analyst PII with PII_FORBIDDEN and returns no rows",
          blocked.get("ok") is False and "PII_FORBIDDEN" in blocked.get("codes", []) and not blocked.get("rows"), str(blocked)[:200])


def executor_guards():
    code = r'''
import json
from governor.ask import executor as e
out = {}
try:
    e.run_readonly("SELECT count(*) FROM fct_invoices a, fct_invoices b, fct_invoices c WHERE a.amount_eur + b.amount_eur + c.amount_eur > -1", timeout_s=0.3, row_cap=10)
    out["timeout"] = "no exception"
except Exception as x:
    out["timeout"] = type(x).__name__
try:
    e.run_readonly("CREATE TABLE zz_accept AS SELECT 1 AS a", timeout_s=5, row_cap=10)
    out["write"] = "no exception"
except Exception as x:
    out["write"] = type(x).__name__
d = e.dry_run("SELECT nope FROM dim_accounts")
out["dry_run_bad"] = bool(d.ok)
d = e.dry_run("SELECT country FROM dim_accounts")
out["dry_run_good"] = bool(d.ok)
print(json.dumps(out))
'''
    r = run([sys.executable, "-c", code], timeout=120)
    d = last_json(r.stdout)
    if check("executor guards run", d is not None, tail(r)):
        check("run_readonly times out with QueryTimeout", d["timeout"] == "QueryTimeout", d["timeout"])
        check("run_readonly refuses writes (read-only connection) with QueryError", d["write"] == "QueryError", d["write"])
        check("dry_run fails on a bad column and passes a good query", d["dry_run_bad"] is False and d["dry_run_good"] is True, str(d))


def no_policy_in_code():
    hits = grep(["src/governor/ask/validator.py", "src/governor/ask/policy.py", "src/governor/ask/executor.py"],
                r"contact_email|contact_name|card_last4|'\*\*\*'|\"\*\*\*\"|dim_accounts")
    check("no policy values (columns, mask, models) hard-coded in validator/policy/executor", not hits, ", ".join(hits[:5]))


guarded("validator", validator_and_masking)
guarded("executor", executor_guards)
guarded("policy in code", no_policy_in_code)
pytest_check("tests/ask")
finish("G5")
