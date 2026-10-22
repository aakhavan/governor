"""G10a acceptance: tune reports for baseline and agent, prompts frozen and unchanged, no holdout run yet, tuning notes."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, golden_leaks, guarded, pytest_check, sha256  # noqa: E402

R = ROOT / "evaluation/reports"


def tune_reports():
    split = json.loads((ROOT / "evaluation/golden/split.json").read_text(encoding="utf-8"))
    sha = (ROOT / "evaluation/golden/FROZEN.sha256").read_text(encoding="utf-8")
    cost = 0.0
    for system in ("baseline", "agent"):
        f = R / f"{system}-tune.json"
        if not check(f"{f.name} exists", f.is_file(), ""):
            continue
        rep = json.loads(f.read_text(encoding="utf-8"))
        check(f"{f.name} covers exactly the tune split", sorted(i["id"] for i in rep["items"]) == sorted(split["tune"]), "")
        gs = str(rep.get("golden_sha") or "")
        check(f"{f.name} used the frozen golden set", len(gs) == 64 and gs in sha, gs[:20])
        cost += rep["summary"].get("cost_usd") or 0
        if system == "agent":
            check("agent made real model calls (cost > 0)", (rep["summary"].get("cost_usd") or 0) > 0, "")
    check("tune cost within the $2 step budget", cost <= 2.0, f"${cost:.3f}")


def freeze():
    pf = R / "PROMPTS_FROZEN.sha256"
    if not check("PROMPTS_FROZEN.sha256 exists", pf.is_file(), ""):
        return
    want = {}
    for line in pf.read_text(encoding="utf-8").splitlines():
        if line.strip():
            h, n = line.split(maxsplit=1)
            want[Path(n.strip().lstrip("*")).name] = h
    now = {p.name: sha256(p) for p in (ROOT / "src/governor/ask/prompts").glob("*.md")}
    check("frozen hashes match the current prompts", bool(now) and want == now, f"{sorted(want)} vs {sorted(now)}")
    bad = golden_leaks(list((ROOT / "src/governor/ask/prompts").glob("*.md")))
    check("no golden text in prompts", not bad, ", ".join(bad))


def no_holdout():
    log = ROOT / "evaluation/holdout_runs.log"
    lines = [l for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.is_file() else []
    check("no holdout run yet (that is G10b)", not lines and not list(R.glob("*-holdout.json")), f"{len(lines)} log lines")


def notes():
    t = (R / "TUNING.md").read_text(encoding="utf-8") if (R / "TUNING.md").is_file() else ""
    check("TUNING.md records the changes and before/after numbers", len(t.splitlines()) >= 8, f"{len(t.splitlines())} lines")


guarded("tune reports", tune_reports)
guarded("freeze", freeze)
guarded("no holdout", no_holdout)
guarded("tuning notes", notes)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests")
finish("G10a")
