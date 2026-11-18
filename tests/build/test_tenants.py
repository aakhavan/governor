"""Tenants in the build (batch3.md sections 31.2 and 31.3), offline: two tenants in tmp_path with copied knowledge
and different KPI ids, the fake build LLM, a fake profiler and no Postgres."""
import json
import os
import re
import shutil
from pathlib import Path

import pytest
from psycopg.conninfo import conninfo_to_dict

from governor.build import __main__ as cli
from governor.build import certify as cert
from governor.build import graph
from governor.build.llm import FakeBuildLLM
from governor.core import paths
from governor.core.catalogue import load_kpis
from governor.core.tenancy import load_tenants

ROOT = Path(__file__).resolve().parents[2]
PREFIX = {"alpha": "aaa_", "beta": "bbb_"}
REGISTRY = """\
tenants:
  alpha: {root: roots/alpha, target: targets/alpha, pg_host: db-alpha, pg_port: 55441, pg_db: shop_alpha}
  beta: {root: roots/beta, target: targets/beta, pg_host: db-beta, pg_port: 55442, pg_db: shop_beta}
"""


def _knowledge(dest: Path, prefix: str) -> None:
    """The repo's knowledge folder, with every KPI id given the tenant's prefix."""
    shutil.copytree(ROOT / "knowledge", dest / "knowledge")
    kpis = dest / "knowledge" / "kpis.yaml"
    kpis.write_text(re.sub(r"(?m)^(\s*- id: )(\w+)", rf"\g<1>{prefix}\g<2>", kpis.read_text(encoding="utf-8")),
                    encoding="utf-8")


@pytest.fixture
def tenants(tmp_path, monkeypatch):
    for name, prefix in PREFIX.items():
        _knowledge(tmp_path / "roots" / name, prefix)
    reg = tmp_path / "tenants.yaml"
    reg.write_text(REGISTRY, encoding="utf-8")
    monkeypatch.setenv("GOVERNOR_TENANTS", str(reg))
    return load_tenants(reg)


def _design(good: dict, prefix: str) -> dict:
    """The sample design with the tenant's KPI ids."""
    out = json.loads(json.dumps(good))
    for k in out["kpis"]:
        k["id"] = prefix + k["id"]
    return out


def _llm(*replies: dict) -> FakeBuildLLM:
    return FakeBuildLLM({"propose": [json.dumps(r) for r in replies]})


def _no_dbt(target, args, **kw):
    raise AssertionError("dbt must not run")


def _ids(text: str, prefix: str) -> set[str]:
    return set(re.findall(rf"\b{prefix}\w+", text))


def test_run_for_tenant_uses_only_its_knowledge(tenants, tmp_path, profile, good):
    for name, other in (("alpha", "beta"), ("beta", "alpha")):
        t = tenants[name]
        other_done = (tenants[other].target / "governor" / "design.md").exists()
        llm = _llm(_design(good, PREFIX[name]))
        out = graph.start(t.target, name, llm, profile=profile, tenant=t, dbt_runner=_no_dbt)
        assert out["status"] == graph.AWAITING, out
        prompt = llm.prompts[0][1]
        assert _ids(prompt, PREFIX[name]), f"{name}'s KPI ids are missing from its planner prompt"
        assert not _ids(prompt, PREFIX[other]), f"{other}'s KPI ids leaked into {name}'s planner prompt"
        assert not re.search(r"\bgmv\b", prompt)  # nor the repo's own catalogue
        assert (t.target / "governor" / "design.md").is_file()
        assert (tenants[other].target / "governor" / "design.md").exists() == other_done  # other's target untouched


