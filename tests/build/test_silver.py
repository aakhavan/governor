"""Silver: check_sql, generated yml and tests, the repair loop (offline with a fake dbt), and the live build in
dev_governor (skipped without the test bed)."""
import json
import os
from pathlib import Path

import pytest
import yaml

from governor.build import graph, silver
from governor.build.dbt import DbtResult
from governor.build.llm import FakeBuildLLM
from governor.build.models import Proposal
from governor.build.workspace import init_target, write_sources

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "build"
SILVER = json.loads((FIXTURES / "sample_silver.json").read_text(encoding="utf-8"))
GOOD_LINES = SILVER["repair"]["int_order_lines"][0]


# ---- check_sql ----

def test_fixture_sql_passes_the_checks(good):
    for name, replies in SILVER["intermediate"].items():
        assert silver.check_sql(name, replies[0], good) == [], name
    assert silver.check_sql("int_order_lines", GOOD_LINES, good) == []
    for m in Proposal.model_validate(good).silver_models:
        if m.folder == "staging":
            assert silver.check_sql(m, silver.staging_sql(m), good) == [], m.name


def test_staging_sql_is_code(good):
    m = Proposal.model_validate(good).model("stg_orders")
    sql = silver.staging_sql(m)
    assert sql.startswith("select\n") and sql.rstrip().endswith("from {{ source('raw', 'olist_orders_dataset') }}")
    assert "CAST(NULLIF(order_purchase_timestamp, '') AS timestamp) as purchased_at" in sql


@pytest.mark.parametrize("sql, expected", [
    ("select order_id from {{ ref('stg_orders') }}; select 1", "exactly one SELECT"),
    ("select * from {{ source('raw', 'olist_orders_dataset') }}", "source() is not allowed"),
    ("select * from {{ ref('stg_reviews') }}", "not a declared ref"),
    ("drop table dev_governor.stg_orders", "not a SELECT"),
    ("create table x as select 1", "not a SELECT"),
    ("delete from {{ ref('stg_orders') }}", "not a SELECT"),
    ("select 1 as a into x", "DDL or DML"),
    ("select {{ var('x') }} from {{ ref('stg_orders') }}", "Jinja call"),
    ("{% set x = 1 %} select 1", "Jinja block"),
    ("select from where", "does not parse"),
    ("", "empty"),
])
def test_check_sql_refuses(good, sql, expected):
    problems = silver.check_sql("int_orders", sql, good)
    assert any(expected in p for p in problems), problems


def test_staging_may_read_only_its_own_raw_table(good):
    assert silver.check_sql("stg_orders", "select 1 from {{ source('raw', 'olist_orders_dataset') }}", good) == []
    problems = silver.check_sql("stg_orders", "select 1 from {{ source('raw', 'olist_customers_dataset') }}", good)
    assert problems and "not this model's raw table" in problems[0]


def test_clean_sql_strips_fence_and_semicolon():
    assert silver.clean_sql("```sql\nselect 1;\n```") == "select 1\n"


# ---- yml and singular tests ----

def test_written_yml_and_key_tests(tmp_path, good):
    init_target(tmp_path, "shop")
    llm = FakeBuildLLM({"intermediate": SILVER["intermediate"]})
    silver.write_silver(tmp_path, good, llm)
    stg = yaml.safe_load((tmp_path / "models" / "staging" / "_staging.yml").read_text(encoding="utf-8"))
    inter = yaml.safe_load((tmp_path / "models" / "intermediate" / "_intermediate.yml").read_text(encoding="utf-8"))
    models = {m["name"]: m for m in stg["models"] + inter["models"]}
    assert set(models) == {m["name"] for m in good["silver_models"]}
    cols = {c["name"]: c for c in models["stg_orders"]["columns"]}
    assert cols["customer_id"]["config"]["meta"]["pii"] is True
    assert "config" not in cols["order_status"]
    assert cols["order_id"]["data_tests"] == ["unique", "not_null"]
    assert {c["name"]: c for c in models["int_orders"]["columns"]}["customer_unique_id"]["config"]["meta"]["pii"]
    # composite keys: no generic key test, one singular test each
    assert not any("data_tests" in c for c in models["stg_order_items"]["columns"])
    tests = sorted(p.name for p in (tmp_path / "tests").glob("*.sql"))
    assert tests == ["int_order_lines__primary_key.sql", "stg_order_items__primary_key.sql",
                     "stg_reviews__primary_key.sql"]
    body = (tmp_path / "tests" / "stg_order_items__primary_key.sql").read_text(encoding="utf-8")
    assert "{{ ref('stg_order_items') }}" in body and "group by order_id, order_item_id" in body
    # staging and intermediate model files written; prompts carry no data values, only the design
    assert (tmp_path / "models" / "staging" / "stg_orders.sql").is_file()
    assert (tmp_path / "models" / "intermediate" / "int_orders.sql").read_text(encoding="utf-8").startswith("select")
    prompt = dict((k, p) for k, p in llm.prompts if k == "intermediate" and "`int_order_reviews`" in p)["intermediate"]
    assert "### stg_reviews" in prompt and "| review_answered_at | timestamp |" in prompt


# ---- the repair loop with a fake dbt ----

class FakeDbt:
    """Fails a model while its file contains a marker; columns come from the design."""

    def __init__(self, design, marker="i.price"):
        self.design, self.marker, self.runs = Proposal.model_validate(design), marker, 0

    def __call__(self, target, args):
        self.runs += 1
        results = []
        for m in self.design.silver_models:
            sql = (Path(target) / "models" / m.folder / f"{m.name}.sql").read_text(encoding="utf-8")
            bad = self.marker in sql
            results.append({"unique_id": f"model.shop.{m.name}", "status": "error" if bad else "success",
                            "message": 'column i.price does not exist' if bad else "OK"})
            results.append({"unique_id": f"test.shop.not_null_{m.name}_x.abc", "status": "skipped" if bad else "pass",
                            "message": None})
        return DbtResult(not any(r["status"] == "error" for r in results), 0, results, "")

    def columns(self, names):
        return {m.name: m.column_names() for m in self.design.silver_models}


