"""Helpers for the batch 2b (D6-D8) acceptance scripts: a built, published, merged and certified sample. Stdlib only."""
from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

from _common import check, run, tail
import _testbed as tb
import _build as bd

GIT_ID = {"GIT_AUTHOR_NAME": "accept-reviewer", "GIT_AUTHOR_EMAIL": "accept@localhost",
          "GIT_COMMITTER_NAME": "accept-reviewer", "GIT_COMMITTER_EMAIL": "accept@localhost"}
DEPLOY_PW = os.environ.get("GOVERNOR_DEPLOY_PASSWORD", "governor_deploy_local")


def env(state_dir: Path) -> dict:
    e = bd.env(state_dir)
    e.update(GIT_ID)
    e.update({"GOVERNOR_DEPLOY_USER": "governor_deploy", "GOVERNOR_DEPLOY_PASSWORD": DEPLOY_PW})
    return e


def git(target: Path, *args: str, e: dict):
    return run(["git", "-C", str(target), *args], timeout=120, env=e)


def built_sample(work: Path, e: dict) -> Path | None:
    design, silver = bd.fixture("sample_design.json"), bd.fixture("sample_silver.json")
    if not check("sample design and silver fixtures exist", design is not None and isinstance(silver, dict), ""):
        return None
    target = bd.init_target(work, e)
    if target is None:
        return None
    s = bd.script(work / "s.json", propose=[json.dumps(design)], **silver)
    d, err = bd.cli(["run", "--target", str(target), "--project-name", "shop", "--llm", s], e)
    if not check("sample run pauses at the design gate", d is not None and d.get("thread_id"), err or str(d)):
        return None
    d2, err2 = bd.cli(["approve", d["thread_id"], "--by", "amir", "--llm", s], e, timeout=2400)
    if not check("sample build completes", d2 is not None and d2.get("status") == "built", err2 or str(d2)[:200]):
        return None
    return target


def published_sample(work: Path, e: dict) -> tuple[Path, str] | None:
    target = built_sample(work, e)
    if target is None:
        return None
    origin = work / "origin.git"
    run(["git", "init", "--bare", "-b", "main", str(origin)], timeout=60, env=e)
    d, err = bd.cli(["publish", "--target", str(target)], e)
    if not check("publish creates a branch and commit", d is not None and d.get("status") == "published" and d.get("branch"), err or str(d)):
        return None
    return target, d["branch"]


def merge(target: Path, branch: str, e: dict) -> bool:
    r1 = git(target, "checkout", "main", e=e)
    r2 = git(target, "merge", "--no-ff", "-m", f"Merge {branch} (accept reviewer)", branch, e=e)
    return check("reviewer merges the pull request branch locally", r1.returncode == 0 and r2.returncode == 0, tail(r2))


def certified_sample(work: Path, e: dict) -> Path | None:
    pub = published_sample(work, e)
    if pub is None:
        return None
    target, branch = pub
    if not merge(target, branch, e):
        return None
    d, err = bd.cli(["certify", "--target", str(target), "--by", "amir"], e, timeout=2400)
    if not check("certify deploys to analytics", d is not None and d.get("status") == "certified", err or str(d)[:200]):
        return None
    return target
