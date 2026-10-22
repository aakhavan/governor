"""G5b acceptance: executed results of the locked cases (LIMIT, row cap, masking semantics, grants), read-only executor guards."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import check, finish, grep, guarded, last_json, pytest_check, run, tail  # noqa: E402
from _g5_cases import ACCEPT, CODE, REJECT  # noqa: E402

def execution_cases():
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
        elif want == "distinct_mask" and not (got["row_count"] == 5 and all(r[0] == "***" for r in rows)):
            bad.append(f"DISTINCT changed by masking: {got['row_count']} rows (expected 5 masked rows)")
        elif want == "count_not_masked" and (not rows or any(not r[cols.index("n")].isdigit() for r in rows)):
            bad.append("COUNT(DISTINCT pii) was masked; it is a number, not a value")
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
    e.run_readonly("SELECT count(*) FROM fct_invoices a, fct_invoices b, fct_invoices c WHERE a.amount_eur + b.amount_eur + c.amount_eur > -1", timeout_s=1.0, row_cap=10)
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
                r"contact_email|contact_name|card_last4|'\*\*\*'|\"\*\*\*\"|dim_accounts|fct_invoices")
    check("no policy values (columns, mask, models) hard-coded in validator/policy/executor", not hits, ", ".join(hits[:5]))


guarded("execution", execution_cases)
guarded("executor", executor_guards)
guarded("policy in code", no_policy_in_code)
pytest_check("tests/ask")
finish("G5b")
