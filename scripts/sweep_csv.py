"""Flatten build-evaluation reports into one CSV row per run (docs/capstone/batch2d.md section 26).

    python scripts/sweep_csv.py evaluation/reports/sweep      # writes <folder>/sweep_runs.csv

Every scalar field of a run becomes a column; nested values are skipped. No data values are involved: the reports
hold statuses, counts, costs and seconds.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path


def rows(folder: Path) -> list[dict]:
    out: list[dict] = []
    for path in sorted(folder.glob("*.json")):
        try:
            report = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        runs = report.get("runs")
        if not isinstance(runs, list):
            continue
        top = {k: v for k, v in report.items() if isinstance(v, (str, int, float, bool)) or v is None}
        for i, run in enumerate(runs, 1):
            if not isinstance(run, dict):
                continue
            models = report.get("models") if isinstance(report.get("models"), dict) else {}
            row = {"report": path.name, "plan_model": models.get("plan"), "write_model": models.get("write"),
                   **{f"report_{k}": v for k, v in top.items()}}
            row.update({k: v for k, v in run.items() if isinstance(v, (str, int, float, bool)) or v is None})
            out.append(row)
    return out


def main(argv: list[str]) -> int:
    if len(argv) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    folder = Path(argv[0])
    data = rows(folder)
    if not data:
        print(f"no build reports with runs in {folder}", file=sys.stderr)
        return 1
    fields: list[str] = []
    for row in data:
        fields += [k for k in row if k not in fields]
    target = folder / "sweep_runs.csv"
    with target.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields)
        writer.writeheader()
        writer.writerows(data)
    print(json.dumps({"out": str(target), "rows": len(data), "columns": len(fields)}))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
