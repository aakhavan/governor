"""G9 acceptance: four reports (baseline/agent x tune/holdout), holdout run once, prompts frozen before the
holdout, no agent PII leak, eval report and README consistent with the report JSON, full suite green."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, frozen_ok, golden_leaks, guarded, pytest_check, sha256  # noqa: E402

R = ROOT / "evaluation/reports"
HEADINGS = ["## Problem", "## How to run", "## Architecture", "## Evaluation", "## Governance and policy",
            "## Decision trace", "## MCP", "## Limitations", "## Provenance"]
reports = {}


def load_reports():
    split = json.loads((ROOT / "evaluation/golden/split.json").read_text(encoding="utf-8"))
    sha = (ROOT / "evaluation/golden/FROZEN.sha256").read_text(encoding="utf-8")
    for system in ("baseline", "agent"):
        for sp in ("tune", "holdout"):
            f = R / f"{system}-{sp}.json"
            if not check(f"report {f.name} exists", f.is_file(), ""):
                continue
            rep = json.loads(f.read_text(encoding="utf-8"))
            reports[(system, sp)] = rep
            ids = sorted(i["id"] for i in rep["items"])
            check(f"{f.name} covers exactly the {sp} split", ids == sorted(split[sp]), f"{len(ids)} items")
            gs = str(rep.get("golden_sha") or "")
            check(f"{f.name} used the frozen golden set", len(gs) == 64 and gs in sha, gs[:20])


def holdout_once():
    log = ROOT / "evaluation/holdout_runs.log"
    lines = [l.split("\t") for l in log.read_text(encoding="utf-8").splitlines() if l.strip()] if log.is_file() else []
    systems = [l[1] for l in lines if len(l) >= 2]
    check("holdout run exactly once per system", sorted(systems) == ["agent", "baseline"], f"log: {systems}")
    pf = R / "PROMPTS_FROZEN.sha256"
    if check("PROMPTS_FROZEN.sha256 exists", pf.is_file(), ""):
        want = {}
        for line in pf.read_text(encoding="utf-8").splitlines():
            if line.strip():
                h, n = line.split(maxsplit=1)
                want[Path(n.strip().lstrip("*")).name] = h
        d = ROOT / "src/governor/ask/prompts"
        now = {p.name: sha256(p) for p in d.glob("*.md")}
        check("prompts unchanged since the freeze", want == now, f"frozen {sorted(want)} vs now {sorted(now)}")
        if lines:
            check("prompts frozen before the holdout runs", pf.stat().st_mtime <= max(
                (R / f"{s}-holdout.json").stat().st_mtime for s in ("agent", "baseline") if (R / f"{s}-holdout.json").is_file()), "")


def quality_and_cost():
    a = reports.get(("agent", "holdout"))
    if a:
        check("no PII leak in agent runs", a["summary"]["pii_leak"] is False
              and reports.get(("agent", "tune"), {}).get("summary", {}).get("pii_leak") is False, "")
    total = sum((rep["summary"].get("cost_usd") or 0) for rep in reports.values())
    check("total eval cost within the $3 budget", total <= 3.0, f"${total:.3f}")


def docs():
    rep = ROOT / "evaluation/eval_report.md"
    readme = ROOT / "README.md"
    check("evaluation/eval_report.md exists", rep.is_file(), "")
    text = readme.read_text(encoding="utf-8") if readme.is_file() else ""
    miss = [h for h in HEADINGS if h not in text]
    check("README has the required sections", not miss, f"missing: {miss}")
    check("README has a Mermaid diagram and points to PROVENANCE.md", "```mermaid" in text and "PROVENANCE.md" in text, "")
    a, b = reports.get(("agent", "holdout")), reports.get(("baseline", "holdout"))
    if a and b:
        nums = [f"{x['summary']['execution_accuracy']:.3f}" for x in (a, b) if x["summary"]["execution_accuracy"] is not None]
        miss = [n for n in nums if n not in text]
        check("README shows the holdout execution accuracy exactly as in the reports", nums and not miss, f"missing {miss}")
    check("demo script exists", (ROOT / "docs/demo-script.md").is_file(), "")
    bad = golden_leaks([f for f in (ROOT / "src/governor/ask/prompts").glob("*.md")])
    check("no golden text in prompts", not bad, ", ".join(bad))


guarded("reports", load_reports)
guarded("holdout", holdout_once)
guarded("quality", quality_and_cost)
guarded("docs", docs)
ok, why = frozen_ok()
check("golden set still frozen", ok, why)
pytest_check("tests")
finish("G9")
