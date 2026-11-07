"""Design proposal: prompt contents, every validation code on a minimal bad proposal, the design report, decisions."""
import csv
import datetime as dt
import json
import re
from pathlib import Path

import pytest

from governor.build import design
from governor.build.graph import record_decisions
from governor.build.llm import FakeBuildLLM, LLMOutputError
from governor.build.models import Finding, Proposal
from governor.core.catalogue import load_approved, load_blueprint, load_kpis
from governor.core.paths import KNOWLEDGE

CATALOGUE = load_kpis(KNOWLEDGE / "kpis.yaml")
BLUEPRINT = load_blueprint(KNOWLEDGE / "blueprint.md")
ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "testbed" / "sample"
POLICY = ROOT / "knowledge" / "shop" / "policy.yaml"


def _model(doc, name):
    return next(m for m in doc["silver_models"] if m["name"] == name)


def _kpi(doc, kid):
    return next(k for k in doc["kpis"] if k["id"] == kid)


def _col(model, name):
    return next(c for c in model["columns"] if c["name"] == name)


def _codes(doc, profile, policy):
    return design.validate(doc, profile, CATALOGUE, policy)


# ---- the fixture ----

def test_sample_design_is_valid(good, profile, policy):
    assert _codes(good, profile, policy) == []
    p = Proposal.model_validate(good)
    built = {k.id for k in p.kpis if k.decision == "build"}
    assert built == {"gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score",
                     "repeat_purchase_rate", "cohort_retention", "historical_clv"}
    assert {k.id for k in p.kpis if k.decision == "decline"} == {"conversion_rate", "gross_margin"}
    assert {m.name for m in p.silver_models} == {"stg_orders", "stg_order_items", "stg_customers", "stg_reviews",
                                                  "int_order_lines", "int_orders", "int_order_reviews"}


# ---- each code on a minimal bad proposal ----

def _unknown_table(d):
    _model(d, "stg_orders")["source_table"] = "olist_nope"


def _unknown_column(d):
    _col(_model(d, "stg_orders"), "purchased_at")["expr"] = "CAST(order_purchased AS timestamp)"


def _staging_with_refs(d):
    _model(d, "stg_orders")["refs"] = ["stg_customers"]


def _intermediate_with_source(d):
    _model(d, "int_orders")["source_table"] = "olist_orders_dataset"


def _intermediate_without_refs(d):
    _model(d, "int_orders")["refs"] = []


def _ref_not_silver(d):
    _model(d, "int_orders")["refs"] = ["stg_orders", "kpi_gmv"]


def _gold_folder(d):
    _model(d, "int_orders")["folder"] = "marts"


def _duplicate(d):
    d["silver_models"].append(json.loads(json.dumps(_model(d, "stg_orders"))))


def _no_key(d):
    _model(d, "stg_orders")["primary_key"] = []


def _undeclared_key(d):
    _model(d, "int_orders")["primary_key"] = ["order_key"]


def _pii_staging(d):
    _col(_model(d, "stg_customers"), "customer_unique_id")["pii"] = False


def _pii_through_expr(d):
    _col(_model(d, "stg_customers"), "customer_state")["expr"] = "UPPER(customer_state)"
    _col(_model(d, "stg_customers"), "customer_state")["pii"] = False


def _pii_intermediate(d):
    _col(_model(d, "int_orders"), "customer_unique_id")["pii"] = False


def _kpi_unknown(d):
    d["kpis"].append({"id": "nps", "decision": "decline", "reason": "no survey",
                      "gap": {"missing": ["surveys"], "typical_sources": ["survey tool"], "next_step": "load surveys"}})


def _kpi_missing(d):
    d["kpis"] = [k for k in d["kpis"] if k["id"] != "aov"]


def _kpi_duplicate(d):
    d["kpis"].append(json.loads(json.dumps(_kpi(d, "gmv"))))


def _mapping_unfilled(d):
    del _kpi(d, "gmv")["mapping"]["freight"]


def _mapping_unknown_name(d):
    _kpi(d, "gmv")["mapping"]["order_id"] = "order_id"


def _mapping_no_domain(d):
    _kpi(d, "gmv")["domain"] = None


def _mapping_unknown_model(d):
    _kpi(d, "on_time_delivery_rate")["mapping"]["orders"] = "int_deliveries"


