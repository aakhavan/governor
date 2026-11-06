"""Certified-answer evaluation: ask's certified path against the shop golden set (batch2b.md section 15).

::

    python -m governor.eval.certified_eval --set <questions.yaml> --role analyst --out <report.json>
        [--llm fake:<script.json>|openrouter]

Each question goes through ``governor.ask.certified.answer`` once. Per question the report holds the outcome, the
value and whether it passed:

* the outcome must equal the expected outcome;
* an ``answer`` must carry a value within ``tol`` of ``expected`` (and, with ``expected_period``, name that period);
* a ``not_available`` with a ``kpi`` must name that KPI.

The summary gives outcome accuracy over all questions, value accuracy over the answerable ones, and the cost
(OpenRouter's billed cost per call; ``cost_unknown`` counts calls that reported none). The set file is read as is;
this module never writes it.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

import yaml

from governor.ask import certified
from governor.core.llm import usage_from_message

KIND = "certified_eval"
OUTCOMES = ("answer", "not_available", "unanswerable", "refused")


# --------------------------------------------------------------------------- metered LLM


class MeteredLLM:
    """Wraps a chat model and records the tokens and billed cost of every response."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm
        self.usage: list[dict] = []

    def _record(self, message: Any) -> None:
        if message is not None:
            self.usage.append(usage_from_message(message))

    def invoke(self, prompt: Any, **kw: Any) -> Any:
        message = self.llm.invoke(prompt, **kw)
        self._record(message)
        return message

    def __getattr__(self, name: str) -> Any:
        if name == "with_structured_output" and hasattr(self.llm, name):
            def structured(*args: Any, **kw: Any) -> Any:
                return _MeteredRunnable(self, self.llm.with_structured_output(*args, **kw))
            return structured
        raise AttributeError(name)

    def model_name(self) -> str:
        for attr in ("model_name", "model"):
            value = getattr(self.llm, attr, None)
            if isinstance(value, str) and value:
                return value
        return type(self.llm).__name__


class _MeteredRunnable:
    def __init__(self, meter: MeteredLLM, runnable: Any) -> None:
        self.meter, self.runnable = meter, runnable

    def invoke(self, prompt: Any, **kw: Any) -> Any:
        out = self.runnable.invoke(prompt, **kw)
        self.meter._record(out.get("raw") if isinstance(out, dict) else None)
        return out


def make_metered(spec: str | None) -> tuple[MeteredLLM, str]:
    """``(llm, llm label)`` for ``--llm``; openrouter builds the real chat model once."""
    spec = (spec or "openrouter").strip()
    llm = certified.make_llm(spec)
    if llm is None:
        from governor.core.llm import get_chat_model

        llm = get_chat_model(temperature=0)
    return MeteredLLM(llm), ("fake" if spec.startswith("fake") else spec)


def cost_of(usage: list[dict]) -> tuple[float | None, int]:
    """``(known cost, calls without a cost)``; the cost is None when no call reported one."""
    known = [u["cost_usd"] for u in usage if u.get("cost_usd") is not None]
    return (round(sum(known), 6) if known else None), sum(u.get("cost_usd") is None for u in usage)


# --------------------------------------------------------------------------- set and scoring


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load_set(path: str | Path, key: str) -> list[dict]:
    doc = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    items = doc.get(key) or []
    if not isinstance(items, list) or not all(isinstance(i, dict) and i.get("id") and i.get("question")
                                              for i in items):
        raise ValueError(f"{path}: '{key}' must be a list of items with id and question")
    return items


def score(question: dict, result: dict) -> dict:
    """Score one answer against its expected outcome; returns the per-question fields."""
    expected = question.get("outcome")
    outcome = result.get("outcome")
    value = result.get("value")
    outcome_ok = outcome == expected
    value_ok: bool | None = None
    reasons: list[str] = []
    if not outcome_ok:
        reasons.append(f"outcome {outcome}, expected {expected}")
    if expected == "answer":
        target, tol = question.get("expected"), float(question.get("tol") or 0)
        value_ok = (outcome == "answer" and isinstance(value, (int, float)) and target is not None
                    and abs(float(value) - float(target)) <= tol + 1e-9)
        if outcome == "answer" and not value_ok:
            reasons.append(f"value {value}, expected {target} +/- {tol}")
        period = question.get("expected_period")
        if period and outcome == "answer" and str(period) not in (result.get("text") or ""):
            value_ok = False
            reasons.append(f"period {period} not named")
    kpi_ok: bool | None = None
    if question.get("kpi"):
        kpi_ok = result.get("kpi_id") == question["kpi"]
    passed = outcome_ok and (value_ok is not False)
    if expected == "not_available" and kpi_ok is False:
        passed = False
        reasons.append(f"kpi {result.get('kpi_id')}, expected {question['kpi']}")
    return {"outcome_ok": outcome_ok, "value_ok": value_ok, "kpi_ok": kpi_ok, "pass": passed,
            "reason": "; ".join(reasons) or None}


