"""G2b acceptance: golden set (40), gold SQL executes on green, split, frozen hashes, review table."""
import json
import re
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, guarded, load_yaml, py_json, pytest_check  # noqa: E402

G = ROOT / "evaluation/golden"
COUNTS = {"simple": 6, "join": 6, "time_grain": 6, "metric": 6, "ambiguous": 5, "policy": 6, "unanswerable": 5}
EXPECT = {"simple": {"answer"}, "join": {"answer"}, "time_grain": {"answer"}, "metric": {"answer"},
          "ambiguous": {"clarify"}, "policy": {"refuse", "aggregate", "mask"}, "unanswerable": {"unanswerable"}}
NEEDS_SQL = {"answer", "aggregate", "mask"}
METRICS_MIN = {"mrr", "arr", "active_subscriptions", "churned_subscriptions", "invoiced_revenue",
               "collected_revenue", "outstanding_receivables", "overdue_invoices"}
state = {}


def metrics():
    m = load_yaml(ROOT / "knowledge/metrics.yaml")["metrics"]
    keys = {"id", "label", "definition", "sql", "grain", "time_column", "synonyms", "owner"}
    bad = [x.get("id") for x in m if not keys <= set(x)]
    check("metrics.yaml: >= 8 metrics with all fields", len(m) >= 8 and not bad, f"{len(m)} metrics; incomplete: {bad}")
    ids = {x["id"] for x in m}
    check("metrics.yaml covers the required metrics", METRICS_MIN <= ids, f"missing: {sorted(METRICS_MIN - ids)}")
    state["metric_sql"] = {x["id"]: x["sql"] for x in m}


def questions():
    doc = load_yaml(G / "questions.yaml")
    qs = doc["questions"]
    state["qs"] = qs
    as_of = (ROOT / "artifacts/green/as_of.txt").read_text(encoding="utf-8").strip()
    check("questions.yaml as_of equals artifacts/green/as_of.txt", str(doc.get("as_of")).strip()[:10] == as_of[:10],
          f"{doc.get('as_of')} vs {as_of}")
    ids = [q["id"] for q in qs]
    check("exactly 40 questions, unique ids", len(qs) == 40 and len(set(ids)) == 40, f"{len(qs)} / {len(set(ids))} unique")
    got = Counter(q["category"] for q in qs)
    check("category counts", dict(got) == COUNTS, str(dict(got)))
    bad = [q["id"] for q in qs if q.get("expect") not in EXPECT.get(q.get("category"), set())]
    check("expect matches category", not bad, f"bad: {bad}")
    bad = [q["id"] for q in qs if (q["expect"] in NEEDS_SQL) != bool(q.get("gold_sql"))]
    check("gold_sql present exactly for answer/aggregate/mask", not bad, f"bad: {bad}")
    bad = [q["id"] for q in qs if q["expect"] == "clarify" and not q.get("missing_slot")]
    check("ambiguous questions name a missing_slot", not bad, f"bad: {bad}")
    pol = [q for q in qs if q["category"] == "policy"]
    roles = {q["role"] for q in pol}
    kinds = {q["expect"] for q in pol}
    check("policy items cover both roles and refuse/aggregate/mask", roles == {"analyst", "finance_admin"}
          and kinds == {"refuse", "aggregate", "mask"}, f"roles {sorted(roles)}, kinds {sorted(kinds)}")
    words = {"dim_accounts", "fct_invoices", "fct_revenue_daily", "mrr_monthly", "select ", "_id"}
    bad = [q["id"] for q in qs if any(w in q["question"].lower() for w in words)]
    check("questions do not name tables, columns or SQL", not bad, f"bad: {bad}")
    sqls = {q["id"]: q["gold_sql"] for q in qs if q.get("gold_sql")}
    star = re.compile(r"select\s+(distinct\s+)?\*|\.\*|,\s*\*\s*(,|from)", re.IGNORECASE)
    bad = [i for i, s in sqls.items() if star.search(s)
           or any(w in s.lower() for w in ("now()", "current_date", "current_timestamp"))]
    check("gold SQL: no SELECT *, no now()/current_date", not bad, f"bad: {bad}")
    state["sqls"] = sqls


