"""Locked security cases for G5a/G5b (human-owned contract). Imported by both acceptance scripts."""

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
    ("analyst", "SELECT count(*) AS n FROM fct_invoices WHERE issued_at > current_date - INTERVAL 30 DAY", ["VOLATILE_TIME"]),
    ("analyst", "SELECT now() AS t", ["VOLATILE_TIME"]),
    ("analyst", "SELECT invoice_id FROM fct_invoices WHERE issued_at >= today() - 7", ["VOLATILE_TIME"]),
    ("analyst", "SELECT a FROM read_json_auto('x.json')", ["TABLE_FUNCTION"]),
    ("analyst", "SELECT file FROM glob('*.csv')", ["TABLE_FUNCTION"]),
    ("analyst", "SELECT table_name FROM duckdb_tables()", ["TABLE_FUNCTION"]),
    ("analyst", "WITH x AS (SELECT payment_id FROM raw.payments) SELECT payment_id FROM x", ["TABLE_NOT_ALLOWED"]),
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
    ("finance_admin", "SELECT DISTINCT contact_name FROM dim_accounts LIMIT 5", "distinct_mask"),
    ("finance_admin", "SELECT country, count(DISTINCT contact_name) AS n FROM dim_accounts GROUP BY country", "count_not_masked"),
    ("analyst", "SELECT count(*) AS n FROM fct_invoices WHERE issued_at >= DATE '2026-01-01'", "rows"),
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
