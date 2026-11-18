"""Publish a built project as a pull request branch (batch2b section 13).

``publish(target, open_pr=False)`` after a ``built`` run (``governor/build.json``):

- makes ``<target>`` a git repo if it is not one, and makes a first commit on ``main`` when the repo has none yet
  (the scaffold: ``dbt_project.yml``, ``profiles/profiles.yml``, ``models/sources.yml`` and a ``.gitignore`` with
  ``target/``, ``logs/``, ``dbt_packages/``);
- with an ``origin`` that has ``main``: fetches it, fast-forwards a local ``main`` that is behind, refuses one that
  has diverged (batch3 section 30.1);
- creates branch ``governor/build-<id8>`` from ``main``, writes ``governor/pr.md`` and commits the generated
  ``models/``, ``tests/`` and ``governor/`` files as ``governor <governor@localhost>`` with the message
  ``governor: build <id8> (<n> KPIs, <m> gaps)``; when the staged files match ``main`` there is no commit: the branch
  is deleted, the target goes back to ``main`` and the result is ``nothing_to_publish`` (batch3 section 30.2);
- pushes the branch (and ``main`` when the remote has none) when ``origin`` exists; with ``open_pr`` runs
  ``gh pr create``.

The published commit is recorded inside the git directory (``.git/governor_published.json``), not in the tree, so
``certify`` can check that it reached ``main`` while the working tree stays clean. The working tree is left on the
new branch.
"""

from __future__ import annotations

import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

import yaml

from governor.build.events import emit

GOVERNOR = ("governor", "governor@localhost")
MAIN = "main"
GITIGNORE = "target/\nlogs/\ndbt_packages/\nprofiles/.user.yml\n"
SCAFFOLD = (".gitignore", "dbt_project.yml", "profiles/profiles.yml", "models/sources.yml")
# governor/ already covers it; named so the fingerprint written at approval (batch3.md section 28) is always committed.
GENERATED = ("models", "tests", "governor", "governor/profile_fingerprint.json")
PUBLISHED_FILE = "governor_published.json"


class PublishError(RuntimeError):
    """A git or gh step failed; the message is one readable line."""


# --------------------------------------------------------------------------- git


def _git_env() -> dict[str, str]:
    env = dict(os.environ)
    env.update({"GIT_AUTHOR_NAME": GOVERNOR[0], "GIT_AUTHOR_EMAIL": GOVERNOR[1],
                "GIT_COMMITTER_NAME": GOVERNOR[0], "GIT_COMMITTER_EMAIL": GOVERNOR[1],
                "GIT_TERMINAL_PROMPT": "0"})
    return env


def git(target: Path, *args: str, check: bool = True, timeout: int = 300) -> subprocess.CompletedProcess:
    proc = subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True, encoding="utf-8",
                          errors="replace", timeout=timeout, env=_git_env())
    if check and proc.returncode != 0:
        first = ((proc.stderr or proc.stdout or "").strip().splitlines() or [""])[-1]
        raise PublishError(f"git {args[0]} failed: {first[:300]}")
    return proc


def _is_own_repo(target: Path) -> bool:
    proc = git(target, "rev-parse", "--show-toplevel", check=False)
    return proc.returncode == 0 and Path(proc.stdout.strip()).resolve() == target.resolve()


def _has_commits(target: Path) -> bool:
    return git(target, "rev-parse", "--verify", "--quiet", "HEAD", check=False).returncode == 0


def _has_remote(target: Path, name: str = "origin") -> bool:
    return git(target, "remote", "get-url", name, check=False).returncode == 0


def published_path(target: Path) -> Path:
    rel = git(target, "rev-parse", "--git-path", PUBLISHED_FILE).stdout.strip()
    path = Path(rel)
    return path if path.is_absolute() else Path(target) / path


def read_published(target: Path) -> dict | None:
    try:
        path = published_path(Path(target))
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None
    except (PublishError, OSError, ValueError):
        return None


