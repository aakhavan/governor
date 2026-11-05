"""D7 acceptance: ask's certified path on a certified sample build: answers with numbers from the certified table and a
citation; declined KPIs quote their gap; person-level requests refused; tampered model replies never become free SQL."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, grep, guarded, last_json, pytest_check, run, tail  # noqa: E402
import _testbed as tb  # noqa: E402
import _build as bd  # noqa: E402
import _build2 as b2  # noqa: E402


def reply(kpi=None, col=None, kind="month", value="2026-01", pick="value", category="answer", msf=None):
    return json.dumps({"kpi_id": kpi, "value_column": col, "period": {"kind": kind, "value": value},
                       "months_since_first": msf, "pick": pick, "category": category})


def ask(work, e, name, question, role, *replies):
    p = work / f"{name}.json"
    p.write_text(json.dumps({"certified": list(replies)}), encoding="utf-8")
    r = run([sys.executable, "-m", "governor.ask.certified", question, "--role", role, "--llm", f"fake:{p}"], timeout=600, env=e)
    d = last_json(r.stdout)
    return (d if isinstance(d, dict) else None), tail(r)


def static():
    check("certified.py exists", (ROOT / "src/governor/ask/certified.py").is_file(), "missing")
    check("certified prompt lives outside the frozen prompts", (ROOT / "src/governor/ask/certified_prompts/certified.md").is_file(), "")
    r = run(["git", "diff", "--quiet", "HEAD", "--", "src/governor/ask/prompts"], timeout=60)
    check("frozen ask prompts unchanged", r.returncode == 0, "")
    check("ask never imports build", not grep(["src/governor/ask"], r"governor\.build"), "")
    app = (ROOT / "src/governor/api/app.py").read_text(encoding="utf-8")
    check("API exposes /v1/ask/certified", "/v1/ask/certified" in app, "")


def database():
    work = bd.workdir()
    e = b2.env(work / "state")
    if not bd.testbed_ready():
        return
    try:
        if b2.certified_sample(work, e) is None:
            return
        d, err = ask(work, e, "gmv", "What was GMV in January 2026?", "analyst", reply("gmv", "gmv"))
        ok = d is not None and d.get("outcome") == "answer" and abs(float(d.get("value") or 0) - 455.0) < 1e-6
        check("answers GMV from the certified table", ok, err or str(d)[:200])
        cit = json.dumps(d.get("citation") if d else "")
        check("answer cites the KPI and its certifier", "gmv" in cit and "amir" in cit, cit[:200])
        check("answer text shows the number filled by code", d is not None and "455" in str(d.get("text")), str(d.get("text") if d else "")[:200])
        d2, err2 = ask(work, e, "gmv_fin", "What was GMV in January 2026?", "finance_admin", reply("gmv", "gmv"))
        check("finance role gets the same certified answer", d2 is not None and abs(float(d2.get("value") or 0) - 455.0) < 1e-6, err2 or str(d2)[:200])
        d3, err3 = ask(work, e, "conv", "What was our conversion rate?", "analyst", reply("conversion_rate", None, category="not_available"))
        check("declined KPI is not_available and quotes its gap",
              d3 is not None and d3.get("outcome") == "not_available" and "session" in str(d3.get("text")).lower(), err3 or str(d3)[:200])
        d4, err4 = ask(work, e, "pii", "List our customers' ids.", "analyst", reply(None, None, category="person_level"))
        check("person-level request refused", d4 is not None and d4.get("outcome") == "refused" and not d4.get("sql"), err4 or str(d4)[:200])
        d5, err5 = ask(work, e, "oos", "What will GMV be next month?", "analyst", reply(None, None, category="out_of_scope"))
        check("out-of-scope question unanswerable", d5 is not None and d5.get("outcome") == "unanswerable", err5 or str(d5)[:200])
        d6, err6 = ask(work, e, "tamper1", "GMV please", "analyst", reply("stg_customers", "customer_unique_id"))
        check("a reply naming an uncertified relation never runs", d6 is not None and d6.get("outcome") == "unanswerable" and not d6.get("sql"), err6 or str(d6)[:200])
        d7, err7 = ask(work, e, "tamper2", "GMV please", "analyst", reply("gmv", "customer_id"))
        check("a reply naming a non-value column never runs", d7 is not None and d7.get("outcome") == "unanswerable" and not d7.get("sql"), err7 or str(d7)[:200])
    finally:
        tb.down()


guarded("static", static)
guarded("database", database)
pytest_check("tests/ask")
finish("D7")
