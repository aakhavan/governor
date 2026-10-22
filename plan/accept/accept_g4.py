"""G4 acceptance: catalog + metric cards from metadata, BM25/hybrid retrieval, recall@3 on gold tables."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (ROOT, check, finish, frozen_ok, golden_leaks, guarded, last_json, load_yaml, py_json,  # noqa: E402
                     pytest_check, run, tail)

CARDS = ROOT / "artifacts/catalog_cards.jsonl"


def cards():
    r = run([sys.executable, "-m", "governor.ask.catalog", "build", "--out", str(CARDS)], timeout=300)
    if not check("catalog build exits 0", r.returncode == 0 and CARDS.is_file(), tail(r)):
        return
    rows = [json.loads(l) for l in CARDS.read_text(encoding="utf-8").splitlines() if l.strip()]
    keys = {"id", "kind", "name", "text", "tables", "pii_columns"}
    check("every card has the required fields", rows and all(keys <= set(c) for c in rows), f"{len(rows)} cards")
    access = load_yaml(ROOT / "knowledge/access.yaml")
    models = {c["name"] for c in rows if c["kind"] == "model"}
    want = set(access["allowlist"]["models"])
    check("one model card per allowlisted model, nothing else", models == want, f"{sorted(models)}")
    metrics = {m["id"] for m in load_yaml(ROOT / "knowledge/metrics.yaml")["metrics"]}
    got = {c["name"] for c in rows if c["kind"] == "metric"}
    check("one metric card per metrics.yaml entry", got == metrics, f"missing: {sorted(metrics - got)}")
    dim = next((c for c in rows if c["kind"] == "model" and c["name"] == "dim_accounts"), None)
    check("dim_accounts card lists its PII columns", dim and {"contact_email", "contact_name"} <= set(dim["pii_columns"]), "")
    mc = [c for c in rows if c["kind"] == "metric"]
    check("metric cards list the tables their SQL uses", mc and all(c["tables"] for c in mc), "")
    bad = golden_leaks([CARDS] + [f for f in (ROOT / "src/governor/ask").rglob("*.py")])
    check("no golden questions or gold SQL in cards or code", not bad, ", ".join(bad[:5]))


def search_api():
    code = ("import json; from governor.ask.retrieval import search\n"
            "a=search('monthly recurring revenue', k=3, mode='bm25')\n"
            "b=search('days outstanding', k=3, mode='bm25')\n"
            "print(json.dumps({'a': sorted({t for h in a for t in h.tables}), 'b': sorted({t for h in b for t in h.tables})}))")
    data, err = py_json(code, timeout=120)
    if check("retrieval.search runs", data is not None, err):
        check("'monthly recurring revenue' finds mrr_monthly in top 3", "mrr_monthly" in data["a"], data["a"])
        check("snake_case split: 'days outstanding' finds fct_invoices in top 3", "fct_invoices" in data["b"], data["b"])


def recall():
    split = json.loads((ROOT / "evaluation/golden/split.json").read_text(encoding="utf-8"))
    qs = {q["id"]: q for q in load_yaml(ROOT / "evaluation/golden/questions.yaml")["questions"]}
    n_gold = sum(1 for i in split["tune"] if qs[i].get("gold_sql"))
    r = run([sys.executable, "-m", "governor.ask.retrieval", "eval", "--split", "tune", "--mode", "bm25", "--k", "3"], timeout=300)
    d = last_json(r.stdout)
    if check("retrieval eval (bm25) runs", r.returncode == 0 and d is not None, tail(r)):
        check("eval counts only tune questions with gold SQL", d.get("n") == n_gold, f"n={d.get('n')}, expected {n_gold}")
        check("bm25 recall@3 on gold tables >= 0.80", (d.get("recall") or 0) >= 0.80, f"recall={d.get('recall')}")
    r = run([sys.executable, "-m", "governor.ask.retrieval", "eval", "--split", "tune", "--mode", "hybrid", "--k", "3",
             "--embedder", "fake"], timeout=300)
    d = last_json(r.stdout)
    check("hybrid eval runs with the fake embedder", r.returncode == 0 and d is not None and d.get("mode") == "hybrid", tail(r))


guarded("cards", cards)
guarded("search", search_api)
guarded("recall", recall)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests/ask")
finish("G4")
