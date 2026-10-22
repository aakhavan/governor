"""G5a acceptance: the locked validator cases (codes, LIMIT rewrite, outer-projection masking) and no hard-coded policy."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import check, finish, grep, guarded, last_json, pytest_check, run, tail  # noqa: E402
from _g5_cases import ACCEPT, CODE, REJECT  # noqa: E402

def validator_cases():
    payload = {"validate": [[r, s] for r, s, _ in REJECT] + [[r, s] for r, s, _ in ACCEPT], "execute": []}
    r = run([sys.executable, "-c", CODE], timeout=300, stdin=json.dumps(payload))
    d = last_json(r.stdout)
    if not check("validator runs on the locked cases", d is not None, tail(r)):
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

    rewrites = {s: g.get("sql") or "" for (_, s, _), g in zip(ACCEPT, v[len(REJECT):])}
    q = "SELECT country, count(*) AS n FROM dim_accounts GROUP BY country"
    check("validator injects a LIMIT when missing", "limit" in rewrites.get(q, "").lower(), rewrites.get(q, "")[:120])
    q = "SELECT DISTINCT contact_name FROM dim_accounts LIMIT 5"
    low = rewrites.get(q, "").lower()
    check("finance_admin masking wraps the original query (outer projection, DISTINCT kept inside)",
          "distinct" in low and low.count("select") >= 2 and "***" in low, low[:160])


def no_policy_in_code():
    hits = grep(["src/governor/ask/validator.py", "src/governor/ask/policy.py"],
                r"contact_email|contact_name|card_last4|'\*\*\*'|\"\*\*\*\"|dim_accounts|fct_invoices")
    check("no policy values (columns, mask, models) hard-coded in validator/policy/executor", not hits, ", ".join(hits[:5]))


guarded("validator", validator_cases)
guarded("policy in code", no_policy_in_code)
pytest_check("tests/ask")
finish("G5a")