def _mapping_unknown_column(d):
    _kpi(d, "gmv")["mapping"]["item_price"] = "no_such_column"


def _mapping_expression_column(d):
    _kpi(d, "net_revenue")["mapping"]["delivered_order"] = "delivery_status = 'done'"


def _decline_no_gap(d):
    _kpi(d, "gross_margin").pop("gap")


def _decline_empty_next_step(d):
    _kpi(d, "conversion_rate")["gap"]["next_step"] = " "


def _decline_no_reason(d):
    _kpi(d, "conversion_rate")["reason"] = ""


def _expr_statement(d):
    _col(_model(d, "stg_orders"), "order_status")["expr"] = "select order_status from raw.olist_orders_dataset"


def _key_not_unique(d):
    _model(d, "stg_orders")["primary_key"] = ["order_status"]


CASES = [
    ("UNKNOWN_SOURCE_TABLE", "stg_orders", _unknown_table),
    ("UNKNOWN_SOURCE_COLUMN", "stg_orders.purchased_at", _unknown_column),
    ("BAD_FOLDER", "stg_orders", _staging_with_refs),
    ("BAD_FOLDER", "int_orders", _intermediate_with_source),
    ("BAD_FOLDER", "int_orders", _intermediate_without_refs),
    ("BAD_FOLDER", "int_orders", _ref_not_silver),
    ("BAD_FOLDER", "int_orders", _gold_folder),
    ("DUPLICATE_MODEL", "stg_orders", _duplicate),
    ("MISSING_KEY", "stg_orders", _no_key),
    ("MISSING_KEY", "int_orders", _undeclared_key),
    ("PII_UNTAGGED", "stg_customers.customer_unique_id", _pii_staging),
    ("PII_UNTAGGED", "stg_customers.customer_state", _pii_through_expr),
    ("PII_UNTAGGED", "int_orders.customer_unique_id", _pii_intermediate),
    ("KPI_UNKNOWN", "kpi.nps", _kpi_unknown),
    ("KPI_MISSING", "kpi.aov", _kpi_missing),
    ("KPI_DUPLICATE", "kpi.gmv", _kpi_duplicate),
    ("MAPPING_INCOMPLETE", "kpi.gmv", _mapping_unfilled),
    ("MAPPING_INCOMPLETE", "kpi.gmv", _mapping_unknown_name),
    ("MAPPING_INCOMPLETE", "kpi.gmv", _mapping_no_domain),
    ("MAPPING_UNKNOWN_MODEL", "kpi.on_time_delivery_rate", _mapping_unknown_model),
    ("MAPPING_UNKNOWN_COLUMN", "kpi.gmv", _mapping_unknown_column),
    ("MAPPING_UNKNOWN_COLUMN", "kpi.net_revenue", _mapping_expression_column),
    ("DECLINE_WITHOUT_GAP", "kpi.gross_margin", _decline_no_gap),
    ("DECLINE_WITHOUT_GAP", "kpi.conversion_rate", _decline_empty_next_step),
    ("DECLINE_WITHOUT_GAP", "kpi.conversion_rate", _decline_no_reason),
    ("EXPR_UNPARSEABLE", "stg_orders.order_status", _expr_statement),
    ("KEY_NOT_UNIQUE", "stg_orders", _key_not_unique),
]


@pytest.mark.parametrize(("code", "subject", "mutate"), CASES, ids=[f"{c[0]}-{c[2].__name__}" for c in CASES])
def test_code_fires(code, subject, mutate, good, profile, policy):
    mutate(good)
    found = _codes(good, profile, policy)
    hits = [f for f in found if f.code == code]
    assert hits, [f.line() for f in found]
    assert any(f.subject == subject for f in hits), [f.line() for f in hits]
    assert all(f.problem.strip() for f in found)


def test_every_validation_code_has_a_case():
    covered = {c[0] for c in CASES} | {"PROPOSAL_UNPARSEABLE"}  # raised by the graph, tested in test_graph
    assert covered == set(design.CODES)


# ---- keys against the profile (batch2c section 19) ----

def _table(profile, name):
    return next(t for t in profile["tables"] if t["name"] == name)


def _key_findings(doc, profile, policy):
    return [f for f in _codes(doc, profile, policy) if f.code == "KEY_NOT_UNIQUE"]


