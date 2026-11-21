"""Server-sent events for one run log.

``timing`` is the clock and the sleep. Tests replace them so a replay finishes
in milliseconds. Live polling waits at most half a second, then stops on
``run_finished`` or 30 minutes without a new event.
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from datetime import datetime
from pathlib import Path

from governor.integrations.console.runs import read_events

_GAP_CAP_S = 2.0
_SPEED_MIN = 1.0
_SPEED_MAX = 32.0
_FIELDS = (
    "v", "ts", "run_id", "graph", "seq", "type", "node", "attempt", "duration_ms",
    "summary", "status", "metrics", "error_code", "target_name",
)


class Timing:
    """The clock the stream waits on. Replace ``now`` and ``sleep`` in tests."""

    def __init__(self) -> None:
        self.poll_s = 0.5
        self.idle_s = 30 * 60
        self.heartbeat_s = 15.0

    def now(self) -> float:
        return time.monotonic()

    def sleep(self, seconds: float) -> None:
        if seconds > 0:
            time.sleep(seconds)


timing = Timing()


def clamp_speed(speed: float) -> float:
    try:
        value = float(speed)
    except (TypeError, ValueError):
        return _SPEED_MIN
    if value != value or value in (float("inf"), float("-inf")):  # NaN or infinity
        return _SPEED_MIN
    if value < _SPEED_MIN:
        return _SPEED_MIN
    if value > _SPEED_MAX:
        return _SPEED_MAX
    return value


def _seq(event: dict) -> int | None:
    seq = event.get("seq")
    if isinstance(seq, bool) or not isinstance(seq, int):
        return None
    return seq


def _ordered(events: list[dict]) -> list[dict]:
    numbered = [(index, event) for index, event in enumerate(events) if _seq(event) is not None]
    numbered.sort(key=lambda item: (item[1]["seq"], item[0]))
    seen: set[int] = set()
    out: list[dict] = []
    for _, event in numbered:
        seq = event["seq"]
        if seq in seen:
            continue
        seen.add(seq)
        out.append(event)
    return out


def _public(event: dict) -> dict:
    out = {}
    for key in _FIELDS:
        if key not in event:
            continue
        value = event[key]
        if key == "target_name":
            if not isinstance(value, str) or "/" in value or "\\" in value or ".." in value:
                continue
        if isinstance(value, str) and ("\\" in value or "://" in value):
            continue
        out[key] = value
    return out


def _frame(event: dict) -> str:
    public = _public(event)
    data = json.dumps(public, ensure_ascii=False, separators=(",", ":"))
    return f"id: {public.get('seq', 0)}\nevent: {public.get('type', 'message')}\ndata: {data}\n\n"


def _stamp(value: object) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed


def gap_seconds(previous: object, current: object, speed: float) -> float:
    """Original gap divided by speed, never more than two seconds."""
    start, end = _stamp(previous), _stamp(current)
    if start is None or end is None:
        return 0.0
    delta = (end - start).total_seconds()
    if delta <= 0:
        return 0.0
    return min(_GAP_CAP_S, delta / clamp_speed(speed))


def _heartbeat(last_beat: float) -> tuple[str | None, float]:
    now = timing.now()
    if now - last_beat >= timing.heartbeat_s:
        return ": heartbeat\n\n", now
    return None, last_beat


def iter_frames(path: Path, *, replay: bool, speed: float, last_id: int) -> Iterator[str]:
    """Yield SSE frames. Replay paces a finished log. Live tails until the run ends or goes idle."""
    speed = clamp_speed(speed)
    ordered = _ordered(read_events(path))
    previous: str | None = None
    pending: list[dict] = []
    for event in ordered:
        if event["seq"] <= last_id:
            if isinstance(event.get("ts"), str):
                previous = event["ts"]
            continue
        pending.append(event)

    if replay:
        last_beat = timing.now()
        for event in pending:
            wait = gap_seconds(previous, event.get("ts"), speed)
            if wait > 0:
                timing.sleep(wait)
                comment, last_beat = _heartbeat(last_beat)
                if comment:
                    yield comment
            yield _frame(event)
            if isinstance(event.get("ts"), str):
                previous = event["ts"]
        return

    for event in pending:
        yield _frame(event)
        if event.get("type") == "run_finished":
            return

    sent = max((event["seq"] for event in ordered), default=last_id)
    last_progress = timing.now()
    last_beat = last_progress
    while True:
        fresh = [event for event in _ordered(read_events(path)) if event["seq"] > sent]
        if fresh:
            for event in fresh:
                sent = event["seq"]
                yield _frame(event)
                if event.get("type") == "run_finished":
                    return
            last_progress = timing.now()
            continue
        if timing.now() - last_progress >= timing.idle_s:
            return
        if timing.now() - last_beat >= timing.heartbeat_s:
            yield ": heartbeat\n\n"
            last_beat = timing.now()
        timing.sleep(min(0.5, max(0.0, timing.poll_s)))
