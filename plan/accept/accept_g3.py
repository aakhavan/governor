"""G3 acceptance: harness metrics on self-test systems, leak detector, holdout guard, baseline (fake LLM)."""
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, grep, guarded, last_json, pytest_check, run, tail  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="g3-accept-"))
LOG = TMP / "holdout_runs.log"
KEYS = {"n", "execution_accuracy", "valid_sql_first", "valid_sql_final", "clarify_precision", "clarify_recall",
        "policy_compliance", "pii_leak", "cost_usd", "latency_s_p50"}
ITEM_KEYS = {"id", "category", "role", "expect", "behaviour", "correct", "sql", "leak", "cost_usd", "latency_s"}


def harness(system, split="tune", *extra):
    r = run([sys.executable, "-m", "governor.eval.run", "--system", system, "--split", split, "--out", str(TMP),
             "--holdout-log", str(LOG), "--llm", "fake", *extra], timeout=900)
    f = TMP / f"{system}-{split}.json"
    rep = json.loads(f.read_text(encoding="utf-8")) if f.is_file() else None
    return r, rep


def self_tests():
    r, rep = harness("oracle")
    if not check("oracle run writes a report", r.returncode == 0 and rep is not None, tail(r)):
        return
    s = rep["summary"]
    check("report summary has all metric keys", KEYS <= set(s), f"missing: {sorted(KEYS - set(s))}")
    check("report items have all keys", rep["items"] and ITEM_KEYS <= set(rep["items"][0]), "")
    check("report records golden_sha and as_of", bool(rep.get("golden_sha")) and bool(rep.get("as_of")), "")
    check("stdout last line is the summary JSON", last_json(r.stdout) == s, "")
    check("oracle: n = 25 on tune", s["n"] == 25, s["n"])
    check("oracle: every metric is 1.0 and no leak",
          s["execution_accuracy"] == 1.0 and s["clarify_precision"] == 1.0 and s["clarify_recall"] == 1.0
          and s["policy_compliance"] == 1.0 and s["pii_leak"] is False, json.dumps(s)[:240])

    r, rep = harness("null")
    if check("null run writes a report", r.returncode == 0 and rep is not None, tail(r)):
        s = rep["summary"]
        check("null: accuracy 0, clarify recall 0, precision null, no leak, policy < 1",
              s["execution_accuracy"] == 0.0 and s["clarify_recall"] == 0.0 and s["clarify_precision"] is None
              and s["pii_leak"] is False and (s["policy_compliance"] or 0) < 1.0, json.dumps(s)[:240])

    r, rep = harness("leaky")
    if check("leaky run writes a report", r.returncode == 0 and rep is not None, tail(r)):
        items = rep["items"]
        an = [i["leak"] for i in items if i["role"] == "analyst"]
        fa = [i["leak"] for i in items if i["role"] == "finance_admin"]
        check("leaky: run flagged, every analyst item leaks, granted email is not a leak for finance_admin",
              rep["summary"]["pii_leak"] is True and an and all(an) and not any(fa),
              f"analyst {sum(an)}/{len(an)}, finance_admin {sum(fa)}/{len(fa)}")


def leak_detector():
    cases = [
        ["analyst", "SELECT contact_email AS e FROM dim_accounts", ["e"], [["a@b.de"]], True],
        ["analyst", "SELECT lower(contact_name) AS n FROM dim_accounts", ["n"], [["max"]], True],
        ["analyst", "WITH x AS (SELECT contact_name AS k FROM dim_accounts) SELECT k FROM x", ["k"], [["Max"]], True],
        ["analyst", "SELECT count(DISTINCT contact_email) AS n FROM dim_accounts", ["n"], [[5]], False],
        ["analyst", "SELECT country, count(*) AS n FROM dim_accounts GROUP BY country", ["country", "n"], [["DE", 3]], False],
        ["finance_admin", "SELECT '***' AS contact_name FROM dim_accounts", ["contact_name"], [["***"]], False],
        ["finance_admin", "SELECT contact_name FROM dim_accounts", ["contact_name"], [["Max Mustermann"]], True],
        ["finance_admin", "SELECT contact_email FROM dim_accounts", ["contact_email"], [["a@b.de"]], False],
    ]
    code = ("import json, sys; from governor.eval.pii import detect_leak\n"
            "out=[bool(detect_leak(s, c, [tuple(r) for r in rows], role)) for role, s, c, rows, _ in json.loads(sys.stdin.read())]\n"
            "print(json.dumps(out))")
    r = run([sys.executable, "-c", code], timeout=120, stdin=json.dumps(cases))
    got = last_json(r.stdout)
    if check("detect_leak runs", got is not None, tail(r)):
        wrong = [i for i, (c, g) in enumerate(zip(cases, got)) if c[4] != g]
        check("detect_leak decides the 8 locked cases", not wrong and len(got) == len(cases), f"wrong cases: {wrong}")


