"""Golden file models, loaders and the freeze check, on a fixture of our own."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime

import pytest
import yaml
from pydantic import ValidationError

from governor.eval import golden
from governor.eval.golden import GoldenSet, Question, Split, load_golden, load_split, verify_frozen

FIXTURE = {
    "as_of": "2030-01-15T09:00:00+00:00",
    "questions": [
        {
            "id": "t01",
            "role": "analyst",
            "category": "simple",
            "question": "How many widgets are there?",
            "expect": "answer",
            "gold_sql": "SELECT 1 AS n",
        },
        {
            "id": "t02",
            "role": "analyst",
            "category": "ambiguous",
            "question": "How are we doing?",
            "expect": "clarify",
            "missing_slot": "metric",
        },
        {
            "id": "t03",
            "role": "finance_admin",
            "category": "policy",
            "question": "Show me the phone numbers.",
            "expect": "mask",
            "gold_sql": "SELECT 'x' AS phone",
            "order_matters": True,
            "rel_tol": 0.01,
            "notes": "fixture only",
        },
        {
            "id": "t04",
            "role": "analyst",
            "category": "unanswerable",
            "question": "What will the weather be?",
            "expect": "unanswerable",
        },
    ],
}
SPLIT = {"tune": ["t01", "t02"], "holdout": ["t03", "t04"]}


def _write(folder, questions=FIXTURE, split=SPLIT, frozen=True):
    (folder / "questions.yaml").write_text(yaml.safe_dump(questions, sort_keys=False), encoding="utf-8")
    (folder / "split.json").write_text(json.dumps(split), encoding="utf-8")
    if frozen:
        lines = [
            f"{hashlib.sha256((folder / name).read_bytes()).hexdigest()}  {name}"
            for name in ("questions.yaml", "split.json")
        ]
        (folder / "FROZEN.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")


def test_load_fixture(tmp_path):
    _write(tmp_path)
    doc = load_golden(tmp_path)
    assert isinstance(doc, GoldenSet)
    assert doc.as_of == datetime.fromisoformat(FIXTURE["as_of"])
    assert [q.id for q in doc.questions] == ["t01", "t02", "t03", "t04"]
    first, third = doc.by_id()["t01"], doc.by_id()["t03"]
    assert first.order_matters is False and first.rel_tol == 1e-6 and first.missing_slot is None
    assert third.order_matters is True and third.rel_tol == 0.01
    split = load_split(tmp_path)
    assert split.tune == ["t01", "t02"] and split.holdout == ["t03", "t04"]


def test_as_of_date_only(tmp_path):
    _write(tmp_path, questions={**FIXTURE, "as_of": "2030-01-15"})
    assert load_golden(tmp_path).as_of == datetime(2030, 1, 15)


def _question(**overrides):
    return {**FIXTURE["questions"][0], **overrides}


@pytest.mark.parametrize(
    "overrides",
    [
        {"role": "admin"},
        {"category": "trivia"},
        {"expect": "maybe"},
        {"gold_sql": None},  # answer without gold SQL
        {"expect": "refuse"},  # refuse with gold SQL
        {"expect": "clarify", "gold_sql": None},  # clarify without missing_slot
        {"rel_tol": -0.1},
        {"surprise": 1},
        {"question": ""},
    ],
)
def test_question_rejects(overrides):
    with pytest.raises(ValidationError):
        Question.model_validate(_question(**overrides))


def test_duplicate_ids_rejected():
    with pytest.raises(ValidationError, match="duplicate"):
        GoldenSet.model_validate({**FIXTURE, "questions": [_question(), _question()]})


def test_split_must_be_disjoint():
    with pytest.raises(ValidationError, match="both"):
        Split.model_validate({"tune": ["a", "b"], "holdout": ["b"]})


def test_verify_frozen_true_when_hashes_match(tmp_path):
    _write(tmp_path)
    assert verify_frozen(tmp_path) is True


def test_verify_frozen_false_after_edit(tmp_path):
    _write(tmp_path)
    (tmp_path / "split.json").write_text(json.dumps({"tune": ["t01"], "holdout": ["t02"]}), encoding="utf-8")
    assert verify_frozen(tmp_path) is False


@pytest.mark.parametrize("missing", ["questions.yaml", "split.json", "FROZEN.sha256"])
def test_verify_frozen_false_on_missing_file(tmp_path, missing):
    _write(tmp_path)
    (tmp_path / missing).unlink()
    assert verify_frozen(tmp_path) is False


def test_verify_frozen_false_on_empty_dir(tmp_path):
    assert verify_frozen(tmp_path) is False
    assert verify_frozen(tmp_path / "nope") is False


def test_default_dir_is_repo_golden():
    assert golden.GOLDEN_DIR.parts[-2:] == ("evaluation", "golden")
