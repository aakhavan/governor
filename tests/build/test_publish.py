"""Publish (branch, commit, pr.md, push to a local bare repo) and certify's merge check (batch2b section 13).
Offline: the build is the fake-dbt build of the sample design. The live check skips without the database."""
import json
import os
import subprocess

import pytest

from governor.build import certify as cert, graph, publish as pub
from governor.build.llm import FakeBuildLLM
from governor.build.workspace import build_dsn, init_target, write_sources
from test_gold import GOOD_SILVER, FakeDbt  # noqa: E402  (tests/build is on sys.path)

GIT_ID = {"GIT_AUTHOR_NAME": "reviewer", "GIT_AUTHOR_EMAIL": "r@localhost",
          "GIT_COMMITTER_NAME": "reviewer", "GIT_COMMITTER_EMAIL": "r@localhost"}


def git(cwd, *args):
    r = subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, env={**os.environ, **GIT_ID})
    assert r.returncode == 0, r.stderr
    return r.stdout


@pytest.fixture
def built(tmp_path, profile, good):
    dbt = FakeDbt(good)
    kw = {"checkpoints": tmp_path / "cp.sqlite", "dbt_runner": dbt, "inspector": dbt.columns,
          "row_counter": lambda names: {n: 3 for n in names}}
    init_target(tmp_path / "t", "shop")
    write_sources(tmp_path / "t", {"olist_orders_dataset": ["order_id"]})
    out = graph.start(tmp_path / "t", "shop", FakeBuildLLM({"propose": [json.dumps(good)]}), profile=profile, **kw)
    a = graph.approve(out["thread_id"], "amir", FakeBuildLLM({"intermediate": GOOD_SILVER}), **kw)
    assert a["status"] == "built"
    target = tmp_path / "t"
    (target / "target").mkdir(exist_ok=True)
    (target / "target" / "run_results.json").write_text("{}", encoding="utf-8")  # ignored, never committed
    return target, a["thread_id"]


def test_refuses_without_a_built_run(tmp_path):
    (tmp_path / "governor").mkdir()
    (tmp_path / "governor" / "build.json").write_text(json.dumps({"status": "escalated"}), encoding="utf-8")
    assert pub.publish(tmp_path)["status"] == "not_built"
    assert not (tmp_path / ".git").exists()


def test_publish_inits_branches_commits_and_writes_pr(built):
    target, tid = built
    out = pub.publish(target)
    branch = f"governor/build-{tid[:8]}"
    assert out["status"] == "published" and out["branch"] == branch and out["pr_url"] is None
    assert git(target, "log", "--format=%an <%ae>|%s", "-1", branch).strip() == \
        f"governor <governor@localhost>|governor: build {tid[:8]} (8 KPIs, 2 gaps)"
    assert git(target, "rev-parse", branch).strip() == out["commit"]
    main_files = git(target, "ls-tree", "-r", "--name-only", "main").split()
    assert sorted(main_files) == sorted([".gitignore", "dbt_project.yml", "profiles/profiles.yml", "models/sources.yml"])
    files = git(target, "ls-tree", "-r", "--name-only", branch)
    for p in ("models/staging/", "models/marts/", "governor/design.md", "governor/design.json", "governor/pr.md",
              "governor/build.json", "governor/gaps.md", "governor/approved.yaml"):
        assert p in files, p
    assert "target/" not in files
    pr = (target / "governor" / "pr.md").read_text(encoding="utf-8")
    for section in ("## Summary", "## Silver models", "## KPIs", "## Gap report", "## Tests", "## Blueprint findings",
                    "## Model cost", "## Reviewer checklist"):
        assert section in pr, section
    assert "gmv" in pr and "conversion_rate" in pr and "- [ ]" in pr and "**amir**" in pr
    assert "| gmv | `kpi_gmv` |" in pr
    assert pub.read_published(target)["commit"] == out["commit"]
    kinds = [json.loads(line)["kind"] for line in
             (target.parent / "state" / "events.jsonl").read_text(encoding="utf-8").splitlines()]
    assert kinds[-1] == "published" and "built" in kinds


def test_publish_pushes_to_origin(built, tmp_path):
    target, tid = built
    origin = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", "-b", "main", str(origin)], check=True, capture_output=True)
    git(target.parent, "init", "-b", "main", str(target))
    git(target, "remote", "add", "origin", str(origin))
    out = pub.publish(target)
    heads = git(origin, "branch", "--list")
    assert out["branch"] in heads and "main" in heads


