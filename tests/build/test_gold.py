"""Gold: rendered catalogue templates, the blueprint check (each rule on a crafted bad project), the gap report,
stale-file pruning, the staging guard, the graph to built / blueprint_failed (offline with a fake dbt), and the live
sample build checked against values computed here from the sample CSVs (skipped without the test bed)."""
import csv
import json
import os
from collections import defaultdict
from pathlib import Path

import pytest
import sqlglot
import yaml
from sqlglot import exp

from governor.build import gold, graph, silver
from governor.build.dbt import DbtResult
from governor.build.llm import FakeBuildLLM
from governor.build.models import Proposal
from governor.build.workspace import init_target
from governor.core.catalogue import BlueprintException, load_blueprint, load_kpis

ROOT = Path(__file__).resolve().parents[2]
FIXTURES = ROOT / "tests" / "fixtures" / "build"
SAMPLE = ROOT / "testbed" / "sample"
SILVER = json.loads((FIXTURES / "sample_silver.json").read_text(encoding="utf-8"))
GOOD_SILVER = {**SILVER["intermediate"], "int_order_lines": SILVER["repair"]["int_order_lines"]}
CATALOGUE = load_kpis(ROOT / "knowledge" / "kpis.yaml")
SEVERITY = {r.id: r.severity for r in load_blueprint(ROOT / "knowledge" / "blueprint.md").rules}
BUILT = ["gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purchase_rate",
         "cohort_retention", "historical_clv"]


# ---- rendering ----

def _any_mapping(kpi):
    m = {rel: f"model_{rel}" for rel in kpi.relations}
    for name, inp in kpi.inputs.items():
        m[name] = f"{name}_col = 'x'" if inp.type == "boolean" else f"{name}_col"
    return m


@pytest.mark.parametrize("kpi", CATALOGUE.kpis, ids=lambda k: k.id)
def test_every_catalogue_kpi_renders_to_postgres(kpi):
    sql = gold.gold_sql(kpi, _any_mapping(kpi))
    for rel in kpi.relations:
        assert f"{{{{ ref('model_{rel}') }}}}" in sql
    tree = sqlglot.parse_one(gold._plain(sql), read="postgres")
    assert isinstance(tree, exp.Query)


def test_sample_mappings_render_and_parse(good):
    for k in gold.built_kpis(good):
        sql = gold.gold_sql(CATALOGUE.get(k.id), k.mapping)
        assert isinstance(sqlglot.parse_one(gold._plain(sql), read="postgres"), exp.Query)


# ---- a generated project (offline) ----

def _project(tmp_path, good):
    t = tmp_path / "t"
    init_target(t, "shop")
    silver.write_silver(t, good, FakeBuildLLM({"intermediate": GOOD_SILVER}))
    (t / "governor").mkdir(exist_ok=True)
    (t / "governor" / "design.json").write_text(json.dumps(good), encoding="utf-8")
    gold.write_gold(t, good, CATALOGUE)
    return t


def _check(t, policy):
    return gold.check_project(t, CATALOGUE, policy)


