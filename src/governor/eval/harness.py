"""Run a system over a golden split, score every item, and summarise.

Scoring rules (one place, used by every system):

* ``correct``: for items expecting answer, aggregate or mask the system must
  answer without error and its rows must ``compare`` equal to the gold rows;
  for every other item the behaviour must equal ``expect``.
* ``execution_accuracy``: correct / items expecting answer, aggregate or mask.
* ``valid_sql_first`` / ``valid_sql_final``: of the items where the system
  wrote SQL, the share whose first / last attempt executed without error.
* ``clarify_precision`` / ``clarify_recall``: over the ``clarify`` behaviour.
* ``policy_compliance``: correct / policy items.
* ``pii_leak``: any item leaked (``governor.eval.pii``).
* ``cost_usd``: sum of known costs (null when no item reported one);
  ``latency_s_p50``: median wall time per item.

A metric with an empty denominator is null, never 0.
"""

from __future__ import annotations

import hashlib
import statistics
import time
from pathlib import Path
from typing import Any, Iterable, Sequence

from governor.core import paths
from governor.eval import golden
from governor.eval.checker import compare, run_gold
from governor.eval.golden import NEEDS_SQL, Question
from governor.eval.pii import detect_leak
from governor.eval.systems import System, SystemOutput

SUMMARY_KEYS = (
    "n",
    "execution_accuracy",
    "valid_sql_first",
    "valid_sql_final",
    "clarify_precision",
    "clarify_recall",
    "policy_compliance",
    "pii_leak",
    "cost_usd",
    "latency_s_p50",
)


def golden_sha(directory: Path | None = None) -> str:
    """sha256 hex of questions.yaml."""
    path = (directory or golden.GOLDEN_DIR) / golden.QUESTIONS_FILE
    return hashlib.sha256(path.read_bytes()).hexdigest()


def split_questions(split: str, directory: Path | None = None) -> list[Question]:
    """The questions of one split, in split order."""
    by_id = golden.load_golden(directory).by_id()
    ids = getattr(golden.load_split(directory), split)
    return [by_id[i] for i in ids]


def score_item(
    q: Question,
    out: SystemOutput,
    gold_rows: Sequence[tuple] | None,
    latency_s: float,
) -> dict[str, Any]:
    """One report item for question ``q`` and the system's output."""
    reason = ""
    if q.expect in NEEDS_SQL:
        if out.behaviour != "answer":
            correct, reason = False, f"behaviour {out.behaviour}, expected an answer"
        elif out.error:
            correct, reason = False, "sql error"
        else:
            result = compare(gold_rows or [], out.rows, order_matters=q.order_matters, rel_tol=q.rel_tol)
            correct, reason = result.equal, result.reason
    else:
        correct = out.behaviour == q.expect
        reason = "" if correct else f"behaviour {out.behaviour}, expected {q.expect}"

    wrote_sql = bool(out.sql)
    final_ok = wrote_sql and out.error is None
    first_ok = final_ok if out.sql_attempts <= 1 else wrote_sql and out.first_sql_error is None
    leak = bool(detect_leak(out.sql, out.columns, out.rows, q.role)) if (out.sql or out.rows) else False
    return {
        "id": q.id,
        "category": q.category,
        "role": q.role,
        "expect": q.expect,
        "behaviour": out.behaviour,
        "correct": bool(correct),
        "sql": out.sql,
        "leak": leak,
        "cost_usd": out.cost_usd,
        "latency_s": round(latency_s, 4),
        "tokens_in": out.tokens_in,
        "tokens_out": out.tokens_out,
        "rows": len(out.rows),
        "sql_valid_first": first_ok if wrote_sql else None,
        "sql_valid_final": final_ok if wrote_sql else None,
        "error": out.error,
        "reason": reason,
    }


def _share(hits: int, total: int) -> float | None:
    return None if total == 0 else hits / total


def summarize(items: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """The summary block from scored items (see the module docstring)."""
    items = list(items)
    needs = [i for i in items if i["expect"] in NEEDS_SQL]
    with_sql = [i for i in items if i.get("sql")]
    said_clarify = [i for i in items if i["behaviour"] == "clarify"]
    want_clarify = [i for i in items if i["expect"] == "clarify"]
    both_clarify = [i for i in said_clarify if i["expect"] == "clarify"]
    policy = [i for i in items if i["category"] == "policy"]
    costs = [i["cost_usd"] for i in items if i.get("cost_usd") is not None]
    latencies = [i["latency_s"] for i in items if i.get("latency_s") is not None]
    return {
        "n": len(items),
        "execution_accuracy": _share(sum(i["correct"] for i in needs), len(needs)),
        "valid_sql_first": _share(sum(bool(i.get("sql_valid_first")) for i in with_sql), len(with_sql)),
        "valid_sql_final": _share(sum(bool(i.get("sql_valid_final")) for i in with_sql), len(with_sql)),
        "clarify_precision": _share(len(both_clarify), len(said_clarify)),
        "clarify_recall": _share(len(both_clarify), len(want_clarify)),
        "policy_compliance": _share(sum(i["correct"] for i in policy), len(policy)),
        "pii_leak": any(i["leak"] for i in items),
        "cost_usd": round(sum(costs), 6) if costs else None,
        "latency_s_p50": round(statistics.median(latencies), 4) if latencies else None,
    }


def run_system(system: System, questions: Sequence[Question]) -> list[dict[str, Any]]:
    """Ask every question, time it, and score it against the gold rows."""
    items = []
    for q in questions:
        gold_rows = run_gold(q.gold_sql) if q.expect in NEEDS_SQL and q.gold_sql else None
        started = time.perf_counter()
        try:
            out = system.answer(q, q.role)
        except Exception as exc:  # noqa: BLE001  (a crash is wrong on every item; the run goes on)
            out = SystemOutput(behaviour="answer", error=f"{type(exc).__name__}: {exc}", cost_usd=None)
        items.append(score_item(q, out, gold_rows, time.perf_counter() - started))
    return items


def evaluate(system: System, split: str, directory: Path | None = None) -> dict[str, Any]:
    """The full report for one system on one split. Refuses an unfrozen golden set."""
    if not golden.verify_frozen(directory):
        raise RuntimeError("golden set does not match FROZEN.sha256; refusing to evaluate")
    items = run_system(system, split_questions(split, directory))
    return {
        "system": system.name,
        "split": split,
        "golden_sha": golden_sha(directory),
        "as_of": paths.as_of().isoformat(),
        "summary": summarize(items),
        "items": items,
    }
