"""Column descriptions from lineage (batch2c section 16): catalogue definitions for gold, lineage and profile for
staging, inheritance for intermediate, one write-model call for the rest (evidence only, never data values), and
``docs_coverage`` in governor/build.json and governor/pr.md. Offline, fake LLM and fake dbt."""
import copy
import json
from pathlib import Path

import yaml

from governor.build import docs, gold, graph, publish, silver
from governor.build.dbt import DbtResult
from governor.build.llm import FakeBuildLLM
from governor.build.models import Proposal
from governor.core.catalogue import load_kpis

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "build"
CATALOGUE = load_kpis(ROOT / "knowledge" / "kpis.yaml")
SILVER = json.loads((FIXTURES / "sample_silver.json").read_text(encoding="utf-8"))
GOOD_SILVER = {**SILVER["intermediate"], "int_order_lines": SILVER["repair"]["int_order_lines"]}


def _yml_columns(path: Path) -> dict[str, dict[str, str]]:
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    return {m["name"]: {c["name"]: c.get("description") or "" for c in m.get("columns") or []} for m in doc["models"]}


def test_docs_gold_uses_catalogue_definition(tmp_path, good):
    d = docs.describe(good, None, CATALOGUE, {}, None)
    gmv = CATALOGUE.get("gmv")
    definition = " ".join(gmv.definition.split())
    assert set(d["kpi_gmv"]) == {"month", "gmv"}
    assert definition in d["kpi_gmv"]["gmv"] and gmv.label in d["kpi_gmv"]["gmv"]
    assert "grain" in d["kpi_gmv"]["month"]
    # a companion value names its role and carries the definition
    clv = CATALOGUE.get("historical_clv")
    assert set(d["kpi_historical_clv"]) == {"cohort_month", "customers", "clv_90d", "clv_180d", "clv_365d"}
    assert " ".join(clv.definition.split()) in d["kpi_historical_clv"]["clv_90d"]
    # written into the marts yml, every output column described, grain test kept
    t = tmp_path / "t"
    gold.write_gold(t, good, CATALOGUE)
    cols = _yml_columns(t / "models" / "marts" / "sales" / "_sales.yml")
    assert cols["kpi_gmv"] == d["kpi_gmv"]
    doc = yaml.safe_load((t / "models" / "marts" / "sales" / "_sales.yml").read_text(encoding="utf-8"))
    month = next(c for m in doc["models"] if m["name"] == "kpi_gmv" for c in m["columns"] if c["name"] == "month")
    assert month["data_tests"] == ["not_null"]
    assert all(all(v for v in m.values()) for m in cols.values())


def test_docs_staging_from_lineage_and_profile(tmp_path, good, profile, policy):
    prof = copy.deepcopy(profile)
    orders = next(t for t in prof["tables"] if t["name"] == "olist_orders_dataset")
    for c in orders["columns"]:
        if c["name"] == "order_approved_at":
            c["null_rate"], c["min"], c["max"] = 0.05, "2017-01-05T11:56:06", "2018-09-03T17:40:06"
        if c["name"] == "order_purchase_timestamp":
            c["null_rate"] = 0.0
    d = docs.describe(good, prof, CATALOGUE, policy, None)
    stg = d["stg_orders"]
    assert "raw.olist_orders_dataset.order_approved_at" in stg["approved_at"]
    assert "cast from text to timestamp" in stg["approved_at"] and "empty text as null" in stg["approved_at"]
    assert "sometimes null (1 to 10%)" in stg["approved_at"]
    assert "2017" not in stg["approved_at"] and "2018" not in stg["approved_at"]  # never values
    assert "never null" in stg["purchased_at"]
    assert stg["order_id"].startswith("Order key.") and "primary key" in stg["order_id"]
    assert "copied as is" in stg["order_id"]
    assert docs.PII_NOTE in stg["customer_id"] and docs.PII_NOTE not in stg["order_status"]
    assert "part of the primary key (order_id, order_item_id)" in d["stg_order_items"]["order_item_id"]
    assert "renamed from price" not in d["stg_order_items"]["item_price"]  # a cast, not a rename
    # policy tag on the source column marks a column the design did not flag
    bad = copy.deepcopy(good)
    next(c for c in bad["silver_models"][2]["columns"] if c["name"] == "customer_city")["pii"] = False
    assert docs.PII_NOTE in docs.describe(bad, prof, None, policy, None)["stg_customers"]["customer_city"]
    # written into _staging.yml
    silver.write_silver(tmp_path, good, FakeBuildLLM({"intermediate": GOOD_SILVER}), docs=d)
    assert _yml_columns(tmp_path / "models" / "staging" / "_staging.yml")["stg_orders"] == stg


def test_docs_intermediate_inherits_from_refs(tmp_path, good, profile, policy):
    d = docs.describe(good, profile, CATALOGUE, policy, None)
    lines = d["int_order_lines"]
    assert lines["item_price"] == d["stg_order_items"]["item_price"]  # first ref that has the column
    assert lines["order_status"] == d["stg_orders"]["order_status"]
    assert lines["customer_unique_id"] == "person-level customer key"  # the design's own text is kept
    assert d["int_order_reviews"]["review_score"] == d["stg_reviews"]["review_score"]
    assert all(v for m in d.values() for v in m.values())  # the sample design needs no model call
    silver.write_silver(tmp_path, good, FakeBuildLLM({"intermediate": GOOD_SILVER}), docs=d)
    assert _yml_columns(tmp_path / "models" / "intermediate" / "_intermediate.yml")["int_order_lines"] == lines