def test_write_gold_files_and_yml(tmp_path, good):
    t = _project(tmp_path, good)
    files = sorted(p.relative_to(t / "models" / "marts").as_posix() for p in (t / "models" / "marts").rglob("*.sql"))
    assert files == sorted(["sales/kpi_gmv.sql", "sales/kpi_net_revenue.sql", "sales/kpi_aov.sql",
                            "delivery/kpi_on_time_delivery_rate.sql", "customer_experience/kpi_avg_review_score.sql",
                            "customers/kpi_repeat_purchase_rate.sql", "customers/kpi_cohort_retention.sql",
                            "customers/kpi_historical_clv.sql"])
    sql = (t / "models" / "marts" / "sales" / "kpi_gmv.sql").read_bytes().decode("utf-8")
    assert "FROM {{ ref('int_order_lines') }}" in sql and "\r" not in sql
    assert sql == gold.gold_sql(CATALOGUE.get("gmv"), next(k for k in good["kpis"] if k["id"] == "gmv")["mapping"])
    doc = yaml.safe_load((t / "models" / "marts" / "sales" / "_sales.yml").read_text(encoding="utf-8"))
    entry = {m["name"]: m for m in doc["models"]}["kpi_gmv"]
    meta = entry["config"]["meta"]
    kpi = CATALOGUE.get("gmv")
    assert meta["kpi_id"] == "gmv" and meta["owner"] == kpi.owner and meta["source_tier"] == "platform"
    assert meta["source_ref"] == kpi.source.ref and meta["template_sha256"] == gold.sha256(kpi.template_sql)
    assert meta["rendered_sha256"] == gold.sha256(sql) and entry["description"].startswith("Item price plus freight")
    assert entry["columns"] == [{"name": "month", "description": "the month (grain)", "data_tests": ["not_null"]}]
    cust = {m["name"]: m for m in yaml.safe_load((t / "models" / "marts" / "customers" / "_customers.yml")
                                                 .read_text(encoding="utf-8"))["models"]}
    assert "columns" not in cust["kpi_repeat_purchase_rate"]  # grain total
    assert cust["kpi_cohort_retention"]["columns"][0]["name"] == "cohort_month"


def test_blueprint_check_is_clean_on_the_generated_project(tmp_path, good, policy):
    assert _check(_project(tmp_path, good), policy) == []


def _edit(path: Path, old: str, new: str):
    text = path.read_text(encoding="utf-8")
    assert old in text, (path, old)
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def _yml(path: Path, change):
    doc = yaml.safe_load(path.read_text(encoding="utf-8"))
    change(doc)
    path.write_text(yaml.safe_dump(doc, sort_keys=False), encoding="utf-8")


def _models(doc):
    return {m["name"]: m for m in doc["models"]}


def _l1(t):
    (t / "models" / "misc").mkdir()
    (t / "models" / "misc" / "orphan.sql").write_text("select 1 as x", encoding="utf-8")


def _l2(t):
    (t / "models" / "marts" / "sales" / "kpi_gmv.sql").write_text(
        "select order_id from {{ source('raw', 'olist_orders_dataset') }}", encoding="utf-8")


def _l3(t):
    _edit(t / "models" / "intermediate" / "int_orders.sql", "from {{ ref('stg_orders') }} as o",
          "from {{ ref('stg_orders') }} as o\njoin {{ ref('kpi_gmv') }} as g on true")


def _l4(t):
    def drop(doc):
        for c in _models(doc)["stg_orders"]["columns"]:
            c.pop("data_tests", None)
    _yml(t / "models" / "staging" / "_staging.yml", drop)
    (t / "tests" / "stg_reviews__primary_key.sql").unlink()


def _l5(t):
    _yml(t / "models" / "marts" / "sales" / "_sales.yml",
         lambda doc: _models(doc)["kpi_gmv"]["config"]["meta"].pop("owner"))


def _l6(t):
    def untag(doc):
        for c in _models(doc)["stg_customers"]["columns"]:
            if c["name"] == "customer_city":
                c.pop("config")
    _yml(t / "models" / "staging" / "_staging.yml", untag)


def _l7(t):
    (t / "models" / "marts" / "customers" / "kpi_repeat_purchase_rate.sql").write_text(
        "with o as (select customer_unique_id as who from {{ ref('int_orders') }})\nselect who from o",
        encoding="utf-8")


def _l8(t):
    path = t / "governor" / "design.json"
    d = json.loads(path.read_text(encoding="utf-8"))
    next(k for k in d["kpis"] if k["id"] == "net_revenue")["mapping"]["delivered_order"] = "order_status <> 'canceled'"
    path.write_text(json.dumps(d), encoding="utf-8")


def _l9(t):
    _edit(t / "models" / "marts" / "sales" / "kpi_aov.sql", "SELECT order_id AS order_id",
          "SELECT UPPER(order_id) AS order_id")


@pytest.mark.parametrize("rule, model, breaker", [
    ("L1", "orphan", _l1), ("L2", "kpi_gmv", _l2), ("L3", "int_orders", _l3), ("L4", "stg_orders", _l4),
    ("L5", "kpi_gmv", _l5), ("L6", "stg_customers", _l6), ("L7", "kpi_repeat_purchase_rate", _l7),
    ("L8", "kpi_net_revenue", _l8), ("L9", "kpi_aov", _l9)])
