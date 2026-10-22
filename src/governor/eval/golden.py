"""The golden set: question file, tune/holdout split, and the freeze check.

``evaluation/golden/questions.yaml`` holds the questions with their expected
behaviour and gold SQL; ``split.json`` divides the ids into tune and holdout;
``FROZEN.sha256`` pins both files (``sha256sum`` format). Every function takes
an optional directory so tests can point at a fixture.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, time
from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from governor.core import paths

GOLDEN_DIR = paths.ROOT / "evaluation" / "golden"
QUESTIONS_FILE = "questions.yaml"
SPLIT_FILE = "split.json"
FROZEN_FILE = "FROZEN.sha256"
FROZEN_NAMES = (QUESTIONS_FILE, SPLIT_FILE)

Role = Literal["analyst", "finance_admin"]
Category = Literal["simple", "join", "time_grain", "metric", "ambiguous", "policy", "unanswerable"]
Expect = Literal["answer", "clarify", "refuse", "aggregate", "mask", "unanswerable"]
NEEDS_SQL: frozenset[str] = frozenset({"answer", "aggregate", "mask"})


class Question(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    role: Role
    category: Category
    question: str = Field(min_length=1)
    expect: Expect
    gold_sql: str | None = None
    order_matters: bool = False
    rel_tol: float = Field(default=1e-6, ge=0)
    missing_slot: str | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def _consistent(self) -> Question:
        if self.expect in NEEDS_SQL and not self.gold_sql:
            raise ValueError(f"{self.id}: expect={self.expect} needs gold_sql")
        if self.expect not in NEEDS_SQL and self.gold_sql:
            raise ValueError(f"{self.id}: expect={self.expect} must not have gold_sql")
        if self.expect == "clarify" and not self.missing_slot:
            raise ValueError(f"{self.id}: expect=clarify needs missing_slot")
        return self


class GoldenSet(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of: datetime
    questions: list[Question]

    @field_validator("as_of", mode="before")
    @classmethod
    def _date_to_datetime(cls, value: object) -> object:
        if isinstance(value, date) and not isinstance(value, datetime):
            return datetime.combine(value, time())
        return value

    @model_validator(mode="after")
    def _unique_ids(self) -> GoldenSet:
        ids = [q.id for q in self.questions]
        dupes = sorted({i for i in ids if ids.count(i) > 1})
        if dupes:
            raise ValueError(f"duplicate question ids: {dupes}")
        return self

    def by_id(self) -> dict[str, Question]:
        return {q.id: q for q in self.questions}


class Split(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tune: list[str]
    holdout: list[str]

    @model_validator(mode="after")
    def _disjoint(self) -> Split:
        both = sorted(set(self.tune) & set(self.holdout))
        if both:
            raise ValueError(f"ids in both tune and holdout: {both}")
        return self


def load_golden(directory: Path | None = None) -> GoldenSet:
    """Parse and validate ``questions.yaml``."""
    path = (directory or GOLDEN_DIR) / QUESTIONS_FILE
    return GoldenSet.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def load_split(directory: Path | None = None) -> Split:
    """Parse and validate ``split.json``."""
    path = (directory or GOLDEN_DIR) / SPLIT_FILE
    return Split.model_validate(json.loads(path.read_text(encoding="utf-8")))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify_frozen(directory: Path | None = None) -> bool:
    """True when questions.yaml and split.json match FROZEN.sha256. False when any file is missing."""
    folder = directory or GOLDEN_DIR
    frozen = folder / FROZEN_FILE
    if not frozen.is_file():
        return False
    want: dict[str, str] = {}
    for line in frozen.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            want[parts[1].strip().lstrip("*")] = parts[0].strip().lower()
    for name in FROZEN_NAMES:
        path = folder / name
        if not path.is_file() or want.get(name) != _sha256(path):
            return False
    return True
