"""The capstone report, rendered from the evaluation report files (batch2b.md section 15).

::

    python -m governor.eval.capstone_report [--reports evaluation/reports/capstone/] [--out evaluation/capstone_report.md]

Reads every ``*.json`` in the reports folder and sorts it by content: build evaluations (``system`` agent or
baseline, from ``governor.eval.build_eval``), the certified-answer evaluation (``kind: certified_eval``) and the red
team (``kind: redteam``). Every number in the report is taken from those files; this module formats, it does not
re-score. Build reports are grouped by planner (``models.plan``) and gold dataset so the agent and the baseline sit
side by side.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from governor.core import paths

DEFAULT_REPORTS = paths.ROOT / "evaluation" / "reports" / "capstone"
DEFAULT_OUT = paths.ROOT / "evaluation" / "capstone_report.md"


# --------------------------------------------------------------------------- formatting


def num(value: Any, digits: int = 4) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, (int, float)):
        if float(value) == int(value) and abs(value) < 1e15:
            return str(int(value))
        return f"{value:.{digits}f}".rstrip("0").rstrip(".")
    return str(value)


def pct(rate: Any) -> str:
    return "n/a" if rate is None else f"{float(rate) * 100:.1f}%"


def usd(value: Any) -> str:
    return "unknown" if value is None else f"${float(value):.4f}"


def cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "\\|").replace("\n", " ")


def table(head: list[str], rows: list[list[Any]]) -> list[str]:
    out = ["| " + " | ".join(head) + " |", "|" + "|".join("---" for _ in head) + "|"]
    out += ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]
    return out


# --------------------------------------------------------------------------- loading


def load_reports(folder: Path) -> dict[str, list[tuple[str, dict]]]:
    found: dict[str, list[tuple[str, dict]]] = {"build": [], "certified": [], "redteam": [], "skipped": []}
    for path in sorted(Path(folder).glob("*.json")):
        try:
            doc = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            found["skipped"].append((path.name, {}))
            continue
        if not isinstance(doc, dict):
            found["skipped"].append((path.name, {}))
        elif doc.get("kind") == "certified_eval":
            found["certified"].append((path.name, doc))
        elif doc.get("kind") == "redteam":
            found["redteam"].append((path.name, doc))
        elif doc.get("system") in ("agent", "baseline") and isinstance(doc.get("runs"), list):
            found["build"].append((path.name, doc))
        else:
            found["skipped"].append((path.name, {}))
    return found


# --------------------------------------------------------------------------- sections


def _gold_total(doc: dict) -> Any:
    runs = doc.get("runs") or []
    return runs[0].get("gold_total") if runs else None


def build_section(reports: list[tuple[str, dict]]) -> list[str]:
    out = ["## Build: agent vs one-shot baseline", ""]
    if not reports:
        return out + ["No build evaluation report found.", ""]
    groups: dict[tuple[str, str], list[tuple[str, dict]]] = {}
    for name, doc in reports:
        planner = str((doc.get("models") or {}).get("plan") or "unknown")
        groups.setdefault((planner, str(doc.get("gold_dataset") or "?")), []).append((name, doc))
    for (planner, dataset), docs in sorted(groups.items()):
        out += [f"### Planner `{planner}`, gold dataset `{dataset}`", ""]
        rows = []
        for name, doc in sorted(docs, key=lambda d: (d[1].get("system") != "agent", d[0])):
            s = doc.get("summary") or {}
            mean = s.get("mean") or {}
            rows.append([
                doc.get("system"), f"`{name}`", (doc.get("models") or {}).get("write"), s.get("runs"),
                pct(s.get("built_rate")), pct(s.get("valid_design_first_try_rate")), pct(s.get("escalated_rate")),
                f"{num(mean.get('gold_passed'), 2)} / {num(_gold_total(doc))}", pct(s.get("gold_all_passed_rate")),
                pct(s.get("kpi_decisions_all_correct_rate")), num(mean.get("validation_repairs"), 2),
                num(mean.get("dbt_repairs"), 2), num(mean.get("tests_passed"), 2), num(mean.get("tests_failed"), 2),
                num(mean.get("blueprint_high"), 2), usd(doc.get("total_cost_usd")), num(mean.get("seconds"), 1),
            ])
        out += table(["system", "report", "write model", "runs", "built", "valid design 1st try", "escalated",
                      "mean gold passed", "all gold passed", "KPI decisions all correct", "mean validation repairs",
                      "mean dbt repairs", "mean tests passed", "mean tests failed", "mean high findings", "cost",
                      "mean seconds"], rows)
        out.append("")
        for name, doc in docs:
            notes = []
            if doc.get("approval"):
                notes.append(f"design approved programmatically as `{doc['approval']}`")
            if doc.get("stopped_by_budget"):
                notes.append(f"stopped by the budget cap {usd(doc.get('max_cost_usd'))} after "
                             f"{(doc.get('summary') or {}).get('runs')} of {doc.get('runs_requested')} runs")
            unknown = (doc.get("summary") or {}).get("cost_unknown_runs")
            if unknown:
                notes.append(f"{unknown} run(s) without a reported cost")
            statuses = (doc.get("summary") or {}).get("statuses") or {}
            if statuses:
                notes.append("statuses " + ", ".join(f"{k} {v}" for k, v in sorted(statuses.items())))
            if doc.get("gold_sha256"):
                notes.append(f"gold sha256 `{str(doc['gold_sha256'])[:12]}`")
            out.append(f"- {doc.get('system')} (`{name}`): " + "; ".join(notes) + ".")
        out.append("")
    return out


def certified_section(reports: list[tuple[str, dict]]) -> list[str]:
    out = ["## Certified answers", ""]
    if not reports:
        return out + ["No certified-answer evaluation report found.", ""]
    for name, doc in reports:
        s = doc.get("summary") or {}
        out += [f"### `{name}` (role `{doc.get('role')}`, model `{doc.get('model')}`)", "",
                f"- Passed: {s.get('passed')}/{s.get('questions')}.",
                f"- Outcome accuracy: {s.get('outcome_correct')}/{s.get('questions')} ({pct(s.get('outcome_accuracy'))}).",
                f"- Value accuracy on answerable questions: {s.get('value_correct')}/{s.get('answerable')} "
                f"({pct(s.get('value_accuracy'))}).",
                f"- Errors: {s.get('errors')}. Cost: {usd(s.get('cost_usd'))}"
                + (f" ({s.get('cost_unknown_calls')} call(s) without a cost)." if s.get("cost_unknown_calls") else "."),
                ""]
        rows = [[i.get("id"), i.get("expected_outcome"), i.get("outcome"), i.get("expected_kpi"), i.get("kpi_id"),
                 num(i.get("expected"), 6), num(i.get("value"), 6), "pass" if i.get("pass") else "FAIL", i.get("reason")]
                for i in doc.get("items") or []]
        out += table(["id", "expected outcome", "outcome", "expected KPI", "KPI", "expected value", "value", "result",
                      "reason"], rows)
        out.append("")
    return out


def redteam_section(reports: list[tuple[str, dict]]) -> list[str]:
    out = ["## Red team and release gate", ""]
    if not reports:
        return out + ["No red-team report found.", ""]
    for name, doc in reports:
        s = doc.get("summary") or {}
        out += [f"### `{name}` (role `{doc.get('role')}`, model `{doc.get('model')}`)", "",
                f"- Release gate: **{str(doc.get('gate')).upper()}** ({doc.get('gate_rule')}).",
                f"- Leaks: {doc.get('leaks')} ({s.get('attack_leaks')} on attacks, {s.get('near_miss_leaks')} on "
                f"near-misses) over {s.get('items')} items.",
                f"- False refusals: {doc.get('false_refusals')} of {s.get('near_misses')} near-misses.",
                f"- Person-level raw values sampled for detection: {doc.get('raw_values_sampled')} (held in memory, "
                "never written).",
                f"- Errors: {s.get('errors')}. Cost: {usd(s.get('cost_usd'))}.", ""]
        cats = s.get("attack_outcomes_by_category") or {}
        rows = [[c, ", ".join(f"{k} {v}" for k, v in sorted(o.items()))] for c, o in cats.items()]
        out += table(["attack category", "outcomes"], rows)
        out.append("")
        flagged = [i for i in doc.get("items") or [] if i.get("leak") or i.get("false_refusal")]
        if flagged:
            out += table(["id", "kind", "outcome", "leak kinds", "fields", "relations outside", "false refusal"],
                         [[i.get("id"), i.get("kind"), i.get("outcome"), ", ".join(i.get("leak_kinds") or []),
                           ", ".join(i.get("leak_fields") or []), ", ".join(i.get("relations_outside") or []),
                           num(i.get("false_refusal"))] for i in flagged])
        else:
            out.append("No item leaked and no near-miss was refused.")
        out.append("")
    return out


def cost_section(found: dict[str, list[tuple[str, dict]]]) -> list[str]:
    rows, known, unknown = [], 0.0, 0
    for group in ("build", "certified", "redteam"):
        for name, doc in found[group]:
            cost = doc.get("total_cost_usd")
            rows.append([group, f"`{name}`", usd(cost)])
            if cost is None:
                unknown += 1
            else:
                known += float(cost)
    out = ["## Costs", ""]
    if not rows:
        return out + ["No report found.", ""]
    out += table(["report", "file", "cost"], rows)
    out += ["", f"Sum of the reported costs: {usd(known)}"
            + (f"; {unknown} report(s) without a cost." if unknown else "."), ""]
    return out


def render(found: dict[str, list[tuple[str, dict]]], folder: Path) -> str:
    lines = ["# Capstone evaluation report", "",
             f"Generated by `governor.eval.capstone_report` from `{folder.as_posix()}`. Every number below is taken "
             "from the report files; nothing is re-scored here.", ""]
    lines += build_section(found["build"])
    lines += certified_section(found["certified"])
    lines += redteam_section(found["redteam"])
    lines += cost_section(found)
    if found["skipped"]:
        lines += ["Skipped (not a known report): " + ", ".join(f"`{n}`" for n, _ in found["skipped"]) + ".", ""]
    return "\n".join(lines).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m governor.eval.capstone_report")
    ap.add_argument("--reports", type=Path, default=DEFAULT_REPORTS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    if not args.reports.is_dir():
        print(f"capstone report: no reports folder {args.reports}", file=sys.stderr)
        return 1
    found = load_reports(args.reports)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render(found, args.reports), encoding="utf-8")
    print(json.dumps({"out": str(args.out), "build": len(found["build"]), "certified": len(found["certified"]),
                      "redteam": len(found["redteam"]), "skipped": len(found["skipped"])}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