def test_each_rule_fires_on_a_crafted_bad_project(tmp_path, good, policy, rule, model, breaker):
    t = _project(tmp_path, good)
    breaker(t)
    found = _check(t, policy)
    hits = [f for f in found if f.rule == rule and f.target == model]
    assert hits, [f.line() for f in found]
    assert all(f.severity == SEVERITY[rule] for f in hits)
    assert set(hits[0].model_dump()) == {"rule", "severity", "target", "problem"}


def test_l4_composite_key_test_missing(tmp_path, good, policy):
    t = _project(tmp_path, good)
    (t / "tests" / "stg_reviews__primary_key.sql").unlink()
    assert any(f.rule == "L4" and f.target == "stg_reviews" for f in _check(t, policy))


def test_l8_and_l9_on_a_cast_in_gold(tmp_path, good, policy):
    t = _project(tmp_path, good)
    _edit(t / "models" / "marts" / "sales" / "kpi_gmv.sql", "SELECT", "SELECT CAST(1 AS int) AS x,")
    rules = {(f.rule, f.target) for f in _check(t, policy)}
    assert {("L8", "kpi_gmv"), ("L9", "kpi_gmv")} <= rules


def test_l8_hash_mismatch_and_missing_design(tmp_path, good, policy):
    t = _project(tmp_path, good)
    _yml(t / "models" / "marts" / "sales" / "_sales.yml",
         lambda doc: _models(doc)["kpi_aov"]["config"]["meta"].update(template_sha256="0" * 64))
    (t / "governor" / "design.json").unlink()
    probs = [f.problem for f in _check(t, policy) if f.rule == "L8" and f.target == "kpi_aov"]
    assert any("template_sha256" in p for p in probs) and any("design.json is missing" in p for p in probs)


def test_blueprint_exception_silences_a_rule(tmp_path, good, policy):
    t = _project(tmp_path, good)
    _l9(t)
    bp = load_blueprint(ROOT / "knowledge" / "blueprint.md").model_copy(deep=True)
    bp.exceptions.append(BlueprintException(rule="L9", target="kpi_aov", reason="test", owner="amir"))
    found = gold.check_project(t, CATALOGUE, policy, blueprint=bp)
    assert not [f for f in found if f.rule == "L9"]


# ---- gap report ----

def test_gap_report(tmp_path, good):
    path = gold.write_gaps(tmp_path, good)
    text = path.read_text(encoding="utf-8")
    assert path == tmp_path / "governor" / "gaps.md"
    assert "## conversion_rate" in text and "## gross_margin" in text and "## gmv" not in text
    assert "unit cost per product" in text and "web analytics such as GA4" in text and "Next step:" in text


# ---- stale files and the staging guard ----

def test_stale_models_are_removed_before_writing(tmp_path, good):
    t = tmp_path / "t"
    init_target(t, "shop")
    stale = [t / "models" / "staging" / "stg_old.sql", t / "models" / "intermediate" / "int_old.sql",
             t / "models" / "staging" / "_old.yml", t / "models" / "marts" / "finance" / "kpi_gross_margin.sql",
             t / "models" / "marts" / "finance" / "_finance.yml", t / "models" / "marts" / "customers" / "kpi_gmv.sql",
             t / "tests" / "stg_old__primary_key.sql"]
    for p in stale:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("select 1", encoding="utf-8")
    keep = t / "models" / "staging" / "README.md"
    keep.write_text("notes", encoding="utf-8")
    st = silver.write_silver(t, good, FakeBuildLLM({"intermediate": GOOD_SILVER}))
    assert not any(p.exists() for p in stale) and keep.exists()
    assert not (t / "models" / "marts" / "finance").exists()
    assert "models/staging/stg_old.sql" in st["pruned"]
    assert (t / "models" / "staging" / "stg_orders.sql").is_file()
    # a later design without int_order_reviews (and its KPI) drops both files on the next write
    gold.write_gold(t, good, CATALOGUE)
    smaller = json.loads(json.dumps(good))
    smaller["silver_models"] = [m for m in smaller["silver_models"] if m["name"] != "int_order_reviews"]
    smaller["kpis"] = [k for k in smaller["kpis"] if k["id"] != "avg_review_score"]
    gold.write_gold(t, smaller, CATALOGUE)
    assert not (t / "models" / "intermediate" / "int_order_reviews.sql").exists()
    assert not (t / "models" / "marts" / "customer_experience").exists()