def holdout_guard():
    r1, _ = harness("oracle", "holdout")
    r2, _ = harness("oracle", "holdout")
    r3, _ = harness("oracle", "holdout", "--force-holdout")
    lines = LOG.read_text(encoding="utf-8").strip().splitlines() if LOG.is_file() else []
    check("holdout: first run ok, second refused (exit 2), forced run ok",
          r1.returncode == 0 and r2.returncode == 2 and r3.returncode == 0, f"rc {r1.returncode}/{r2.returncode}/{r3.returncode}")
    check("holdout log has one line per completed run, tab-separated", len(lines) == 2
          and all(len(l.split("\t")) == 3 and l.split("\t")[1] == "oracle" for l in lines), f"{len(lines)} lines")


def baseline():
    r, rep = harness("baseline")
    if check("baseline (fake LLM) runs on tune", r.returncode == 0 and rep is not None, tail(r)):
        check("baseline report: 25 items, cost 0 with fake LLM", len(rep["items"]) == 25 and not rep["summary"]["cost_usd"], "")
    p = ROOT / "src/governor/ask/prompts/baseline.md"
    check("baseline prompt file exists", p.is_file(), "")
    hits = grep(["src/governor/ask/baseline.py"], r"import .*(validator|retrieval|executor)|from \.(validator|retrieval|executor)")
    check("baseline uses no retrieval, validator or executor", not hits, ", ".join(hits))
    from _common import golden_leaks
    bad = golden_leaks([f for f in (ROOT / "src/governor").rglob("*") if f.suffix in (".py", ".md")] +
                       [f for f in (ROOT / "tests").rglob("*.py")])
    check("no golden questions or gold SQL copied into src/ or tests/", not bad, ", ".join(bad[:5]))


def pinned_as_of():
    from _common import load_yaml, py_json
    pin = ROOT / "fixture/AS_OF"
    want = pin.read_text(encoding="utf-8").strip() if pin.is_file() else ""
    golden = str(load_yaml(ROOT / "evaluation/golden/questions.yaml").get("as_of"))
    check("fixture/AS_OF pins the golden set's as_of", bool(want) and want == golden, f"{want!r} vs {golden!r}")
    hits = grep(["fixture/build_green.py", "fixture/load_raw.py", "fixture/generate_raw.py"],
                r"datetime\.now|utcnow|date\.today|time\.time\(")
    check("build scripts never read the wall clock", not hits, ", ".join(hits[:4]))
    probe = ("import json; from governor.core.warehouse import connect; c = connect()\n"
             "r = c.execute('select count(*), sum(days_outstanding), sum(amount_eur) from fct_invoices').fetchone()\n"
             "c.close(); print(json.dumps([str(x) for x in r]))")
    before, err = py_json(probe)
    r = run([sys.executable, "fixture/build_green.py"], timeout=900)
    after, err2 = py_json(probe)
    asof = (ROOT / "artifacts/green/as_of.txt").read_text(encoding="utf-8").strip() if (ROOT / "artifacts/green/as_of.txt").is_file() else ""
    check("a rebuild reproduces as_of and the marts", r.returncode == 0 and asof == want and before == after and before is not None,
          err or err2 or f"as_of {asof!r}; fct_invoices {before} -> {after}")


guarded("pinned as_of", pinned_as_of)
guarded("self-test systems", self_tests)
guarded("leak detector", leak_detector)
guarded("holdout guard", holdout_guard)
guarded("baseline", baseline)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests/eval")
pytest_check("tests/ask")
finish("G3")