def ensure_repo(target: Path) -> bool:
    """git init (branch main) when the target is not its own repo; the scaffold commit when it has none.
    Returns True when the scaffold commit was made."""
    if not _is_own_repo(target):
        git(target, "init", "-b", MAIN)
    if _has_commits(target):
        return False
    gi = target / ".gitignore"
    if not gi.is_file():
        gi.write_text(GITIGNORE, encoding="utf-8")
    git(target, "symbolic-ref", "HEAD", f"refs/heads/{MAIN}")
    git(target, "add", "--", *[p for p in SCAFFOLD if (target / p).exists()])
    git(target, "commit", "-m", "governor: scaffold")
    return True


def ensure_on_main(target: str | Path) -> str | None:
    """Before a new build: a target that is its own git repo must be on ``main``, because ``publish`` branches
    from ``main`` and git refuses that checkout over the new build's files when the target is still on an earlier
    build's branch. A clean target on another branch is switched to ``main`` (returns the branch it left); one with
    uncommitted changes is refused with a readable :class:`PublishError`. Not a repo, or no commits yet: nothing to do."""
    target = Path(target)
    if not target.is_dir() or not _is_own_repo(target) or not _has_commits(target):
        return None
    branch = git(target, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if branch == MAIN:
        return None
    if git(target, "status", "--porcelain").stdout.strip():
        raise PublishError(f"the target is on branch '{branch}' with uncommitted changes; commit, stash or discard "
                           f"them and switch to '{MAIN}' before a new build")
    git(target, "checkout", MAIN)
    return branch


DIVERGED = "local main has diverged from origin/main; pull and resolve, then publish again"
ORIGIN_MAIN = f"refs/remotes/origin/{MAIN}"


def _generated(path: str) -> bool:
    return any(path == d or path.startswith(d + "/") for d in GENERATED)


def sync_main(target: Path) -> str | None:
    """Before branching (batch3 section 30.1), when the target has an ``origin`` with a ``main``: fetch it; a local
    ``main`` that is only behind is fast-forwarded; one with commits of its own as well is refused with
    :class:`PublishError` (``diverged``) and nothing changes. Returns ``"fast_forwarded"`` or ``None``.

    The fast-forward moves the ``main`` ref without touching the generated files in the working tree (they are the
    new build, and the branch made next stages them over the new ``main``). When ``main`` is checked out, the index
    follows the new ``main`` and the files outside the generated folders that the fast-forward changed are updated
    when the working tree still had them as on the old ``main``."""
    if not _has_remote(target):
        return None
    if not git(target, "ls-remote", "--heads", "origin", MAIN, timeout=120).stdout.strip():
        return None  # an empty origin: publish pushes main itself
    git(target, "fetch", "origin", f"+refs/heads/{MAIN}:{ORIGIN_MAIN}", timeout=600)
    counts = git(target, "rev-list", "--left-right", "--count", f"{MAIN}...{ORIGIN_MAIN}").stdout.split()
    ahead, behind = int(counts[0]), int(counts[1])
    if behind == 0:
        return None
    if ahead > 0:
        raise PublishError(DIVERGED)
    old = git(target, "rev-parse", MAIN).stdout.strip()
    new = git(target, "rev-parse", ORIGIN_MAIN).stdout.strip()
    on_main = git(target, "symbolic-ref", "--quiet", "HEAD", check=False).stdout.strip() == f"refs/heads/{MAIN}"
    if not on_main:
        git(target, "update-ref", f"refs/heads/{MAIN}", new, old)
        return "fast_forwarded"
    changed = [p for p in git(target, "diff", "--name-only", "-z", old, new).stdout.split("\0")
               if p and not _generated(p)]
    clean = [p for p in changed if not git(target, "status", "--porcelain", "--", p).stdout.strip()]
    in_new = set(git(target, "ls-tree", "-r", "-z", "--name-only", new, "--", *clean).stdout.split("\0")) \
        if clean else set()
    git(target, "update-ref", f"refs/heads/{MAIN}", new, old)
    git(target, "reset", "-q")  # index = the new main; the working tree is left as it is
    for p in clean:
        if p in in_new:
            git(target, "checkout", "--", p)
        elif (target / p).is_file():
            (target / p).unlink()
    return "fast_forwarded"


# --------------------------------------------------------------------------- pr.md


def load_build(target: Path) -> dict | None:
    path = Path(target) / "governor" / "build.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def kpi_meta(target: Path) -> dict[str, dict]:
    """kpi_id -> {model, definition, owner, source_tier, source_ref, template_sha256, rendered_sha256, domain}
    from the generated ``models/marts/<domain>/_<domain>.yml`` files."""
    out: dict[str, dict] = {}
    for yml in sorted((Path(target) / "models" / "marts").glob("*/_*.yml")):
        doc = yaml.safe_load(yml.read_text(encoding="utf-8")) or {}
        for m in doc.get("models") or []:
            meta = ((m.get("config") or {}).get("meta")) or m.get("meta") or {}
            if not meta.get("kpi_id"):
                continue
            out[str(meta["kpi_id"])] = {"model": m.get("name"), "definition": m.get("description") or "",
                                        "domain": yml.parent.name, **{k: str(v) for k, v in meta.items()}}
    return out


def _design(target: Path) -> dict:
    path = Path(target) / "governor" / "design.json"
    try:
        return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    except ValueError:
        return {}


def _docs_line(cov: dict | None) -> str:
    """Column-description coverage (batch2c section 16): the reviewer reviews the descriptions with the code."""
    if not isinstance(cov, dict):
        return "- Column descriptions: (not recorded)"
    share = float(cov.get("share") or 0.0)
    return (f"- Column descriptions: {share:.0%} ({cov.get('described', 0)} of {cov.get('columns', 0)} columns; "
            "review them in the yml files)")


def render_pr(target: Path, build: dict, branch: str) -> str:
    target = Path(target)
    id8 = str(build.get("thread_id") or "")[:8]
    kpis = build.get("kpis_built") or []
    gaps = build.get("gaps") or []
    tests = build.get("tests_passed") or {}
    findings = build.get("blueprint") or []
    cost = build.get("cost") or {}
    meta = kpi_meta(target)
    folders = {m.get("name"): m.get("folder") for m in _design(target).get("silver_models") or []}
    silver_models = (build.get("models") or {}).get("silver") or []

    lines = [f"# governor: build {id8}", "",
             "## Summary", "",
             f"governor built this dbt project from the raw schema: {len(silver_models)} silver models, "
             f"{len(kpis)} KPIs and {len(gaps)} gaps. Build thread `{build.get('thread_id')}`, branch `{branch}`.", "",
             f"- Design approved by: **{build.get('approved_by') or '(not recorded)'}**",
             f"- dbt tests passed: {tests.get('total', 0)} (silver {tests.get('silver', 0)}, gold {tests.get('gold', 0)})",
             f"- SQL repairs: {build.get('repairs', 0)}",
             _docs_line(build.get("docs_coverage")), "",
             "## Silver models", ""]
    lines += [f"- `{name}` ({folders.get(name) or 'silver'})" for name in silver_models] or ["(none)"]
    lines += ["", "## KPIs", "", "| KPI | model | domain | owner | source tier | source |", "|---|---|---|---|---|---|"]
    for k in kpis:
        m = meta.get(k.get("id"), {})
        lines.append(f"| {k.get('id')} | `{k.get('model')}` | {k.get('domain')} | {m.get('owner') or '-'} | "
                     f"{m.get('source_tier') or '-'} | {m.get('source_ref') or '-'} |")
    lines += ["", "## Gap report", ""]
    if not gaps:
        lines.append("No KPI was declined.")
    for g in gaps:
        lines += [f"- **{g.get('id')}**: {g.get('reason') or '(no reason given)'}",
                  f"  - missing: {', '.join(g.get('missing') or []) or '(not stated)'}",
                  f"  - typical sources: {', '.join(g.get('typical_sources') or []) or '(not stated)'}",
                  f"  - next step: {g.get('next_step') or '(not stated)'}"]
    lines += ["", "## Tests", "",
              f"dbt build ran every test in the dev schema: {tests.get('total', 0)} passed "
              f"({tests.get('silver', 0)} silver, {tests.get('gold', 0)} gold).", "",
              "## Blueprint findings", ""]
    lines += [f"- {f.get('rule')} ({f.get('severity')}) {f.get('target')}: {f.get('problem')}" for f in findings] \
        or ["No findings."]
    lines += ["", "## Model cost", "",
              f"{cost.get('llm_calls', 0)} model calls, cost "
              + (f"${cost['cost_usd']:.4f}" if isinstance(cost.get("cost_usd"), (int, float)) else "unknown") + "."]
    for model, c in (cost.get("by_model") or {}).items():
        usd = f"${c['cost_usd']:.4f}" if isinstance(c.get("cost_usd"), (int, float)) else "unknown"
        lines.append(f"- `{model}`: {c.get('calls', 0)} calls, {c.get('input_tokens', 0)} in / "
                     f"{c.get('output_tokens', 0)} out tokens, {usd}")
    lines += ["", "## Reviewer checklist", "",
              "- [ ] The silver models read the right raw tables and keys (`governor/design.md`).",
              "- [ ] Every KPI mapping in `governor/approved.yaml` matches the business meaning.",
              "- [ ] The declined KPIs and their next steps in `governor/gaps.md` are right.",
              "- [ ] No PII column reaches a gold model untagged; blueprint findings are acceptable.",
              "- [ ] The dbt tests cover the keys and the KPI grain.",
              "- [ ] After merging, run `python -m governor.build certify --target <dir> --by <name>`.", ""]
    return "\n".join(lines)


# --------------------------------------------------------------------------- publish


def publish(target: str | Path, *, open_pr: bool = False) -> dict:
    started = time.monotonic()
    target = Path(target).resolve()
    build = load_build(target)
    if not build or build.get("status") != "built":
        return {"status": "not_built",
                "reason": f"governor/build.json says {(build or {}).get('status')!r}; publish needs a built run"}
    thread_id = str(build.get("thread_id") or "")
    id8 = thread_id[:8]
    if not id8:
        return {"status": "not_built", "reason": "governor/build.json has no thread_id"}
    branch = f"governor/build-{id8}"
    n_kpis, n_gaps = len(build.get("kpis_built") or []), len(build.get("gaps") or [])

    scaffold = ensure_repo(target)
    sync_main(target)
    git(target, "checkout", "-B", branch, MAIN)
    pr = target / "governor" / "pr.md"
    pr.write_bytes(render_pr(target, build, branch).encode("utf-8"))
    git(target, "add", "-A", "--", *[d for d in GENERATED if (target / d).exists()])
    if git(target, "diff", "--cached", "--quiet", MAIN, "--", check=False).returncode == 0:
        git(target, "checkout", MAIN)
        git(target, "branch", "-D", branch)
        return {"status": "nothing_to_publish", "reason": "the build matches main"}
    message = f"governor: build {id8} ({n_kpis} KPIs, {n_gaps} gaps)"
    git(target, "commit", "-m", message)
    commit = git(target, "rev-parse", "HEAD").stdout.strip()
    published_path(target).write_text(json.dumps({"commit": commit, "branch": branch, "thread_id": thread_id}),
                                      encoding="utf-8")

    pushed = False
    if _has_remote(target):
        git(target, "push", "--set-upstream", "origin", branch, timeout=600)
        if not git(target, "ls-remote", "--heads", "origin", MAIN, timeout=120).stdout.strip():
            git(target, "push", "origin", f"refs/heads/{MAIN}:refs/heads/{MAIN}", timeout=600)
        pushed = True
    pr_url = None
    if open_pr:
        proc = subprocess.run(["gh", "pr", "create", "--base", MAIN, "--head", branch, "--title", message,
                               "--body-file", str(pr)], cwd=str(target), capture_output=True, text=True,
                              encoding="utf-8", errors="replace", timeout=300)
        if proc.returncode != 0:
            first = ((proc.stderr or proc.stdout or "").strip().splitlines() or [""])[-1]
            raise PublishError(f"gh pr create failed: {first[:300]}")
        pr_url = (proc.stdout.strip().splitlines() or [None])[-1]
    out: dict[str, Any] = {"status": "published", "branch": branch, "commit": commit, "pr_url": pr_url}
    emit("published", thread_id=thread_id, branch=branch, commit=commit, kpis=n_kpis, gaps=n_gaps, pushed=pushed,
         pr=bool(pr_url), pr_url=pr_url, scaffold=scaffold, seconds=round(time.monotonic() - started, 1))
    return out


__all__ = ["PublishError", "ensure_on_main", "kpi_meta", "load_build", "publish", "read_published", "render_pr",
           "sync_main"]
