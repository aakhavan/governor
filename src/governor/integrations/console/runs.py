"""Find live and shipped demo runs. Live wins when a run id exists in both."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

from governor.core import paths
from governor.core.runtrace.fold import fold

GRAPHS = ("build", "ask")
RUN_ID = r"^[A-Za-z0-9_.-]{1,128}$"
_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def state_dir() -> Path:
    """The same folder the run log writer uses."""
    raw = os.environ.get("GOVERNOR_STATE_DIR")
    return paths.ROOT / raw if raw else paths.STATE


def demo_dir() -> Path:
    return paths.ROOT / "src" / "governor" / "integrations" / "console" / "demo"


def targets_root() -> Path:
    raw = os.environ.get("GOVERNOR_TARGETS_DIR")
    if not raw:
        return state_dir() / "targets"
    path = Path(raw)
    return path if path.is_absolute() else paths.ROOT / path


_RUN_ID = re.compile(RUN_ID)


def _safe_id(value: str) -> bool:
    return _RUN_ID.fullmatch(value) is not None


def read_events(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    rows: list[dict] = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _ordered(events: list[dict]) -> list[dict]:
    def key(item: tuple[int, dict]) -> tuple:
        index, event = item
        seq = event.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            return (0, seq, index)
        return (1, index, 0)

    ordered: list[dict] = []
    seen: set[int] = set()
    for _, event in sorted(enumerate(events), key=key):
        seq = event.get("seq")
        if isinstance(seq, int) and not isinstance(seq, bool):
            if seq in seen:
                continue
            seen.add(seq)
        ordered.append(event)
    return ordered


def _scan(root: Path, source: str) -> dict[tuple[str, str], tuple[str, Path]]:
    found: dict[tuple[str, str], tuple[str, Path]] = {}
    if not root.is_dir():
        return found
    for graph in GRAPHS:
        folder = root / graph
        if not folder.is_dir():
            continue
        for path in folder.glob("*.jsonl"):
            run_id = path.stem
            if _safe_id(run_id):
                found[(graph, run_id)] = (source, path)
    return found


def discover() -> dict[tuple[str, str], tuple[str, Path]]:
    """``(graph, run_id) -> (source, path)``. A live file replaces a demo with the same id."""
    found = _scan(demo_dir(), "demo")
    found.update(_scan(state_dir() / "runs", "live"))
    return found


def find_run(run_id: str) -> tuple[str, str, Path] | None:
    """``(source, graph, path)`` for one run id. Live wins. Newest file wins a cross-graph clash."""
    if not _safe_id(run_id):
        return None
    matches = [(graph, source, path) for (graph, rid), (source, path) in discover().items() if rid == run_id]
    if not matches:
        return None
    matches.sort(key=lambda item: (item[1] != "live", item[0]))
    graph, source, path = matches[0]
    return source, graph, path


def target_name(events: list[dict]) -> str | None:
    for event in events:
        if event.get("type") != "run_started":
            continue
        name = event.get("target_name")
        if isinstance(name, str) and _NAME.fullmatch(name):
            return name
    return None


def resolve_target(name: str | None) -> Path | None:
    """``<GOVERNOR_TARGETS_DIR>/<name>`` when that directory exists. Never a path from the client."""
    if name is None or not _NAME.fullmatch(name):
        return None
    root = targets_root().resolve()
    folder = (root / name).resolve()
    if folder.parent != root or not folder.is_dir():
        return None
    return folder


def _status(view: dict) -> str:
    run = view["run"]
    if run.get("state") == "failed":
        return "failed"
    status = run.get("status")
    if isinstance(status, str) and status:
        return status
    state = run.get("state")
    return state if isinstance(state, str) and state else "running"


def summarise(graph: str, run_id: str, source: str, events: list[dict]) -> dict:
    ordered = _ordered(events)
    view = fold(ordered)
    started = next((event.get("ts") for event in ordered if isinstance(event.get("ts"), str)), None)
    last = next((event.get("ts") for event in reversed(ordered) if isinstance(event.get("ts"), str)), None)
    run = view["run"]
    return {
        "run_id": run_id,
        "graph": graph,
        "started": started,
        "last_event": last,
        "status": _status(view),
        "elapsed_ms": run["elapsed_ms"],
        "cost_usd": run["cost_usd"],
        "llm_calls": run["llm_calls"],
        "source": source,
    }


def list_runs(graph: str | None, limit: int) -> list[dict]:
    rows = []
    for (item_graph, run_id), (source, path) in discover().items():
        if graph and item_graph != graph:
            continue
        rows.append(summarise(item_graph, run_id, source, read_events(path)))
    rows.sort(key=lambda item: (item["started"] or "", item["run_id"]), reverse=True)
    return rows[:limit]


def view_of(events: list[dict]) -> dict:
    return fold(_ordered(events))