def _rate(flags: list[bool]) -> float | None:
    return round(sum(flags) / len(flags), 6) if flags else None


def summarise(items: list[dict], cost_unknown: int, total_cost: float | None) -> dict:
    answerable = [i for i in items if i["expected_outcome"] == "answer"]
    confusion: dict[str, dict[str, int]] = {}
    for i in items:
        row = confusion.setdefault(i["expected_outcome"] or "?", {})
        row[i["outcome"]] = row.get(i["outcome"], 0) + 1
    return {
        "questions": len(items),
        "passed": sum(i["pass"] for i in items),
        "outcome_correct": sum(i["outcome_ok"] for i in items),
        "outcome_accuracy": _rate([i["outcome_ok"] for i in items]),
        "answerable": len(answerable),
        "value_correct": sum(bool(i["value_ok"]) for i in answerable),
        "value_accuracy": _rate([bool(i["value_ok"]) for i in answerable]),
        "confusion": confusion,
        "errors": sum(i["outcome"] == "error" for i in items),
        "cost_usd": total_cost,
        "cost_unknown_calls": cost_unknown,
    }


# --------------------------------------------------------------------------- run


Answerer = Callable[[str], dict]


def ask_one(question: str, role: str, llm: Any, adapter: Any) -> dict:
    """One certified answer as a plain dict; a broken run is outcome ``error`` (the loop goes on)."""
    try:
        return certified.answer(question, role, llm, adapter).model_dump(mode="json")
    except Exception as error:  # noqa: BLE001
        return {"outcome": "error", "text": f"{type(error).__name__}: {str(error).splitlines()[0][:300]}",
                "value": None, "kpi_id": None, "sql": None, "citation": None}


def evaluate(set_path: str | Path, role: str, answerer: Answerer, meter: MeteredLLM | None = None, *,
             llm_label: str = "", raw: Any = None) -> dict:
    """Run every question through ``answerer`` and return the report; with ``raw`` (person-level values, as the
    red team samples them) every string in it is redacted against them."""
    questions = load_set(set_path, "questions")
    items: list[dict] = []
    for q in questions:
        before = len(meter.usage) if meter else 0
        t0 = time.perf_counter()
        result = answerer(str(q["question"]))
        cost, unknown = cost_of(meter.usage[before:]) if meter else (None, 0)
        items.append({
            "id": q["id"], "question": q["question"], "expected_outcome": q.get("outcome"),
            "expected_kpi": q.get("kpi"), "expected": q.get("expected"), "tol": q.get("tol"),
            "outcome": result.get("outcome"), "value": result.get("value"), "kpi_id": result.get("kpi_id"),
            "text": result.get("text"), "sql": result.get("sql"),
            **score(q, result),
            "cost_usd": cost, "cost_unknown_calls": unknown, "seconds": round(time.perf_counter() - t0, 2),
        })
    total, unknown = cost_of(meter.usage) if meter else (None, 0)
    report = {
        "kind": KIND,
        "set_file": str(set_path),
        "set_sha256": file_sha256(set_path),
        "role": role,
        "llm": llm_label,
        "model": meter.model_name() if meter else None,
        "items": items,
        "summary": summarise(items, unknown, total),
        "total_cost_usd": total,
    }
    if raw is None:
        return report
    from governor.eval.redteam import redact_report  # redteam imports this module; import late

    return redact_report(report, raw)


def write_report(report: dict, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m governor.eval.certified_eval")
    ap.add_argument("--set", required=True, type=Path, dest="set_path")
    ap.add_argument("--role", default="analyst", choices=sorted(certified.READER_ROLES))
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--llm", default="openrouter", help="openrouter or fake:<script.json>")
    args = ap.parse_args(argv)
    adapter = None
    try:
        meter, label = make_metered(args.llm)
        adapter = certified.default_adapter()
        from governor.eval.redteam import sample_raw

        raw = sample_raw()
        report = evaluate(args.set_path, args.role, lambda q: ask_one(q, args.role, meter, adapter), meter,
                          llm_label=label, raw=raw)
    except Exception as error:  # noqa: BLE001
        print(f"certified eval failed: {type(error).__name__}: {str(error).splitlines()[0][:300]}", file=sys.stderr)
        return 1
    finally:
        if adapter is not None:
            adapter.close()
    write_report(report, args.out)
    s = report["summary"]
    print(json.dumps({"out": str(args.out), "questions": s["questions"], "passed": s["passed"],
                      "outcome_accuracy": s["outcome_accuracy"], "value_accuracy": s["value_accuracy"],
                      "cost_usd": s["cost_usd"]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