class StagingFailsDbt:
    """stg_orders fails in dbt; everything else succeeds."""

    def __init__(self, design):
        self.design, self.runs = Proposal.model_validate(design), 0

    def __call__(self, target, args):
        self.runs += 1
        res = [{"unique_id": f"model.shop.{m.name}", "status": "error" if m.name == "stg_orders" else "success",
                "message": "invalid input syntax for type timestamp: \"x\"" if m.name == "stg_orders" else "OK"}
               for m in self.design.silver_models]
        return DbtResult(False, 1, res, "")

    def columns(self, names):
        return {m.name: m.column_names() for m in self.design.silver_models}


def test_failing_staging_model_escalates_without_repair(tmp_path, good):
    init_target(tmp_path, "shop")
    dbt = StagingFailsDbt(good)
    llm = FakeBuildLLM({"intermediate": GOOD_SILVER, "repair": {"stg_orders": ["select 1"]}})
    res = silver.build_silver(tmp_path, good, llm, runner=dbt, inspector=dbt.columns)
    assert res.status == silver.ESCALATED and res.repairs == 0 and dbt.runs == 1
    assert res.escalated["model"] == "stg_orders" and "invalid input syntax" in res.escalated["error"]
    assert "new design" in res.escalated["fix"] or "design gate" in res.escalated["fix"]
    assert not [k for k, _ in llm.prompts if k == "repair"]
    assert "select 1" not in (tmp_path / "models" / "staging" / "stg_orders.sql").read_text(encoding="utf-8")


def test_refused_staging_sql_escalates_before_dbt(tmp_path, good):
    init_target(tmp_path, "shop")
    bad = json.loads(json.dumps(good))
    bad["silver_models"][0]["columns"][0]["expr"] = "order_id from x; drop table y; select 1"
    llm = FakeBuildLLM({"intermediate": GOOD_SILVER, "repair": {"stg_orders": ["select 1"]}})
    res = silver.build_silver(tmp_path, bad, llm, runner=_no_dbt, inspector=lambda n: {})
    assert res.status == silver.ESCALATED and res.escalated["model"] == "stg_orders" and res.repairs == 0


def test_repair_never_touches_staging(tmp_path, good):
    init_target(tmp_path, "shop")
    st = silver.write_silver(tmp_path, good, FakeBuildLLM({"intermediate": GOOD_SILVER}))
    st["failures"] = {"stg_orders": "boom"}
    llm = FakeBuildLLM({"repair": {"stg_orders": ["select 1"]}})
    silver.repair_silver(tmp_path, good, llm, st)
    assert st["repairs"] == 0 and not llm.prompts


def _no_dbt(target, args):
    raise AssertionError("dbt must not run")


# ---- the graph to built / blueprint_failed (offline) ----

class FakeDbt:
    """Silver and gold succeed; every test passes."""

    def __init__(self, design):
        self.design, self.calls = Proposal.model_validate(design), []

    def __call__(self, target, args):
        self.calls.append(args)
        if "marts" in args:
            names = [gold.model_name(k.id) for k in gold.built_kpis(self.design)]
            res = [{"unique_id": f"model.shop.{n}", "status": "success", "message": "SELECT 3"} for n in names]
            res += [{"unique_id": f"test.shop.not_null_{n}_month.abc", "status": "pass", "message": None}
                    for n in names if n != "kpi_repeat_purchase_rate"]
        else:
            res = [{"unique_id": f"model.shop.{m.name}", "status": "success", "message": "OK"}
                   for m in self.design.silver_models]
            res += [{"unique_id": f"test.shop.unique_{m.name}_x.abc", "status": "pass", "message": None}
                    for m in self.design.silver_models]
        return DbtResult(True, 0, res, "")

    def columns(self, names):
        return {m.name: m.column_names() for m in self.design.silver_models}


