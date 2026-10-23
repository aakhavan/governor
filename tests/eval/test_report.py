"""eval_report.md rendering: numbers from the JSONs, failure classes, annotations, losses (fixture reports)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from governor.eval import report
from governor.eval.harness import summarize


def item(id_, category, expect, behaviour, correct, reason="", leak=False, role="analyst"):
    return {"id": id_, "category": category, "role": role, "expect": expect, "behaviour": behaviour,
            "correct": correct, "sql": "SELECT 1" if behaviour == "answer" else None, "leak": leak,
            "cost_usd": 0.01, "latency_s": 1.0, "sql_valid_first": True if behaviour == "answer" else None,
            "sql_valid_final": True if behaviour == "answer" else None, "reason": reason}


def make(system, split, items):
    return {"system": system, "split": split, "golden_sha": "f" * 64, "as_of": "2026-10-22T14:11:26+00:00",
            "llm": "fake", "summary": summarize(items), "items": items}


AGENT_HOLDOUT = [
    item("x1", "simple", "answer", "answer", True, "equal"),
    item("x2", "join", "answer", "answer", False, "column count differs: gold 1, pred 2"),
    item("x3", "ambiguous", "clarify", "answer", False, "behaviour answer, expected clarify"),
    item("x4", "simple", "answer", "clarify", False, "behaviour clarify, expected an answer"),
    item("x5", "time_grain", "answer", "answer", False, "row count differs: gold 8, pred 12"),
]
BASELINE_HOLDOUT = [
    item("x1", "simple", "answer", "answer", True, "equal"),
    item("x2", "join", "answer", "answer", True, "equal"),
    item("x3", "ambiguous", "clarify", "answer", False, "behaviour answer, expected clarify"),
    item("x4", "simple", "answer", "answer", True, "equal"),
    item("x5", "policy", "refuse", "answer", False, "behaviour answer, expected refuse", leak=True),
]
TUNE = [item("t1", "simple", "answer", "answer", True, "equal")]


@pytest.fixture
def reports_dir(tmp_path: Path) -> Path:
    data = {("baseline", "tune"): TUNE, ("agent", "tune"): TUNE,
            ("baseline", "holdout"): BASELINE_HOLDOUT, ("agent", "holdout"): AGENT_HOLDOUT}
    for (system, split), items in data.items():
        (tmp_path / f"{system}-{split}.json").write_text(json.dumps(make(system, split, items)), encoding="utf-8")
    return tmp_path


def test_classify_rules():
    by_id = {i["id"]: report.classify(i) for i in AGENT_HOLDOUT if not i["correct"]}
    assert by_id == {"x2": "wrong grain", "x3": "missed clarification", "x4": "over-clarification",
                     "x5": "wrong filter"}
    assert report.classify(BASELINE_HOLDOUT[4]) == "policy"


def test_fmt_three_decimals_and_null():
    assert report.fmt(0.7) == "0.700"
    assert report.fmt(None) == "-"
    assert report.fmt(False) == "false"


def test_annotation_overrides_class_and_note():
    fails = report.failures(make("agent", "holdout", AGENT_HOLDOUT), {"x5": {"class": "other", "note": "zero fill"}})
    x5 = next(f for f in fails if f["id"] == "x5")
    assert (x5["class"], x5["note"]) == ("other", "zero fill")


def test_unknown_annotation_class_is_an_error():
    with pytest.raises(ValueError):
        report.failures(make("agent", "holdout", AGENT_HOLDOUT), {"x2": {"class": "bad luck"}})


def test_main_writes_numbers_from_the_json_and_names_losses(reports_dir: Path, tmp_path: Path):
    out = tmp_path / "eval_report.md"
    assert report.main(["--reports", str(reports_dir), "--out", str(out), "--holdout-log", str(tmp_path / "none")]) == 0
    text = out.read_text(encoding="utf-8")
    agent = json.loads((reports_dir / "agent-holdout.json").read_text(encoding="utf-8"))["summary"]
    assert f"{agent['execution_accuracy']:.3f}" in text
    assert "Agent loses to the baseline on holdout: join (0/1 vs 1/1), simple (1/2 vs 2/2)" in text
    for line in ("`x2` (join, analyst), wrong grain", "`x3` (ambiguous, analyst), missed clarification",
                 "`x4` (simple, analyst), over-clarification"):
        assert line in text


def test_missing_report_fails(reports_dir: Path, tmp_path: Path):
    (reports_dir / "agent-tune.json").unlink()
    with pytest.raises(FileNotFoundError):
        report.main(["--reports", str(reports_dir), "--out", str(tmp_path / "r.md")])
