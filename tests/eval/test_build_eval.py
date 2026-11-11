"""Build evaluation harness (batch2b section 15), offline: fake LLM, fake dbt, fake gold queries."""
import importlib.util
import json
from pathlib import Path

import pytest

from governor.build import gold
from governor.build.dbt import DbtResult
from governor.build.llm import FakeBuildLLM
from governor.build.models import Proposal
from governor.build.workspace import init_target
from governor.eval import build_eval as be

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "build"
SAMPLE_GOLD = ROOT / "evaluation" / "build_gold" / "sample_gold.yaml"
DESIGN = json.loads((FIXTURES / "sample_design.json").read_text(encoding="utf-8"))
SILVER = json.loads((FIXTURES / "sample_silver.json").read_text(encoding="utf-8"))
GOOD_SILVER = {**SILVER["intermediate"], "int_order_lines": SILVER["repair"]["int_order_lines"]}


def _sample_profile() -> dict:
    spec = importlib.util.spec_from_file_location("_build_conftest", ROOT / "tests" / "build" / "conftest.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.sample_profile()


@pytest.fixture(scope="module")
def profile() -> dict:
    return _sample_profile()


@pytest.fixture(autouse=True)
def _state_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("GOVERNOR_STATE_DIR", str(tmp_path / "state"))
    monkeypatch.delenv("GOVERNOR_BUILD_NOTIFIERS", raising=False)


# ---- gold checks ----

def _check(**kw):
    return be.GoldCheck(**{"id": "c", "table": "kpi_gmv", "expr": "max(gmv)", "where": "", "expected": 455.0,
                           "tol": 0.001, **kw})


def test_gold_scoring_pass_out_of_tolerance_and_missing():
    values = {"a": 455.0005, "b": 460.0}

    def query(check, schema):
        assert schema == "dev_governor"
        if check.id == "c":
            raise be.GoldQueryError("missing_table", "relation does not exist")
        if check.id == "d":
            raise be.GoldQueryError("missing_column", "column gmv does not exist")
        return values[check.id]

    out = be.score_gold([_check(id="a"), _check(id="b"), _check(id="c"), _check(id="d")], query)
    assert [o["passed"] for o in out] == [True, False, False, False]
    assert [o["reason"] for o in out] == ["", "out_of_tolerance", "missing_table", "missing_column"]
    assert out[0]["value"] == pytest.approx(455.0005)


def test_gold_scoring_null_and_decimal():
    from decimal import Decimal

    out = be.score_gold([_check(id="n"), _check(id="d", tol=0)], lambda c, s: None if c.id == "n" else Decimal("455"))
    assert [o["passed"] for o in out] == [False, True] and out[0]["reason"] == "no_value"


def test_gold_file_loads_and_sql_is_composed():
    g = be.load_gold(SAMPLE_GOLD)
    assert len(g.checks) == 6 and g.checks[0].table == "kpi_gmv"
    assert len(be.file_sha256(SAMPLE_GOLD)) == 64
    q = be.check_sql(g.checks[0])
    text = q.as_string(None) if hasattr(q, "as_string") else str(q)
    assert '"dev_governor"."kpi_gmv"' in text and "where to_char(month" in text


# ---- baseline pieces ----

def test_baseline_paths_are_confined(tmp_path):
    t = tmp_path / "t"
    t.mkdir()
    reply = be.BaselineReply(files=[
        {"path": "models/marts/kpi_gmv.sql", "content": "select 1"},
        {"path": "tests/x.sql", "content": "select 1 where false"},
        {"path": "../escape.sql", "content": "x"},
        {"path": "models/../../escape.sql", "content": "x"},
        {"path": "dbt_project.yml", "content": "x"},
        {"path": "C:/abs.sql", "content": "x"},
        {"path": "models/sources.yml", "content": "x"},
    ])
    written, refused = be.write_baseline(t, reply)
    assert written == ["models/marts/kpi_gmv.sql", "tests/x.sql"] and len(refused) == 5
    assert not (tmp_path / "escape.sql").exists()


def test_baseline_prompt_has_no_templates(profile):
    from governor.core.catalogue import load_blueprint, load_kpis

    cat = load_kpis(be.Hooks().kpis_path)
    text = be.baseline_prompt(profile, cat, load_blueprint(be.Hooks().blueprint_path))
    assert "{{" not in text.replace("{{ source(", "").replace("{{ ref(", "")
    for k in cat.kpis:
        assert k.template_sql.strip().splitlines()[0] not in text
    gmv = next(d for d in be.kpis_for_baseline(cat) if d["id"] == "gmv")
    assert gmv["model"] == "kpi_gmv" and gmv["output_columns"] == ["month", "gmv"]


# ---- the run loop ----

class FakeDbt:
    """Every model and test succeeds; columns come from the design."""

    def __init__(self, design):
        self.design, self.calls = Proposal.model_validate(design), []

    def __call__(self, target, args):
        self.calls.append(args)
        if "marts" in args:
            names = [gold.model_name(k.id) for k in gold.built_kpis(self.design)]
            res = [{"unique_id": f"model.shop.{n}", "status": "success", "message": ""} for n in names]
            res += [{"unique_id": f"test.shop.nn_{n}.a", "status": "pass", "message": None} for n in names]
        elif args == ["build"]:
            res = [{"unique_id": "model.shop.kpi_gmv", "status": "success", "message": ""},
                   {"unique_id": "test.shop.x.a", "status": "pass", "message": None},
                   {"unique_id": "test.shop.y.a", "status": "fail", "message": "1 row"}]
            return DbtResult(False, 1, res, "")
        else:
            res = [{"unique_id": f"model.shop.{m.name}", "status": "success", "message": ""}
                   for m in self.design.silver_models]
        return DbtResult(True, 0, res, "")

    def columns(self, names):
        return {m.name: m.column_names() for m in self.design.silver_models}


def _hooks(profile, built_tables):
    dbt = FakeDbt(DESIGN)
    resets = []

    def make_target(work, system, i):
        t = work / f"{system}-{i:02d}" / "project"
        assert not t.exists()
        init_target(t, be.PROJECT)
        return t

    def query(check, schema):
        if check.table not in built_tables:
            raise be.GoldQueryError("missing_table", "no table")
        return check.expected

    hooks = be.Hooks(reset=lambda: resets.append(1), make_target=make_target, query=query,
                     profiler=lambda policy: profile, dbt_runner=dbt,
                     graph_kwargs={"inspector": dbt.columns, "row_counter": lambda names: {n: 1 for n in names}})
    return hooks, dbt, resets


REPORT_KEYS = {"system", "gold_file", "gold_sha256", "models", "approval", "runs", "summary", "total_cost_usd",
               "stopped_by_budget", "max_cost_usd"}
RUN_KEYS = {"run", "status", "valid_design_first_try", "validation_repairs", "dbt_repairs", "escalated",
            "tests_passed", "tests_failed", "blueprint_high", "kpi_decisions_correct", "kpi_decisions_total",
            "gold_passed", "gold_total", "cost_usd", "seconds"}


def test_agent_runs_are_approved_by_the_harness_and_scored(tmp_path, profile):
    tables = {f"kpi_{k}" for k in ("gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score",
                                   "repeat_purchase_rate")}
    hooks, dbt, resets = _hooks(profile, tables)
    llm = FakeBuildLLM({"propose": [json.dumps(DESIGN)], "intermediate": GOOD_SILVER})
    rep = be.evaluate("agent", 2, SAMPLE_GOLD, llm, work=tmp_path / "w", hooks=hooks)
    assert REPORT_KEYS <= set(rep) and len(rep["gold_sha256"]) == 64 and rep["approval"] == "eval-harness"
    assert rep["models"] == {"plan": "fake", "write": "fake"} and len(resets) == 2
    assert len(rep["runs"]) == 2
    for r in rep["runs"]:
        assert RUN_KEYS <= set(r)
        assert r["status"] == "built" and r["approved_by"] == "eval-harness"
        assert r["gold_passed"] == r["gold_total"] == 6
        assert r["valid_design_first_try"] is True and r["validation_repairs"] == 0 and r["dbt_repairs"] == 0
        assert r["kpi_decisions_correct"] == r["kpi_decisions_total"] == 10
        assert r["escalated"] is False and r["tests_passed"] == 8 and r["blueprint_high"] == 0
        assert r["cost_usd"] == 0.0
    s = rep["summary"]
    assert s["runs"] == 2 and s["built_rate"] == 1.0 and s["gold_all_passed_rate"] == 1.0
    assert s["mean"]["gold_passed"] == 6.0 and s["valid_design_first_try_rate"] == 1.0
    json.dumps(rep)  # serialisable


def test_partial_baseline_scores_what_it_built(tmp_path, profile):
    hooks, dbt, _ = _hooks(profile, {"kpi_gmv"})
    files = {"files": [{"path": "models/marts/kpi_gmv.sql", "content": "select 1 as month, 2 as gmv"}]}
    llm = FakeBuildLLM({"baseline": [json.dumps(files)]})
    rep = be.evaluate("baseline", 1, SAMPLE_GOLD, llm, work=tmp_path / "w", hooks=hooks)
    (r,) = rep["runs"]
    assert RUN_KEYS <= set(r) and rep["approval"] is None
    assert r["gold_passed"] == 1 and r["gold_total"] == 6 and r["dbt_repairs"] == 0
    assert dbt.calls == [["build"]]  # built once, never repaired
    assert r["status"] == "failed" and r["tests_passed"] == 1 and r["tests_failed"] == 1
    assert r["files"] == ["models/marts/kpi_gmv.sql"]
    assert r["kpi_decisions_correct"] == 3  # gmv built, conversion_rate and gross_margin declined
    assert {c["reason"] for c in r["gold"] if not c["passed"]} == {"missing_table"}
    assert (Path(r["target"]) / "models" / "marts" / "kpi_gmv.sql").is_file()
    assert [k for k, _ in llm.prompts] == ["baseline"]


def test_unparseable_baseline_reply_is_recorded(tmp_path, profile):
    hooks, dbt, _ = _hooks(profile, set())
    rep = be.evaluate("baseline", 1, SAMPLE_GOLD, FakeBuildLLM({"baseline": ["not json"]}), work=tmp_path / "w",
                      hooks=hooks)
    (r,) = rep["runs"]
    assert r["status"] == "invalid_output" and r["gold_passed"] == 0 and dbt.calls == []


def test_budget_stops_further_runs(tmp_path, profile):
    hooks, _, resets = _hooks(profile, {"kpi_gmv"})
    files = {"files": [{"path": "models/marts/kpi_gmv.sql", "content": "select 1"}]}

    class Costly(FakeBuildLLM):
        def structured(self, kind, prompt, schema, role="plan"):
            out = super().structured(kind, prompt, schema, role)
            self.calls[-1]["cost_usd"] = 0.6
            return out

    rep = be.evaluate("baseline", 5, SAMPLE_GOLD, Costly({"baseline": [json.dumps(files)]}), work=tmp_path / "w",
                      hooks=hooks, max_cost_usd=1.0)
    assert len(rep["runs"]) == 2 and rep["stopped_by_budget"] is True and rep["total_cost_usd"] == pytest.approx(1.2)
    assert rep["summary"]["mean"]["cost_usd"] == pytest.approx(0.6)


def test_a_broken_run_is_recorded_and_the_loop_goes_on(tmp_path, profile):
    hooks, _, _ = _hooks(profile, set())

    def boom():
        raise RuntimeError("database down")

    hooks.reset = boom
    rep = be.evaluate("agent", 2, SAMPLE_GOLD, FakeBuildLLM({}), work=tmp_path / "w", hooks=hooks)
    assert [r["status"] for r in rep["runs"]] == ["error", "error"] and "database down" in rep["runs"][0]["error"]
    assert rep["summary"]["statuses"] == {"error": 2}


def test_build_eval_blueprint_breakdown():
    found = [{"rule": "L2", "severity": "high"}, {"rule": "L2", "severity": "high"}, {"rule": "L5", "severity": "low"}]
    assert be.blueprint_breakdown(found) == {"L2": {"high": 2}, "L5": {"low": 1}}
    runs = [{"status": "built", "blueprint_findings": {"L2": {"high": 1}}},
            {"status": "built", "blueprint_findings": {"L2": {"high": 2}, "L5": {"low": 1}}},
            {"status": "error"}]
    assert be.summarise(runs, 0)["blueprint_findings_by_rule"] == {"L2": {"high": 3}, "L5": {"low": 1}}


def test_build_eval_valid_first_try_recorded(tmp_path, profile):
    hooks, _, _ = _hooks(profile, set())
    llm = FakeBuildLLM({"propose": [json.dumps(DESIGN)], "intermediate": GOOD_SILVER})
    rep = be.evaluate("agent", 1, SAMPLE_GOLD, llm, work=tmp_path / "w", hooks=hooks)
    run = rep["runs"][0]
    assert run["valid_design_first_try"] is True and isinstance(run["blueprint_findings"], dict)
    assert rep["summary"]["valid_design_first_try_rate"] == 1.0


def test_cli_rejects_unknown_system(capsys):
    with pytest.raises(SystemExit):
        be.main(["--system", "other", "--gold", str(SAMPLE_GOLD), "--out", "x.json"])


# ---- --policy (batch2d section 24) ----

def _capture_main(monkeypatch, tmp_path, extra):
    seen = {}

    def fake_evaluate(system, runs, gold_path, llm, **kw):
        seen.update(kw)
        return {"summary": {"runs": 0, "statuses": {}, "mean": {"gold_passed": 0}}, "total_cost_usd": 0.0,
                "stopped_by_budget": False}

    monkeypatch.setattr(be, "make_eval_llm", lambda *a: object())
    monkeypatch.setattr(be, "evaluate", fake_evaluate)
    assert be.main(["--system", "agent", "--gold", str(SAMPLE_GOLD), "--out", str(tmp_path / "r.json"), *extra]) == 0
    return seen


def test_build_eval_policy_option_reaches_the_hooks(monkeypatch, tmp_path):
    policy = tmp_path / "policy.yaml"
    policy.write_text("cust_ref: customer_id\n", encoding="utf-8")
    hooks = _capture_main(monkeypatch, tmp_path, ["--policy", str(policy)])["hooks"]
    assert hooks.policy == policy
    # the agent path takes the policy from the hooks
    calls = []

    def fake_start(target, project, llm, *, policy, **kw):
        calls.append(policy)
        raise RuntimeError("stop here")

    monkeypatch.setattr(be.graph, "start", fake_start)
    with pytest.raises(RuntimeError, match="stop here"):
        be.run_agent(object(), tmp_path / "t", tmp_path / "w", hooks, None)
    assert calls == [policy]


def test_build_eval_default_policy_is_still_the_shop_policy(monkeypatch, tmp_path):
    assert _capture_main(monkeypatch, tmp_path, [])["hooks"] is None
    assert be.Hooks().policy == ROOT / "knowledge" / "shop" / "policy.yaml"


def test_build_eval_rejects_a_missing_policy_file(tmp_path):
    with pytest.raises(SystemExit):
        be.main(["--system", "agent", "--gold", str(SAMPLE_GOLD), "--out", str(tmp_path / "r.json"),
                 "--policy", str(tmp_path / "nope.yaml")])