def test_run_for_tenant_profiles_its_own_database(tenants, profile, good, monkeypatch):
    from governor.build import profile as profiling

    seen: list[tuple[str, str, dict]] = []

    def fake_profile_schema(dsn, schema, policy=None):
        seen.append((dsn, schema, policy))
        return json.loads(json.dumps(profile))

    monkeypatch.setattr(profiling, "profile_schema", fake_profile_schema)
    for k, v in {"GOVERNOR_PG_HOST": "db-wrong", "GOVERNOR_PG_PORT": "1", "GOVERNOR_PG_DB": "wrong"}.items():
        monkeypatch.setenv(k, v)
    before = dict(os.environ)
    t = tenants["alpha"]
    out = graph.start(t.target, "alpha", _llm(_design(good, "aaa_")), tenant=t, dbt_runner=_no_dbt)
    assert out["status"] == graph.AWAITING
    assert len(seen) == 1
    info = conninfo_to_dict(seen[0][0])
    assert (info["host"], info["port"], info["dbname"]) == ("db-alpha", "55441", "shop_alpha")
    assert seen[0][1] == "raw" and seen[0][2]  # the tenant's policy file was read
    assert dict(os.environ) == before  # nothing process-wide changed

    # silver, gold and dbt are bound to the same database
    kwargs = graph.tenant_graph_kwargs(t)
    for key in ("inspector", "row_counter"):
        info = conninfo_to_dict(kwargs[key].keywords["dsn"])
        assert (info["host"], info["port"], info["dbname"]) == ("db-alpha", "55441", "shop_alpha")
    assert kwargs["kpis_path"] == t.kpis_path and kwargs["blueprint_path"] == t.blueprint_path
    assert kwargs["default_approved"] == t.approved_default
    env = kwargs["dbt_runner"].keywords["env"]
    assert (env["GOVERNOR_PG_HOST"], env["GOVERNOR_PG_PORT"], env["GOVERNOR_PG_DB"]) == ("db-alpha", "55441",
                                                                                        "shop_alpha")


def test_tenant_checkpoints_are_separate(tenants, profile, good):
    a, b = tenants["alpha"], tenants["beta"]
    out = graph.start(a.target, "alpha", _llm(_design(good, "aaa_")), profile=profile, tenant=a, dbt_runner=_no_dbt)
    tid = out["thread_id"]
    assert out["status"] == graph.AWAITING and a.checkpoints.is_file()
    for kw in ({"tenant": b}, {}):  # unknown to beta, and to the no-tenant state folder
        with pytest.raises(graph.BuildError, match="unknown build thread"):
            graph.approve(tid, "Reviewer", _llm(), dbt_runner=_no_dbt, **kw)
    with pytest.raises(graph.BuildError, match="is not the target of tenant beta"):
        graph.start(a.target, "alpha", _llm(), profile=profile, tenant=b)
    # alpha resumes its own thread, from its own checkpoints, with its own catalogue
    llm = _llm(_design(good, "aaa_"))
    again = graph.reject(tid, "use fewer models", llm, tenant=a, dbt_runner=_no_dbt)
    assert again["status"] == graph.AWAITING and _ids(llm.prompts[0][1], "aaa_")
    assert not _ids(llm.prompts[0][1], "bbb_")


def test_no_tenant_behaviour_unchanged(tenants, tmp_path, profile, good, monkeypatch):
    t = tenants["beta"]
    graph.start(t.target, "beta", _llm(_design(good, "bbb_")), profile=profile, tenant=t, dbt_runner=_no_dbt)
    # the module defaults still point at the repo's knowledge after a tenant run
    assert graph.DEFAULT_KPIS == paths.KNOWLEDGE / "kpis.yaml"
    assert graph.DEFAULT_BLUEPRINT == paths.KNOWLEDGE / "blueprint.md"
    assert graph.DEFAULT_APPROVED == paths.KNOWLEDGE / "approved.yaml"
    assert graph.DEFAULT_POLICY == paths.KNOWLEDGE / "shop" / "policy.yaml"

    seen: list[dict] = []
    real = graph.build_graph

    def spy(llm, saver, **kw):
        seen.append(kw)
        return real(llm, saver, **kw)

    monkeypatch.setattr(graph, "build_graph", spy)
    llm = _llm(good)
    out = graph.start(tmp_path / "target", "shop", llm, profile=profile)
    assert out["status"] in (graph.AWAITING, graph.INVALID)  # the default catalogue may differ from the sample design
    assert seen == [{}]  # no tenant: build_graph gets exactly what the caller passed
    assert (tmp_path / "state" / graph.CHECKPOINT_FILE).is_file()  # GOVERNOR_STATE_DIR, as before
    prompt = llm.prompts[0][1]
    default_ids = {k.id for k in load_kpis(graph.DEFAULT_KPIS).kpis}
    assert all(re.search(rf"\b{re.escape(i)}\b", prompt) for i in default_ids)  # the default catalogue, as before
    assert not _ids(prompt, "bbb_")