def gold_sql_runs():
    sqls = {**state["sqls"], **{f"metric:{k}": v for k, v in state.get("metric_sql", {}).items()}}
    code = ("import duckdb, json, sys, sqlglot\n"
            "from sqlglot import exp\n"
            "from governor.core import paths as p\n"
            "allowed=set(__import__('yaml').safe_load(open('knowledge/access.yaml',encoding='utf-8'))['allowlist']['models'])\n"
            "from governor.core.warehouse import connect\nsqls=json.loads(sys.stdin.read()); c=connect(); out={}\n"
            "for k,s in sqls.items():\n"
            "    try:\n"
            "        tree=sqlglot.parse_one(s, read='duckdb')\n"
            "        ctes={c_.alias_or_name for c_ in tree.find_all(exp.CTE)}\n"
            "        tabs={t.name for t in tree.find_all(exp.Table)} - ctes\n"
            "        rows=c.execute(s).fetchall()\n"
            "        out[k]={'rows':len(rows),'bad_tables':sorted(tabs-allowed)}\n"
            "    except Exception as e:\n"
            "        out[k]={'error':f'{type(e).__name__}: {e}'[:160]}\n"
            "c.close(); print(json.dumps(out))")
    from _common import run
    r = run([sys.executable, "-c", code], timeout=300, stdin=json.dumps(sqls))
    from _common import last_json, tail
    data = last_json(r.stdout)
    if not check("gold and metric SQL can be checked", data is not None, tail(r)):
        return
    err = {k: v["error"] for k, v in data.items() if "error" in v}
    check("every gold/metric SQL executes on the green warehouse", not err, json.dumps(err)[:240] if err else f"{len(data)} ok")
    empty = [k for k, v in data.items() if v.get("rows") == 0]
    check("every gold/metric SQL returns rows", not empty, f"empty: {empty}")
    bad = {k: v["bad_tables"] for k, v in data.items() if v.get("bad_tables")}
    check("gold/metric SQL uses allowlisted marts only", not bad, json.dumps(bad)[:240])


def split():
    s = json.loads((G / "split.json").read_text(encoding="utf-8"))
    tune, hold = s.get("tune", []), s.get("holdout", [])
    ids = {q["id"] for q in state["qs"]}
    check("split 25 tune / 15 holdout, disjoint, covers all", len(tune) == 25 and len(hold) == 15
          and not set(tune) & set(hold) and set(tune) | set(hold) == ids, f"{len(tune)}/{len(hold)}")
    cat = {q["id"]: q["category"] for q in state["qs"]}
    miss = [c for c in COUNTS if c not in {cat[i] for i in hold if i in cat} or c not in {cat[i] for i in tune if i in cat}]
    check("every category in both tune and holdout", not miss, f"missing: {miss}")
    ok, why = frozen_ok()
    check("FROZEN.sha256 matches questions.yaml and split.json", ok, why)


def checker():
    cases = [
        ([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], False, 1e-6, True),
        ([(1, "a"), (2, "b")], [(2, "b"), (1, "a")], True, 1e-6, False),
        ([(1, "a")], [("a", 1)], False, 1e-6, True),
        ([(100.0,)], [(100.00005,)], False, 1e-6, True),
        ([(100.0,)], [(100.01,)], False, 1e-6, False),
        ([(1,), (1,)], [(1,)], False, 1e-6, False),
        ([(None,)], [(None,)], False, 1e-6, True),
        ([(None,)], [(0,)], False, 1e-6, False),
        ([(1, 2)], [(1, 2, 3)], False, 1e-6, False),
        ([], [], False, 1e-6, True),
    ]
    code = ("import json, sys; from governor.eval.checker import compare\n"
            "cases=json.loads(sys.stdin.read()); out=[]\n"
            "for g,p_,o,t,_ in cases:\n"
            "    out.append(bool(compare([tuple(r) for r in g],[tuple(r) for r in p_],order_matters=o,rel_tol=t).equal))\n"
            "print(json.dumps(out))")
    from _common import last_json, run, tail
    r = run([sys.executable, "-c", code], timeout=120, stdin=json.dumps(cases))
    got = last_json(r.stdout)
    if not check("checker.compare runs", got is not None, tail(r)):
        return
    wrong = [i for i, (c, g) in enumerate(zip(cases, got)) if c[4] != g]
    check("checker.compare decides the 10 locked cases", not wrong and len(got) == len(cases), f"wrong cases: {wrong}")



def no_prompts_yet():
    d = ROOT / "src/governor/ask/prompts"
    found = [p.name for p in d.glob("*.md")] if d.is_dir() else []
    check("no agent prompts exist yet (golden set frozen first)", not found, f"found: {found}")



def frozen_api():
    data, err = py_json("import json; from governor.eval.golden import verify_frozen, load_golden, load_split\n"
                        "g = load_golden(); s = load_split(); print(json.dumps({'ok': bool(verify_frozen())}))")
    check("governor.eval.golden loads the files and verify_frozen() is true", bool(data and data["ok"]), err)


def review_table():
    p = G / "REVIEW.md"
    text = p.read_text(encoding="utf-8") if p.is_file() else ""
    missing = [q["id"] for q in state.get("qs", []) if q["id"] not in text]
    check("evaluation/golden/REVIEW.md lists every question for the gate review", p.is_file() and not missing,
          f"missing: {missing[:5]}" if missing else "")


guarded("metrics", metrics)
guarded("questions", questions)
if "sqls" in state:
    guarded("gold sql", gold_sql_runs)
    guarded("split", split)
    guarded("review table", review_table)
guarded("frozen api", frozen_api)
guarded("no prompts", no_prompts_yet)
pytest_check("tests/eval")
finish("G2b")