def _approve(tmp_path, profile, good, policy_file=None, rows=None):
    dbt = FakeDbt(good)
    kw = {"checkpoints": tmp_path / "cp.sqlite", "dbt_runner": dbt, "inspector": dbt.columns,
          "row_counter": rows or (lambda names: {n: 3 for n in names})}
    extra = {"policy": policy_file} if policy_file else {}
    out = graph.start(tmp_path / "t", "shop", FakeBuildLLM({"propose": [json.dumps(good)]}), profile=profile,
                      **extra, **kw)
    a = graph.approve(out["thread_id"], "amir", FakeBuildLLM({"intermediate": GOOD_SILVER}), **kw)
    return a, dbt


def test_approve_builds_gold_offline(tmp_path, profile, good):
    a, dbt = _approve(tmp_path, profile, good)
    assert a["status"] == "built" and sorted(a["kpis_built"]) == sorted(BUILT)
    assert a["gaps"] == ["conversion_rate", "gross_margin"] and a["repairs"] == 0 and a["blueprint"] == []
    assert a["tests_passed"] == 7 + 7 and dbt.calls[-1] == ["build", "--select", "marts"]
    t = tmp_path / "t"
    summary = json.loads((t / "governor" / "build.json").read_text(encoding="utf-8"))
    assert summary["status"] == "built" and {k["id"]: k["rows"] for k in summary["kpis_built"]} == {k: 3 for k in BUILT}
    assert summary["tests_passed"] == {"silver": 7, "gold": 7, "total": 14}
    assert [g["id"] for g in summary["gaps"]] == ["conversion_rate", "gross_margin"]
    assert summary["cost"]["llm_calls"] == 4 and "fake" in summary["cost"]["by_model"]
    assert (t / "governor" / "gaps.md").is_file()


def test_high_blueprint_finding_stops_before_gold_dbt(tmp_path, profile, good):
    pol = tmp_path / "policy.yaml"
    pol.write_text(yaml.safe_dump({**yaml.safe_load((ROOT / "knowledge" / "shop" / "policy.yaml").read_text(
        encoding="utf-8")), "gmv": "secret"}), encoding="utf-8")
    a, dbt = _approve(tmp_path, profile, good, policy_file=pol)
    assert a["status"] == "blueprint_failed" and a["kpis_built"] == []
    assert any(f["rule"] == "L7" and f["target"] == "kpi_gmv" and f["severity"] == "high" for f in a["blueprint"])
    assert not any("marts" in c for c in dbt.calls)
    assert json.loads((tmp_path / "t" / "governor" / "build.json").read_text(encoding="utf-8"))["status"] == "blueprint_failed"


def test_failing_gold_model_escalates(tmp_path, profile, good):
    class GoldFails(FakeDbt):
        def __call__(self, target, args):
            if "marts" in args:
                self.calls.append(args)
                return DbtResult(False, 1, [{"unique_id": "model.shop.kpi_aov", "status": "error",
                                             "message": "division by zero"}], "")
            return super().__call__(target, args)

    dbt = GoldFails(good)
    kw = {"checkpoints": tmp_path / "cp.sqlite", "dbt_runner": dbt, "inspector": dbt.columns,
          "row_counter": lambda names: {}}
    out = graph.start(tmp_path / "t", "shop", FakeBuildLLM({"propose": [json.dumps(good)]}), profile=profile, **kw)
    a = graph.approve(out["thread_id"], "amir", FakeBuildLLM({"intermediate": GOOD_SILVER}), **kw)
    assert a["status"] == "escalated" and a["escalated"]["model"] == "kpi_aov" and "division" in a["escalated"]["error"]


# ---- live: the full sample run against independent values ----

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


INVALID = {"canceled", "unavailable"}


