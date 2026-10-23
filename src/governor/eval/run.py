"""CLI: evaluate one system on one golden split and write the report.

    uv run python -m governor.eval.run --system baseline --split tune --llm fake

Writes ``<out>/<system>-<split>.json``; the last stdout line is the summary
as JSON. A holdout run is logged to the holdout log, and a second holdout
run of the same system exits with code 2 unless ``--force-holdout``.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from governor.core import paths
from governor.eval import golden, harness
from governor.eval.systems import available, get_system

DEFAULT_OUT = paths.ROOT / "evaluation" / "reports"
DEFAULT_HOLDOUT_LOG = paths.ROOT / "evaluation" / "holdout_runs.log"
EXIT_HOLDOUT_USED = 2


def holdout_already_run(log: Path, system: str) -> bool:
    """True when the log holds a completed holdout run of ``system``."""
    if not log.is_file():
        return False
    for line in log.read_text(encoding="utf-8").splitlines():
        parts = line.split("\t")
        if len(parts) == 3 and parts[1] == system:
            return True
    return False


def record_holdout(log: Path, system: str, sha: str) -> None:
    """Append ``<iso ts>\\t<system>\\t<golden_sha>`` (the timestamp is audit only)."""
    log.parent.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with log.open("a", encoding="utf-8", newline="\n") as f:
        f.write(f"{stamp}\t{system}\t{sha}\n")


def make_llm(kind: str):
    if kind == "fake":
        from governor.ask.llm_testing import FakeLLM

        return FakeLLM()
    from governor.ask.baseline import default_llm

    return default_llm()


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m governor.eval.run", description=__doc__.splitlines()[0])
    parser.add_argument("--system", required=True, help=f"one of: {', '.join(available())}")
    parser.add_argument("--split", required=True, choices=["tune", "holdout"])
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--llm", choices=["fake", "openrouter"], default="fake")
    parser.add_argument("--holdout-log", type=Path, default=DEFAULT_HOLDOUT_LOG)
    parser.add_argument("--force-holdout", action="store_true")
    parser.add_argument("--golden-dir", type=Path, default=None, help=argparse.SUPPRESS)  # test fixtures
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    if not golden.verify_frozen(args.golden_dir):
        print("golden set does not match FROZEN.sha256; refusing to run", file=sys.stderr)
        return 1
    if args.split == "holdout" and not args.force_holdout and holdout_already_run(args.holdout_log, args.system):
        print(
            f"holdout already run for {args.system} (see {args.holdout_log}); pass --force-holdout to run again",
            file=sys.stderr,
        )
        return EXIT_HOLDOUT_USED

    gold_as_of = golden.load_golden(args.golden_dir).as_of
    if args.golden_dir is None and gold_as_of != paths.as_of():
        print(f"warning: golden as_of {gold_as_of.isoformat()} != green as_of {paths.as_of().isoformat()}",
              file=sys.stderr)

    system = get_system(args.system, llm=make_llm(args.llm))
    report = harness.evaluate(system, args.split, args.golden_dir)
    report["llm"] = args.llm
    args.out.mkdir(parents=True, exist_ok=True)
    target = args.out / f"{args.system}-{args.split}.json"
    target.write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8", newline="\n")
    if args.split == "holdout":
        record_holdout(args.holdout_log, args.system, report["golden_sha"])

    print(f"wrote {target}")
    print(json.dumps(report["summary"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
