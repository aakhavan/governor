"""C5 acceptance: per-role serving schemas (hashed for analysts, masked for finance), isolation, salt kept private."""
import secrets
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, py_json, pytest_check, run, tail  # noqa: E402
import _testbed as tb  # noqa: E402

POLICY = "customer_unique_id: person_id\ncustomer_zip_code_prefix: location\ncustomer_city: location\nreview_comment_message: free_text\n"
ACCESS = """version: 1
allowlist:
  models: []
limits:
  default_limit: 100
  row_cap: 1000
  timeout_s: 10
mask_value: "***"
roles:
  analyst:
    pii: aggregate_only
    grants: []
  finance_admin:
    pii: mask
    grants:
      - olist_customers_dataset.customer_city
"""

CHECKS = r'''
import json, os, re, psycopg
salt = os.environ["GOVERNOR_PII_SALT"]
out = {}
with psycopg.connect(os.environ["GOVERNOR_PG_ADMIN_DSN"], autocommit=True) as a:
    raw_ids = {r[0] for r in a.execute("SELECT customer_unique_id FROM raw.olist_customers_dataset")}
    raw_cities = {r[0] for r in a.execute("SELECT customer_city FROM raw.olist_customers_dataset")}
    raw_states = sorted(r[0] for r in a.execute("SELECT customer_state FROM raw.olist_customers_dataset"))
    defs = [r[0] for r in a.execute("SELECT definition FROM pg_views WHERE schemaname LIKE 'serve_%'")]
out["views"] = len(defs)
out["salt_in_defs"] = any(salt in d for d in defs)
def as_role(role, sql):
    with psycopg.connect(os.environ["ASK_DSN"]) as c:
        c.execute(f"SET ROLE {role}")
        return c.execute(sql).fetchall()
def denied(role, sql):
    try:
        as_role(role, sql)
        return False
    except Exception:
        return True
ids = [r[0] for r in as_role("governor_analyst", "SELECT customer_unique_id FROM serve_analyst.olist_customers_dataset")]
out["hashed"] = bool(ids) and all(re.fullmatch(r"[0-9a-f]{64}", i or "") for i in ids)
out["no_raw_values"] = not (set(ids) & raw_ids)
n = as_role("governor_analyst", "SELECT count(DISTINCT customer_unique_id) FROM serve_analyst.olist_customers_dataset")[0][0]
out["distinct_kept"] = n == len(raw_ids)
states = sorted(r[0] for r in as_role("governor_analyst", "SELECT customer_state FROM serve_analyst.olist_customers_dataset"))
out["non_pii_unchanged"] = states == raw_states
out["analyst_denied_finance"] = denied("governor_analyst", "SELECT 1 FROM serve_finance_admin.olist_customers_dataset LIMIT 1")
out["analyst_denied_private"] = denied("governor_analyst", "SELECT 1 FROM private.pii_salt")
out["analyst_denied_raw"] = denied("governor_analyst", "SELECT 1 FROM raw.olist_customers_dataset LIMIT 1")
fin = as_role("governor_finance_admin", "SELECT customer_unique_id, customer_city FROM serve_finance_admin.olist_customers_dataset")
out["finance_masked"] = bool(fin) and all(r[0] == "***" for r in fin)
out["finance_grant"] = {r[1] for r in fin} == raw_cities
out["finance_denied_analyst"] = denied("governor_finance_admin", "SELECT 1 FROM serve_analyst.olist_customers_dataset LIMIT 1")
print(json.dumps(out))
'''


def database():
    check("src/governor/core/serving.py exists", (ROOT / "src" / "governor" / "core" / "serving.py").is_file(), "missing")
    if not tb.docker_ok() or not tb.up():
        return
    try:
        if not tb.load_sample() or not tb.apply_roles():
            return
        salt = "c5salt" + secrets.token_hex(8)
        with tempfile.TemporaryDirectory() as d:
            policy, access = Path(d) / "policy.yaml", Path(d) / "access.yaml"
            policy.write_text(POLICY, encoding="utf-8")
            access.write_text(ACCESS, encoding="utf-8")
            args = [sys.executable, "-m", "governor.core.serving", "apply", "--source", "raw",
                    "--policy", str(policy), "--access", str(access)]
            env = tb.env(GOVERNOR_PII_SALT=salt)
            r = run(args, timeout=300, env=env)
            if not check("serving apply succeeds", r.returncode == 0, tail(r)):
                return
            r = run(args, timeout=300, env=env)
            check("serving apply is idempotent", r.returncode == 0, tail(r))
        d, err = py_json(CHECKS, env=tb.env(GOVERNOR_PII_SALT=salt, ASK_DSN=tb.ASK_DSN))
        if not check("serving checks run", d is not None, err):
            return
        check("one view per table per role (18 views)", d["views"] == 18, str(d["views"]))
        check("the salt never appears in a view definition", d["salt_in_defs"] is False, "")
        check("analyst sees PII as 64-hex digests", d["hashed"] is True, "")
        check("analyst view contains no raw PII values", d["no_raw_values"] is True, "")
        check("COUNT(DISTINCT) on hashed PII equals the raw distinct count", d["distinct_kept"] is True, "")
        check("non-PII columns pass through unchanged", d["non_pii_unchanged"] is True, "")
        check("analyst is denied the finance schema", d["analyst_denied_finance"] is True, "")
        check("analyst is denied private (salt)", d["analyst_denied_private"] is True, "")
        check("analyst is denied raw", d["analyst_denied_raw"] is True, "")
        check("finance sees ungranted PII masked", d["finance_masked"] is True, "")
        check("finance sees the granted column unmasked", d["finance_grant"] is True, "")
        check("finance is denied the analyst schema", d["finance_denied_analyst"] is True, "")
    finally:
        tb.down()


guarded("database", database)
pytest_check("tests", required=["test_validator_postgres_rejects_select_star", "test_validator_postgres_injects_limit",
                                "test_validator_postgres_default_deny",
                                "test_validator_postgres_rejects_role_switch", "test_postgres_timeout_clamped"])
finish("C5")
