"""CLI: ask one question through the governor-ask graph, or resume a paused one.

    uv run python -m governor.ask.run "QUESTION" --role analyst [--thread ID] [--llm fake:SCRIPT.json|openrouter]
    uv run python -m governor.ask.run --resume THREAD_ID --answer "TEXT" [--llm ...]

Prints the answer card (or the clarifying question). The last stdout line is
JSON ``{outcome, trace_id, thread_id}``; a paused question has outcome
``clarify`` and no trace yet. Graph state is checkpointed in SQLite under
``paths.STATE``, so ``--resume`` works from a new process; a finished run's
checkpoints are deleted (see ``governor.ask.checkpoints``). ``--llm`` is not
saved with the thread: pass the same kind (or a script for the remaining
replies) when resuming.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from governor.ask import checkpoints
from governor.ask.graph import build_graph
from governor.ask.policy import roles
from governor.core import paths

PREVIEW_ROWS = 20


@contextmanager
def sqlite_checkpointer(path: Path | None = None) -> Iterator[SqliteSaver]:
    """A SqliteSaver on ``<state dir>/checkpoints.sqlite`` (secure_delete on); closed on exit."""
    with checkpoints.open_saver(path or paths.CHECKPOINTS) as saver:
        yield saver


def make_llm(spec: str) -> Any:
    """``fake:SCRIPT.json`` -> scripted FakeLLM; ``fake`` -> FakeLLM; ``openrouter`` -> None (per-node models)."""
    if spec == "openrouter":
        return None
    from governor.ask.llm_testing import FakeLLM, load_script

    if spec == "fake":
        return FakeLLM()
    if spec.startswith("fake:"):
        return load_script(spec.split(":", 1)[1])
    raise SystemExit(f"--llm must be fake, fake:SCRIPT.json or openrouter, got {spec!r}")


def _fixtures(args: argparse.Namespace) -> dict:
    """Hidden test options that point the graph at a fixture warehouse."""
    out: dict[str, Any] = {}
    if args.database:
        out["database"] = args.database
    if args.access:
        out["access_path"] = args.access
    if args.meta:
        out["meta_path"] = args.meta
    if args.cards:
        out["cards"] = json.loads(args.cards.read_text(encoding="utf-8"))
    if args.as_of:
        out["as_of"] = datetime.fromisoformat(args.as_of)
    return out


def render(card: dict) -> str:
    """The answer card as plain text."""
    lines = [card.get("text") or ""]
    columns, rows = card.get("columns") or [], card.get("rows") or []
    if columns:
        lines += ["", " | ".join(columns)]
        lines += [" | ".join("" if v is None else str(v) for v in row) for row in rows[:PREVIEW_ROWS]]
        if len(rows) > PREVIEW_ROWS:
            lines.append(f"... {len(rows) - PREVIEW_ROWS} more rows")
    if card.get("sql"):
        lines += ["", "SQL:", card["sql"]]
    if card.get("models"):
        lines.append(f"Models: {', '.join(card['models'])}")
    if card.get("sources"):
        lines.append(f"Sources: {', '.join(card['sources'])}")
    for fresh in card.get("freshness") or []:
        lines.append(f"Freshness: {fresh['source']} {fresh['status']} ({fresh['age_hours_at_as_of']} h at as_of)")
    if card.get("as_of"):
        lines.append(f"As of: {card['as_of']}")
    return "\n".join(lines)


def parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="python -m governor.ask.run", description=__doc__.splitlines()[0])
    parser.add_argument("question", nargs="?")
    parser.add_argument("--role", help="a role from knowledge/access.yaml (analyst, finance_admin)")
    parser.add_argument("--thread", help="thread id for a new question (default: a new uuid)")
    parser.add_argument("--resume", metavar="THREAD_ID", help="resume a thread paused at clarify")
    parser.add_argument("--answer", help="the answer to the clarifying question (with --resume)")
    parser.add_argument("--llm", default="openrouter", help="fake, fake:SCRIPT.json or openrouter")
    for hidden in ("--database", "--access", "--meta", "--cards"):  # test fixtures
        parser.add_argument(hidden, type=Path, default=None, help=argparse.SUPPRESS)
    parser.add_argument("--as-of", default=None, help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.resume:
        if args.answer is None or args.question:
            parser.error("--resume needs --answer and no question")
    elif not args.question or not args.role:
        parser.error("a question and --role are required (or --resume ID --answer TEXT)")
    elif args.role not in roles(args.access):
        parser.error(f"unknown role {args.role!r}; known: {', '.join(roles(args.access))}")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    sys.stdout.reconfigure(encoding="utf-8")
    thread_id = args.resume or args.thread or str(uuid.uuid4())
    config = {"configurable": {"thread_id": thread_id}}
    with sqlite_checkpointer() as saver:
        graph = build_graph(llm=make_llm(args.llm), checkpointer=saver, **_fixtures(args))
        if args.resume:
            pending = graph.get_state(config)
            if not pending.next:
                print(f"thread {thread_id} is not waiting for an answer", file=sys.stderr)
                return 1
            role = (pending.values or {}).get("role")
            result = checkpoints.invoke(graph, saver, Command(resume=args.answer), config, role)
        else:
            checkpoints.prune_stale(saver)
            result = checkpoints.invoke(graph, saver, {"question": args.question, "role": args.role}, config, args.role)

    if result.get("__interrupt__"):
        print(f"Clarification needed: {result['__interrupt__'][0].value['missing_slot']}")
        print(f'Resume with: python -m governor.ask.run --resume {thread_id} --answer "..."')
        summary = {"outcome": "clarify", "trace_id": None, "thread_id": thread_id}
    else:
        print(render(result.get("answer") or {}))
        if result.get("trace_error"):
            print(f"warning: the trace was not stored ({result['trace_error']})", file=sys.stderr)
        trace = result.get("trace") or {}
        summary = {"outcome": trace.get("outcome"), "trace_id": trace.get("trace_id"), "thread_id": thread_id}
    print(json.dumps(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