def test_cli_tenant_fills_target_and_refuses_mismatch(tenants, tmp_path, profile, good, capsys, monkeypatch):
    a, b = tenants["alpha"], tenants["beta"]
    script = tmp_path / "script.json"
    script.write_text(json.dumps({"propose": [json.dumps(_design(good, "aaa_"))]}), encoding="utf-8")
    prof = tmp_path / "profile.json"
    prof.write_text(json.dumps(profile), encoding="utf-8")
    run = ["run", "--llm", f"fake:{script}", "--profile", str(prof)]

    assert cli.main([*run, "--tenant", "alpha"]) == 0
    out = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert out["status"] == graph.AWAITING
    assert "name: alpha" in (a.target / "dbt_project.yml").read_text(encoding="utf-8")  # project name = tenant name
    assert (a.target / "governor" / "design.md").is_file() and a.checkpoints.is_file()
    assert not b.target.exists()
    assert cli.main([*run, "--tenant", "alpha", "--target", str(a.target)]) == 0  # the tenant's own target is fine
    capsys.readouterr()

    assert cli.main([*run, "--tenant", "alpha", "--target", str(b.target)]) == 2
    err = capsys.readouterr().err
    assert "is not the target of tenant alpha" in err
    assert not b.target.exists()  # nothing written to beta's target

    published: list[Path] = []

    def fake_publish(target, open_pr=False):
        published.append(Path(target))
        return {"status": "nothing_to_publish", "reason": "the build matches main"}

    monkeypatch.setattr("governor.build.publish.publish", fake_publish)
    assert cli.main(["publish", "--tenant", "beta"]) == 0
    assert published == [b.target]
    assert cli.main(["publish", "--tenant", "beta", "--target", str(a.target)]) == 2
    assert published == [b.target]

    assert cli.main(["publish", "--tenant", "gamma"]) == 2
    assert "unknown tenant 'gamma' (known: alpha, beta)" in capsys.readouterr().err
    assert cli.main(["publish"]) == 2
    assert "publish needs --target" in capsys.readouterr().err
    monkeypatch.delenv("GOVERNOR_TENANTS")
    assert cli.main(["publish", "--tenant", "beta"]) == 2
    assert "--tenant needs GOVERNOR_TENANTS" in capsys.readouterr().err


def test_certify_refuses_admin_dsn_of_another_tenant(tenants, capsys, monkeypatch):
    a, b = tenants["alpha"], tenants["beta"]
    monkeypatch.setenv("GOVERNOR_PG_ADMIN_DSN", "host=db-beta port=55442 dbname=shop_beta user=postgres")
    with pytest.raises(cert.CertifyError) as err:
        cert.certify(a.target, "Reviewer", tenant=a, dbt_runner=_no_dbt)
    msg = str(err.value)
    assert "db-beta:55442/shop_beta" in msg and "tenant alpha (db-alpha:55441/shop_alpha)" in msg
    assert "user=" not in msg and "postgres" not in msg

    assert cli.main(["certify", "--tenant", "alpha", "--by", "Reviewer"]) == 1
    assert "not at the database of tenant alpha" in capsys.readouterr().err

    for dsn in ("host=db-alpha port=55441 dbname=shop_beta", "host=db-alpha port=5432 dbname=shop_alpha",
                "postgresql://u@db-other:55441/shop_alpha"):
        with pytest.raises(cert.CertifyError, match="not at the database of tenant alpha"):
            cert.check_admin_dsn(dsn, a)

    # the tenant's own database passes the check and certify goes on to the merge check (no repo: not_merged)
    monkeypatch.setenv("GOVERNOR_PG_ADMIN_DSN", "postgresql://postgres@db-alpha:55441/shop_alpha")
    a.target.mkdir(parents=True)
    out = cert.certify(a.target, "Reviewer", tenant=a, dbt_runner=_no_dbt)
    assert out["status"] == "not_merged"
    with pytest.raises(cert.CertifyError, match="is not the target of tenant alpha"):
        cert.certify(b.target, "Reviewer", tenant=a, dbt_runner=_no_dbt)