def test_key_not_unique_flags_non_candidate_key(good, profile, policy):
    _model(good, "stg_orders")["primary_key"] = ["order_status"]
    hits = _key_findings(good, profile, policy)
    assert [f.subject for f in hits] == ["stg_orders"]
    assert "[order_id]" in hits[0].problem and "olist_orders_dataset" in hits[0].problem
    # names and counts only: no raw value as a whole token
    assert [v for v in _sample_values()
            if re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", hits[0].problem)] == []


def test_key_superset_of_candidate_key_is_accepted(good, profile, policy):
    assert ["order_id", "order_item_id"] in _table(profile, "olist_order_items_dataset")["candidate_keys"]
    assert _key_findings(good, profile, policy) == []  # the candidate pair (order_item_id through a cast)
    _model(good, "stg_order_items")["primary_key"] = ["order_id", "order_item_id", "seller_id"]
    assert _key_findings(good, profile, policy) == []  # a superset of a unique key is unique
    _model(good, "stg_order_items")["primary_key"] = ["order_id"]  # one half of the pair is not
    assert [f.subject for f in _key_findings(good, profile, policy)] == ["stg_order_items"]


def test_key_on_table_without_candidate_key_is_flagged(good, profile, policy):
    _table(profile, "olist_order_reviews_dataset")["candidate_keys"] = []
    hits = _key_findings(good, profile, policy)
    assert [f.subject for f in hits] == ["stg_reviews"]
    assert "olist_order_reviews_dataset has no unique column or column pair" in hits[0].problem


def test_computed_key_is_flagged(good, profile, policy):
    _col(_model(good, "stg_orders"), "order_id")["expr"] = "UPPER(order_id)"
    hits = _key_findings(good, profile, policy)
    assert [f.subject for f in hits] == ["stg_orders.order_id"]
    assert "key column 'order_id' is computed" in hits[0].problem
    # a bare column, a cast of one (either syntax) and a null expr are not computed
    for expr in ("order_id", "CAST(order_id AS text)", "order_id::text", None):
        _col(_model(good, "stg_orders"), "order_id")["expr"] = expr
        assert _key_findings(good, profile, policy) == [], expr


def test_unbuildable_kpi_marked_build_is_caught(good, profile, policy):
    k = _kpi(good, "gross_margin")
    k.clear()
    k.update({"id": "gross_margin", "decision": "build", "domain": "finance",
              "mapping": {"order_lines": "int_order_lines", "product_costs": "stg_product_costs",
                          "purchased_at": "purchased_at", "item_price": "item_price", "product_key": "product_id",
                          "delivered_order": "order_status = 'delivered'", "cost_product_key": "product_id",
                          "unit_cost": "unit_cost"}})
    codes = {f.code for f in _codes(good, profile, policy)}
    assert "MAPPING_UNKNOWN_MODEL" in codes


# ---- the prompt ----

def _sample_values() -> set[str]:
    out = set()
    for f in SAMPLE.glob("*.csv"):
        with f.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                out |= {v.strip() for v in row.values() if v and len(v.strip()) >= 5}
    return out


def test_prompt_has_no_raw_values_and_pii_as_counts(profile, good):
    prompt = design.build_prompt(profile, CATALOGUE, BLUEPRINT, [], None)
    section = prompt.split("## Profile")[1].split("## Blueprint")[0]
    values = _sample_values()

    def found(v, text):  # a whole token, so 'delivered' inside a column name does not count
        return re.search(rf"(?<![\w-]){re.escape(v)}(?![\w-])", text) is not None

    assert sorted(v for v in values if found(v, section)) == []
    # the catalogue's own words ('canceled', 'delivered' in definitions) are human-owned text, not raw data
    catalogue_text = json.dumps(design.catalogue_for_prompt(CATALOGUE))
    assert sorted(v for v in values if found(v, prompt) and not found(v, catalogue_text)) == []
    body = json.loads(section.split("```json")[1].split("```")[0])
    for t in body["tables"]:
        for c in t["columns"]:
            assert "min" not in c and "max" not in c
            if c.get("pii"):
                assert set(c) == {"name", "pii", "null_rate", "distinct"}
    for k in CATALOGUE.kpis:
        assert k.id in prompt and k.template_sql.strip().splitlines()[0] not in prompt
    for r in BLUEPRINT.rules:
        assert r.text in prompt


def test_prompt_on_repair_carries_findings_previous_and_note(profile, good):
    f = Finding(code="MISSING_KEY", subject="stg_orders", problem="no primary_key")
    prompt = design.build_prompt(profile, CATALOGUE, BLUEPRINT, [], [f], previous=good, note="use int_orders")
    assert "MISSING_KEY stg_orders: no primary_key" in prompt
    assert "use int_orders" in prompt and "Your previous proposal" in prompt
    first = design.build_prompt(profile, CATALOGUE, BLUEPRINT, [], None)
    assert "previous proposal" not in first.lower().split("## profile")[1]


def test_propose_is_one_structured_call(profile, good):
    llm = FakeBuildLLM({"propose": [json.dumps(good)]})
    p = design.propose(profile, CATALOGUE, BLUEPRINT, [], llm)
    assert isinstance(p, Proposal) and len(llm.prompts) == 1 and llm.prompts[0][0] == "propose"
    assert llm.calls[0]["cost_usd"] == 0.0
    with pytest.raises(LLMOutputError):
        design.propose(profile, CATALOGUE, BLUEPRINT, [], FakeBuildLLM({"propose": ["not json"]}))


# ---- the report ----

SECTIONS = ["## Silver models", "## KPIs", "## Gap report", "## Assumptions", "## Validation findings", "## Commands"]


def test_report_has_every_section_in_order(good):
    text = design.render_report(good, [], "thread-123")
    first = text.splitlines()[2]
    assert first.startswith("7 silver model(s), 8 KPI(s) to build, 2 KPI(s) declined")
    positions = [text.index(s) for s in SECTIONS]
    assert positions == sorted(positions)
    for k in CATALOGUE.kpis:
        assert f"| {k.id} |" in text
    assert "stg_customers | staging | raw.olist_customers_dataset | customer_id |" in text
    assert "unit cost per product" in text and "supplier invoices" in text and "load a product cost table" in text
    assert "order_status values 'canceled'" in text
    assert "None: the proposal passed every check." in text
    assert "python -m governor.build approve thread-123 --by <name>" in text
    assert 'python -m governor.build reject thread-123 --note "<what to change>"' in text
    assert "NOT IN ('canceled', 'unavailable')" in text


def test_report_with_findings_is_not_approvable(good):
    f = Finding(code="PII_UNTAGGED", subject="stg_customers.customer_unique_id", problem="reads PII")
    text = design.render_report(good, [f], "t1")
    assert "| PII_UNTAGGED | stg_customers.customer_unique_id | reads PII |" in text
    assert "approve t1" not in text and "cannot be approved" in text
    assert "## Gap report" in design.render_report(None, [f], "t1")


# ---- recorded decisions ----

def test_record_decisions_appends_and_supersedes(tmp_path, good):
    p = Proposal.model_validate(good)
    path = record_decisions(tmp_path, p, "amir", dt.date(2026, 11, 5), "t1")
    a = load_approved(path)
    n = sum(len(k.mapping) for k in p.kpis if k.decision == "build")
    assert len(a.decisions) == n
    d = next(d for d in a.decisions if d.subject == "kpi.repeat_purchase_rate.customer_key")
    assert (d.kind, d.value, d.approved_by, d.approved_on) == ("column_mapping", "customer_unique_id", "amir",
                                                               dt.date(2026, 11, 5))
    assert "t1" in d.source
    # approving again replaces the same entries and keeps others
    text = path.read_text(encoding="utf-8").replace("decisions:\n", "decisions:\n- {id: keep-me, kind: correction, "
                                                    "subject: x, reason: y, approved_by: z, approved_on: 2026-11-01}\n", 1)
    path.write_text(text, encoding="utf-8")
    record_decisions(tmp_path, p, "sam", dt.date(2026, 11, 6), "t2")
    a2 = load_approved(path)
    assert len(a2.decisions) == n + 1 and a2.decisions[0].id == "keep-me"
    assert {d.approved_by for d in a2.decisions[1:]} == {"sam"}


def test_policy_fixture_is_the_shop_policy(policy):
    assert POLICY.is_file() and "customer_unique_id" in policy