def _with_computed(good):
    design = copy.deepcopy(good)
    design["silver_models"].append({
        "name": "int_customer_orders", "folder": "intermediate", "source_table": None, "refs": ["int_orders"],
        "description": "one row per person-level customer with their count of orders",
        "primary_key": ["customer_unique_id"],
        "columns": [{"name": "customer_unique_id", "expr": None, "type": "text", "pii": True, "description": ""},
                    {"name": "order_count", "expr": None, "type": "integer", "pii": False, "description": ""},
                    {"name": "first_purchased_at", "expr": None, "type": "timestamp", "pii": False, "description": ""}]})
    return design


def test_docs_llm_fills_the_rest_without_values(good, profile, policy):
    design = _with_computed(good)
    prof = copy.deepcopy(profile)
    secrets = []
    for t in prof["tables"]:
        for c in t["columns"]:
            if not c["pii"] and c["inferred_type"] in ("integer", "numeric"):
                c["min"], c["max"] = 98765.4321, 12345.6789
                secrets = ["98765.4321", "12345.6789"]
    long_text = "Number of orders the person placed, counted over int_orders by customer_unique_id " * 4
    llm = FakeBuildLLM({"describe": {"int_customer_orders": [json.dumps(
        {"order_count": long_text, "first_purchased_at": "Purchase time of the person's first order.",
         "not_a_column": "ignored"})]}})
    d = docs.describe(design, prof, CATALOGUE, policy, llm)
    assert [k for k, _ in llm.prompts] == ["describe"]  # one call, only for the model with empty columns
    prompt = llm.prompts[0][1]
    assert "order_count" in prompt and "first_purchased_at" in prompt and "int_orders" in prompt
    assert "one row per person-level customer" in prompt  # model description
    assert "order_status 'delivered' means the order was delivered" in prompt  # design assumptions
    assert "rows" in prompt  # profile counts
    for s in secrets:
        assert s not in prompt  # never data values
    cols = d["int_customer_orders"]
    assert cols["customer_unique_id"] == d["int_orders"]["customer_unique_id"]  # rule 3 before the model
    assert len(cols["order_count"]) <= docs.MAX_CHARS and long_text.startswith(cols["order_count"])
    assert not cols["order_count"].endswith(" ")
    assert cols["first_purchased_at"] == "Purchase time of the person's first order."
    assert "not_a_column" not in cols
    # a reply that is not JSON leaves the columns empty (coverage shows it) instead of failing the build
    bad = docs.describe(design, prof, CATALOGUE, policy, FakeBuildLLM({"describe": {"int_customer_orders": ["no"]}}))
    assert bad["int_customer_orders"]["order_count"] == ""
    assert docs.trim("word " * 60).count(" ") < 60 and len(docs.trim("x" * 300)) == docs.MAX_CHARS


class _Dbt:
    def __init__(self, design):
        self.design = Proposal.model_validate(design)

    def __call__(self, target, args):
        names = ([gold.model_name(k.id) for k in gold.built_kpis(self.design)] if "marts" in args
                 else [m.name for m in self.design.silver_models])
        return DbtResult(True, 0, [{"unique_id": f"model.shop.{n}", "status": "success", "message": "OK"}
                                   for n in names], "")

    def columns(self, names):
        return {m.name: m.column_names() for m in self.design.silver_models}


def test_docs_coverage_in_build_summary(tmp_path, good, profile):
    design = _with_computed(good)
    dbt = _Dbt(design)
    kw = {"checkpoints": tmp_path / "cp.sqlite", "dbt_runner": dbt, "inspector": dbt.columns,
          "row_counter": lambda names: {n: 3 for n in names}}
    out = graph.start(tmp_path / "t", "shop", FakeBuildLLM({"propose": [json.dumps(design)]}), profile=profile, **kw)
    script = {"intermediate": {**GOOD_SILVER, "int_customer_orders": [
        "select customer_unique_id, count(*) as order_count, min(purchased_at) as first_purchased_at "
        "from {{ ref('int_orders') }} group by 1"]},
              "describe": {"int_customer_orders": [json.dumps({"order_count": "Orders the person placed."})]}}
    llm = FakeBuildLLM(script)
    a = graph.approve(out["thread_id"], "amir", llm, **kw)
    assert a["status"] == "built", a
    t = tmp_path / "t"
    summary = json.loads((t / "governor" / "build.json").read_text(encoding="utf-8"))
    cov = summary["docs_coverage"]
    assert cov == docs.coverage(t)
    assert cov["columns"] > 40 and cov["described"] == cov["columns"] - 1  # first_purchased_at left empty
    assert cov["share"] == round(cov["described"] / cov["columns"], 4) and cov["share"] < 1
    assert any(kind == "describe" for kind, _ in llm.prompts)
    inter = _yml_columns(t / "models" / "intermediate" / "_intermediate.yml")
    assert inter["int_customer_orders"]["order_count"] == "Orders the person placed."
    pr = publish.render_pr(t, summary, "governor/build-x")
    assert f"Column descriptions: {cov['share']:.0%} ({cov['described']} of {cov['columns']} columns" in pr