def test_next_build_after_publish_starts_on_main(built):
    """8 Nov: publish left the target on the build branch, the next build wrote over it, and the next publish's
    checkout of main aborted. A clean target is switched back to main before a new build."""
    target, tid = built
    out = pub.publish(target)
    assert git(target, "rev-parse", "--abbrev-ref", "HEAD").strip() == out["branch"]
    assert pub.ensure_on_main(target) == out["branch"]
    assert git(target, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    assert pub.ensure_on_main(target) is None  # already on main: nothing to do


def test_new_build_refused_on_a_dirty_build_branch(built):
    target, _ = built
    out = pub.publish(target)
    (target / "governor" / "design.md").write_text("changed", encoding="utf-8")
    with pytest.raises(pub.PublishError, match="uncommitted changes"):
        pub.ensure_on_main(target)
    assert git(target, "rev-parse", "--abbrev-ref", "HEAD").strip() == out["branch"]  # nothing switched


def test_ensure_on_main_ignores_a_target_without_git(tmp_path):
    assert pub.ensure_on_main(tmp_path) is None and not (tmp_path / ".git").exists()


def _events(target):
    return [json.loads(line) for line in
            (target.parent / "state" / "events.jsonl").read_text(encoding="utf-8").splitlines()]


def test_published_event_carries_pr_url(built, monkeypatch):
    target, tid = built
    url = "https://github.com/example/olist-dbt/pull/7"
    real_run = subprocess.run

    def fake_run(cmd, *a, **k):
        if cmd and cmd[0] == "gh":  # no network: gh prints the new pull request's url
            return subprocess.CompletedProcess(cmd, 0, stdout=f"Creating pull request\n{url}\n", stderr="")
        return real_run(cmd, *a, **k)

    monkeypatch.setattr(pub.subprocess, "run", fake_run)
    out = pub.publish(target, open_pr=True)
    assert out["pr_url"] == url
    ev = _events(target)[-1]
    assert ev["kind"] == "published" and ev["pr_url"] == url and ev["pr"] is True and ev["thread_id"] == tid


def test_published_event_pr_url_is_null_without_a_pr(built):
    target, _ = built
    assert pub.publish(target)["pr_url"] is None
    ev = _events(target)[-1]
    assert ev["kind"] == "published" and "pr_url" in ev and ev["pr_url"] is None


def test_certify_refuses_before_the_merge(built):
    target, _ = built
    assert cert.certify(target, "amir", dbt_runner=_no_dbt)["status"] == "not_merged"  # not published yet
    out = pub.publish(target)
    res = cert.certify(target, "amir", dbt_runner=_no_dbt)
    assert res["status"] == "not_merged" and "not main" in res["reason"]
    git(target, "checkout", "main")
    res = cert.certify(target, "amir", dbt_runner=_no_dbt)
    assert res["status"] == "not_merged" and "not merged" in res["reason"]
    git(target, "merge", "--no-ff", "-m", "merge", out["branch"])
    (target / "stray.txt").write_text("x", encoding="utf-8")
    assert "uncommitted" in cert.certify(target, "amir", dbt_runner=_no_dbt)["reason"]
    (target / "stray.txt").unlink()
    assert cert.merge_check(target) == (out["commit"], None)


def test_certify_registry_written_after_serving(built, monkeypatch):
    target, _ = built
    out = pub.publish(target)
    git(target, "checkout", "main")
    git(target, "merge", "--no-ff", "-m", "merge", out["branch"])
    monkeypatch.setenv("GOVERNOR_PG_ADMIN_DSN", "postgresql://unused")
    monkeypatch.delenv("GOVERNOR_PII_SALT", raising=False)
    order = []
    ok = cert.DbtResult(True, 0, [{"unique_id": "model.shop.kpi_gmv", "status": "success"}], "")
    monkeypatch.setattr(cert, "prepare_registry", lambda dsn: order.append("prepare") or "env")
    monkeypatch.setattr(cert, "write_registry",
                        lambda *a, **kw: order.append("write") or ([{"kpi_id": "gmv"}], []))

    def failing_serve(dsn):
        order.append("serve")
        raise RuntimeError("serving failed")

    monkeypatch.setattr(cert, "serve", failing_serve)
    with pytest.raises(RuntimeError, match="serving failed"):
        cert.certify(target, "amir", dbt_runner=lambda *a, **kw: ok)
    assert order == ["prepare", "serve"]  # nothing certified when serving fails
    monkeypatch.setattr(cert, "serve", lambda dsn: order.append("serve") or {"views": 2})
    order.clear()
    assert cert.certify(target, "amir", dbt_runner=lambda *a, **kw: ok)["status"] == "certified"
    assert order == ["prepare", "serve", "write"]


def test_empty_salt_rejected_early(built, monkeypatch):
    target, _ = built
    monkeypatch.setenv("GOVERNOR_PII_SALT", "")
    with pytest.raises(cert.CertifyError, match="GOVERNOR_PII_SALT"):
        cert.certify(target, "amir", dbt_runner=_no_dbt)


def _no_dbt(*a, **kw):
    raise AssertionError("dbt must not run before the merge")


def test_profiles_has_prod_target_without_a_password(tmp_path):
    init_target(tmp_path, "shop")
    text = (tmp_path / "profiles" / "profiles.yml").read_text(encoding="utf-8")
    assert "    prod:" in text and "schema: analytics" in text and "GOVERNOR_DEPLOY_PASSWORD') }}" in text
    assert "governor_deploy_local" not in text
    old = tmp_path / "old"
    (old / "profiles").mkdir(parents=True)
    (old / "profiles" / "profiles.yml").write_text(text.split("    prod:")[0], encoding="utf-8")
    init_target(old, "shop")
    assert (old / "profiles" / "profiles.yml").read_text(encoding="utf-8").count("    prod:") == 1


# ---- live ----

def _deploy_up() -> bool:
    if not os.environ.get("GOVERNOR_PG_ADMIN_DSN"):
        return False
    try:
        import psycopg

        with psycopg.connect(build_dsn(), connect_timeout=3), \
                psycopg.connect(os.environ["GOVERNOR_PG_ADMIN_DSN"], connect_timeout=3) as a:
            return bool(a.execute("select 1 from pg_roles where rolname = 'governor_deploy'").fetchone())
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _deploy_up(), reason="needs the test-bed database with roles applied")
def test_live_deploy_role_creates_only_in_analytics():
    import psycopg

    with psycopg.connect(os.environ["GOVERNOR_PG_ADMIN_DSN"]) as a:
        rows = dict(a.execute(
            "select n.nspname, has_schema_privilege('governor_deploy', n.oid, 'CREATE') from pg_namespace n "
            "where n.nspname in ('analytics', 'raw', 'dev_governor', 'public', 'private')").fetchall())
    assert rows.get("analytics") is True
    assert not any(v for k, v in rows.items() if k != "analytics")
