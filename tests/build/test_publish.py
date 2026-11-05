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