def _target(tmp_path):
    init_target(tmp_path, "shop")
    return tmp_path


def test_bad_draft_is_repaired(tmp_path, good):
    dbt = FakeDbt(good)
    llm = FakeBuildLLM({"intermediate": SILVER["intermediate"], "repair": SILVER["repair"]})
    res = silver.build_silver(_target(tmp_path), good, llm, runner=dbt, inspector=dbt.columns)
    assert res.status == silver.BUILT and res.repairs == 1 and dbt.runs == 2 and res.tests_passed == 7
    repair = [p for k, p in llm.prompts if k == "repair"]
    assert len(repair) == 1 and "column i.price does not exist" in repair[0] and "i.price as item_price" in repair[0]


def test_always_failing_model_escalates_after_two_write_and_one_plan_repair(tmp_path, good):
    dbt = FakeDbt(good)
    bad = SILVER["intermediate"]["int_order_lines"][0]
    llm = FakeBuildLLM({"intermediate": SILVER["intermediate"], "repair": {"int_order_lines": [bad]}})
    roles = []
    text = llm.text
    llm.text = lambda kind, prompt, key=None, role="write": (roles.append((kind, role)), text(kind, prompt, key, role))[1]
    res = silver.build_silver(_target(tmp_path), good, llm, runner=dbt, inspector=dbt.columns)
    assert res.status == silver.ESCALATED and res.repairs == silver.MAX_REPAIRS == 3
    assert res.escalated["model"] == "int_order_lines" and "i.price" in res.escalated["error"]
    assert [r for k, r in roles if k == "repair"] == ["write", "write", "plan"]


def test_refused_sql_is_repaired_before_dbt(tmp_path, good):
    dbt = FakeDbt(good)
    script = {"intermediate": {**SILVER["intermediate"], "int_orders": ["drop table x"]},
              "repair": {"int_order_lines": [GOOD_LINES], "int_orders": SILVER["intermediate"]["int_orders"]}}
    res = silver.build_silver(_target(tmp_path), good, FakeBuildLLM(script), runner=dbt, inspector=dbt.columns)
    assert res.status == silver.BUILT and res.repairs == 2


def test_column_mismatch_is_a_failure(good):
    built = {m["name"]: [c["name"] for c in m["columns"]] for m in good["silver_models"]}
    built["int_orders"] = built["int_orders"][:-1] + ["extra"]
    out = silver.declared_vs_built(good, built)
    assert list(out) == ["int_orders"] and "estimated_delivery_at" in out["int_orders"] and "extra" in out["int_orders"]


def test_approve_runs_silver_in_the_graph(tmp_path, profile, good):
    dbt = FakeDbt(good)
    kw = {"checkpoints": tmp_path / "cp.sqlite", "dbt_runner": dbt, "inspector": dbt.columns,
          "row_counter": lambda names: {n: 1 for n in names}}
    out = graph.start(tmp_path / "t", "shop", FakeBuildLLM({"propose": [json.dumps(good)]}), profile=profile, **kw)
    llm = FakeBuildLLM({"intermediate": SILVER["intermediate"], "repair": SILVER["repair"]})
    a = graph.approve(out["thread_id"], "amir", llm, **kw)
    # silver is built, then gold (D5): the fake dbt answers the marts run with the silver results
    assert a["status"] == "built" and a["repairs"] == 1 and dbt.runs == 3
    assert a["models"][:7] == [m["name"] for m in good["silver_models"]] and a["llm_calls"] == 1 + 3 + 1
    assert (tmp_path / "t" / "governor" / "approved.yaml").is_file()


# ---- live: dev_governor on the test bed ----

def _raw_ready() -> bool:
    if not os.environ.get("GOVERNOR_BUILD_PASSWORD"):
        return False
    try:
        import psycopg

        from governor.build.workspace import build_dsn

        with psycopg.connect(build_dsn(), connect_timeout=3) as c:
            return c.execute("select count(*) from information_schema.tables where table_schema = 'raw'").fetchone()[0] >= 9
    except Exception:  # noqa: BLE001
        return False


live = pytest.mark.skipif(not _raw_ready(), reason="needs GOVERNOR_BUILD_PASSWORD and the Olist tables in raw")


def _live_target(tmp_path):
    from governor.build.__main__ import raw_tables

    init_target(tmp_path, "shop")
    write_sources(tmp_path, raw_tables())
    return tmp_path


@live
def test_live_sample_silver_builds_with_a_repair(tmp_path, good):
    llm = FakeBuildLLM({"intermediate": SILVER["intermediate"], "repair": SILVER["repair"]})
    res = silver.build_silver(_live_target(tmp_path), good, llm)
    assert res.status == silver.BUILT, res.escalated
    assert res.repairs == 1 and res.tests_passed > 0


@live
def test_live_always_failing_script_escalates(tmp_path, good):
    bad = "select nope from {{ ref('stg_orders') }}"
    llm = FakeBuildLLM({"intermediate": {**SILVER["intermediate"], "int_order_lines": [bad]},
                        "repair": {"int_order_lines": [bad]}})
    res = silver.build_silver(_live_target(tmp_path), good, llm)
    assert res.status == silver.ESCALATED and res.escalated["model"] == "int_order_lines"
    assert "nope" in res.escalated["error"]
