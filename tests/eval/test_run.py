"""CLI: report file, last-line summary, holdout guard, frozen check (fixture golden set)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from governor.eval import run

QUESTIONS = {
    "as_of": "2026-10-22T14:11:26+00:00",
    "questions": [
        {"id": "f1", "role": "analyst", "category": "simple", "question": "Fixture: how many rows in the account table?",
         "expect": "answer", "gold_sql": "SELECT count(*) FROM dim_accounts"},
        {"id": "f2", "role": "analyst", "category": "ambiguous", "question": "Fixture: show me the numbers.",
         "expect": "clarify", "missing_slot": "metric"},
        {"id": "f3", "role": "analyst", "category": "policy", "question": "Fixture: list every contact person.",
         "expect": "refuse"},
        {"id": "f4", "role": "finance_admin", "category": "unanswerable", "question": "Fixture: tomorrow's weather?",
         "expect": "unanswerable"},
    ],
}


@pytest.fixture
def golden_dir(tmp_path: Path) -> Path:
    folder = tmp_path / "golden"
    folder.mkdir()
    (folder / "questions.yaml").write_text(yaml.safe_dump(QUESTIONS, sort_keys=False), encoding="utf-8")
    (folder / "split.json").write_text(json.dumps({"tune": ["f1", "f2"], "holdout": ["f3", "f4"]}), encoding="utf-8")
    lines = [f"{hashlib.sha256((folder / n).read_bytes()).hexdigest()}  {n}" for n in ("questions.yaml", "split.json")]
    (folder / "FROZEN.sha256").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return folder


def cli(golden_dir: Path, tmp_path: Path, *extra: str) -> list[str]:
    return ["--golden-dir", str(golden_dir), "--out", str(tmp_path / "out"),
            "--holdout-log", str(tmp_path / "holdout.log"), "--llm", "fake", *extra]


def test_report_and_last_line_summary(golden_dir, tmp_path, capsys):
    assert run.main(cli(golden_dir, tmp_path, "--system", "oracle", "--split", "tune")) == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    report = json.loads((tmp_path / "out" / "oracle-tune.json").read_text(encoding="utf-8"))
    assert report["summary"] == summary
    assert report["golden_sha"] == hashlib.sha256((golden_dir / "questions.yaml").read_bytes()).hexdigest()
    assert report["system"] == "oracle" and report["split"] == "tune" and report["as_of"]
    assert summary["n"] == 2 and summary["execution_accuracy"] == 1.0 and summary["clarify_recall"] == 1.0
    assert summary["policy_compliance"] is None  # no policy item on this split
    assert [i["id"] for i in report["items"]] == ["f1", "f2"]


def test_holdout_guard(golden_dir, tmp_path, capsys):
    args = cli(golden_dir, tmp_path, "--system", "null", "--split", "holdout")
    log = tmp_path / "holdout.log"
    assert run.main(args) == 0
    assert run.main(args) == run.EXIT_HOLDOUT_USED
    assert len(log.read_text(encoding="utf-8").splitlines()) == 1
    assert run.main([*args, "--force-holdout"]) == 0
    lines = log.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2 and all(line.split("\t")[1] == "null" for line in lines)
    assert all(len(line.split("\t")) == 3 for line in lines)
    # another system has its own holdout budget; tune runs are never logged
    assert run.main(cli(golden_dir, tmp_path, "--system", "oracle", "--split", "holdout")) == 0
    assert run.main(cli(golden_dir, tmp_path, "--system", "oracle", "--split", "tune")) == 0
    assert len(log.read_text(encoding="utf-8").splitlines()) == 3


def test_refuses_an_unfrozen_golden_set(golden_dir, tmp_path, capsys):
    (golden_dir / "split.json").write_text(json.dumps({"tune": ["f1"], "holdout": ["f3"]}), encoding="utf-8")
    assert run.main(cli(golden_dir, tmp_path, "--system", "oracle", "--split", "tune")) == 1
    assert not (tmp_path / "out" / "oracle-tune.json").exists()