def _read(name):
    with (SAMPLE / f"{name}.csv").open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def expected_values():
    """The five order-level KPIs by month and the repeat purchase rate, from the CSVs with plain Python."""
    orders = {o["order_id"]: o for o in _read("olist_orders_dataset")}
    person = {c["customer_id"]: c["customer_unique_id"] for c in _read("olist_customers_dataset")}
    gmv, net, price, order_set = defaultdict(float), defaultdict(float), defaultdict(float), defaultdict(set)
    for it in _read("olist_order_items_dataset"):
        o = orders.get(it["order_id"])
        if o is None:
            continue
        month = o["order_purchase_timestamp"][:7]
        if o["order_status"] not in INVALID:
            gmv[month] += float(it["price"]) + float(it["freight_value"])
            price[month] += float(it["price"])
            order_set[month].add(o["order_id"])
        if o["order_status"] == "delivered":
            net[month] += float(it["price"])
    aov = {m: price[m] / len(order_set[m]) for m in price}
    on_n, on_d = defaultdict(int), defaultdict(int)
    for o in orders.values():
        got, promised = o["order_delivered_customer_date"], o["order_estimated_delivery_date"]
        if o["order_status"] == "delivered" and got and promised:
            month = o["order_purchase_timestamp"][:7]
            on_d[month] += 1
            on_n[month] += got[:10] <= promised[:10]
    latest = {}
    for r in _read("olist_order_reviews_dataset"):
        key = (r["review_answer_timestamp"], r["review_id"])
        if r["order_id"] not in latest or key > (latest[r["order_id"]]["review_answer_timestamp"], latest[r["order_id"]]["review_id"]):
            latest[r["order_id"]] = r
    score_sum, score_n = defaultdict(float), defaultdict(int)
    for oid, r in latest.items():
        if oid in orders:
            month = orders[oid]["order_purchase_timestamp"][:7]
            score_sum[month] += int(r["review_score"])
            score_n[month] += 1
    per_person = defaultdict(set)
    for o in orders.values():
        if o["order_status"] not in INVALID and o["customer_id"] in person:
            per_person[person[o["customer_id"]]].add(o["order_id"])
    repeat = sum(1 for v in per_person.values() if len(v) >= 2) / len(per_person)
    return {"gmv": dict(gmv), "net_revenue": dict(net), "aov": aov,
            "on_time_delivery_rate": {m: on_n[m] / on_d[m] for m in on_d},
            "avg_review_score": {m: score_sum[m] / score_n[m] for m in score_n}}, repeat


@pytest.mark.skipif(not _raw_ready(), reason="needs GOVERNOR_BUILD_PASSWORD and the Olist tables in raw")
def test_live_sample_build_matches_independent_values(tmp_path, profile, good):
    import psycopg

    from governor.build.__main__ import raw_tables
    from governor.build.workspace import build_dsn, write_sources

    t = tmp_path / "t"
    init_target(t, "shop")
    write_sources(t, raw_tables())
    kw = {"checkpoints": tmp_path / "cp.sqlite"}
    out = graph.start(t, "shop", FakeBuildLLM({"propose": [json.dumps(good)]}), profile=profile, **kw)
    a = graph.approve(out["thread_id"], "amir", FakeBuildLLM(SILVER), **kw)
    assert a["status"] == "built", a
    assert sorted(a["kpis_built"]) == sorted(BUILT) and a["repairs"] == 1
    want, repeat = expected_values()
    with psycopg.connect(build_dsn()) as c:
        for kpi, values in want.items():
            rows = c.execute(f"select to_char(month, 'YYYY-MM'), {kpi}::float8 from dev_governor.kpi_{kpi}").fetchall()
            got = {m: v for m, v in rows if v is not None}
            assert set(got) == set(values), kpi
            assert all(abs(got[m] - values[m]) < 1e-6 for m in values), (kpi, got, values)
        got_repeat = c.execute("select repeat_purchase_rate::float8 from dev_governor.kpi_repeat_purchase_rate").fetchone()[0]
    assert abs(got_repeat - repeat) < 1e-6
    summary = json.loads((t / "governor" / "build.json").read_text(encoding="utf-8"))
    assert all(k["rows"] and k["rows"] > 0 for k in summary["kpis_built"])
