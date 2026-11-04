"""KPI catalogue, layer blueprint and approved decisions (design sections 6 to 8)."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from governor.core import catalogue as c
from governor.core.catalogue import CatalogueError

ROOT = Path(__file__).resolve().parents[2]

AOV_YAML = """\
version: 1
kpis:
  - id: aov
    label: Average order value
    status: proposed
    definition: >-
      Item value of valid orders divided by the number of valid orders, per month.
    grain: month
    owner: finance team
    source:
      tier: platform
      ref: https://example.com/shop-platform/glossary#aov
    relations:
      orders: {description: one row per order}
    inputs:
      order_id:    {relation: orders, type: key}
      order_value: {relation: orders, type: money, description: "item price, freight excluded"}
      order_date:  {relation: orders, type: timestamp}
      valid_order: {relation: orders, type: boolean, description: the order counts as a sale}
    template_sql: |
      SELECT date_trunc('month', {order_date}) AS month,
             SUM({order_value}) / COUNT(DISTINCT {order_id}) AS aov
      FROM {orders}
      WHERE {valid_order}
      GROUP BY 1
    requires: [orders]
    prerequisites: []
    sources: []
"""

FULL_MAPPING = {
    "orders": "serve_analyst.orders",
    "order_id": "order_id",
    "order_value": "item_value",
    "order_date": "purchased_at",
    "valid_order": "is_valid",
}


def _aov() -> dict:
    return yaml.safe_load(AOV_YAML)


def _write(tmp_path: Path, data: dict | str, name: str = "kpis.yaml") -> Path:
    p = tmp_path / name
    p.write_text(data if isinstance(data, str) else yaml.safe_dump(data, sort_keys=False), encoding="utf-8")
    return p


def _kpi(data: dict) -> dict:
    return data["kpis"][0]


# --------------------------------------------------------------------------- catalogue


def test_valid_catalogue_loads(tmp_path):
    cat = c.load_kpis(_write(tmp_path, AOV_YAML))
    assert [k.id for k in cat.kpis] == ["aov"]
    dumped = cat.model_dump()
    assert dumped["version"] == 1
    kpi = dumped["kpis"][0]
    assert kpi["inputs"]["order_value"]["relation"] == "orders"
    assert kpi["source"] == {"tier": "platform", "ref": "https://example.com/shop-platform/glossary#aov", "note": None}
    assert cat.get("aov").placeholders() == ["order_date", "order_value", "order_id", "orders", "valid_order"]


def _expect_error(tmp_path, data, *needles):
    with pytest.raises(CatalogueError) as exc:
        c.load_kpis(_write(tmp_path, data))
    text = str(exc.value).lower()
    for n in needles:
        assert n.lower() in text, text
    return text


def test_duplicate_id_rejected(tmp_path):
    data = _aov()
    data["kpis"].append(dict(_kpi(data)))
    _expect_error(tmp_path, data, "duplicate", "aov")


def test_bad_status_rejected(tmp_path):
    data = _aov()
    _kpi(data)["status"] = "certified"
    _expect_error(tmp_path, data, "aov", "status")


def test_undeclared_placeholder_rejected(tmp_path):
    data = _aov()
    _kpi(data)["template_sql"] += "  AND {region}\n"
    _expect_error(tmp_path, data, "aov", "region")


def test_input_with_unknown_relation_rejected(tmp_path):
    data = _aov()
    _kpi(data)["inputs"]["order_id"]["relation"] = "customers"
    _expect_error(tmp_path, data, "aov", "customers")


def test_requires_unknown_relation_rejected(tmp_path):
    data = _aov()
    _kpi(data)["requires"] = ["orders", "payments"]
    _expect_error(tmp_path, data, "aov", "payments")


def test_unknown_key_rejected(tmp_path):
    data = _aov()
    _kpi(data)["formula"] = "x"
    _expect_error(tmp_path, data, "aov", "formula")


def test_kpi_source_tier_validated(tmp_path):
    # an unknown tier is refused
    data = _aov()
    _kpi(data)["source"]["tier"] = "blog"
    _expect_error(tmp_path, data, "aov", "tier")

    # a vendor tier needs a note
    data = _aov()
    _kpi(data)["source"] = {"tier": "vendor", "ref": "Vendor X metrics glossary"}
    _expect_error(tmp_path, data, "aov", "note")
    _kpi(data)["source"]["note"] = "no company, accounting or platform definition exists"
    assert c.load_kpis(_write(tmp_path, data)).kpis[0].source.tier == "vendor"

    # ref must be filled
    data = _aov()
    _kpi(data)["source"]["ref"] = " "
    _expect_error(tmp_path, data, "aov", "ref")

    # every tier in the precedence order is accepted
    for tier in c.SOURCE_PRECEDENCE:
        data = _aov()
        _kpi(data)["source"] = {"tier": tier, "ref": "doc", "note": "n"}
        assert c.load_kpis(_write(tmp_path, data)).kpis[0].source.tier == tier
    assert c.SOURCE_PRECEDENCE == ("company", "accounting", "platform", "vendor")


def test_approved_kpi_needs_owner_and_source(tmp_path):
    data = _aov()
    _kpi(data)["status"] = "approved"
    assert c.load_kpis(_write(tmp_path, data)).kpis[0].status == "approved"

    del _kpi(data)["owner"]
    _expect_error(tmp_path, data, "aov", "owner")

    data = _aov()
    _kpi(data)["status"] = "approved"
    del _kpi(data)["source"]
    _expect_error(tmp_path, data, "aov", "source")

    data = _aov()
    _kpi(data)["owner"] = ""
    _expect_error(tmp_path, data, "aov", "owner")


def test_proposed_draft_may_omit_provenance(tmp_path):
    data = _aov()
    del _kpi(data)["owner"]
    del _kpi(data)["source"]
    kpi = c.load_kpis(_write(tmp_path, data)).kpis[0]
    assert kpi.owner is None and kpi.source is None


def test_unquoted_comma_in_flow_mapping_is_caught(tmp_path):
    # design section 6 writes this unquoted; YAML splits it at the comma
    text = AOV_YAML.replace('"item price, freight excluded"', "item price, freight excluded")
    _expect_error(tmp_path, text, "aov", "freight excluded")


def test_bad_yaml_and_missing_file(tmp_path):
    with pytest.raises(CatalogueError):
        c.load_kpis(_write(tmp_path, "version: 1\nkpis: [\n"))
    with pytest.raises(CatalogueError):
        c.load_kpis(tmp_path / "nope.yaml")


# --------------------------------------------------------------------------- render


def test_render_fills_every_placeholder(tmp_path):
    kpi = c.load_kpis(_write(tmp_path, AOV_YAML)).get("aov")
    sql = c.render(kpi, FULL_MAPPING)
    assert "{" not in sql
    assert "FROM serve_analyst.orders" in sql
    assert "SUM(item_value) / COUNT(DISTINCT order_id)" in sql
    assert "date_trunc('month', purchased_at)" in sql


def test_render_refuses_missing_name(tmp_path):
    kpi = c.load_kpis(_write(tmp_path, AOV_YAML)).get("aov")
    mapping = {k: v for k, v in FULL_MAPPING.items() if k != "order_value"}
    with pytest.raises(CatalogueError, match="order_value"):
        c.render(kpi, mapping)
    with pytest.raises(CatalogueError, match="order_value"):
        c.render(kpi, dict(FULL_MAPPING, order_value="  "))


def test_render_refuses_unknown_name(tmp_path):
    kpi = c.load_kpis(_write(tmp_path, AOV_YAML)).get("aov")
    with pytest.raises(CatalogueError, match="region"):
        c.render(kpi, dict(FULL_MAPPING, region="x"))


def test_render_refuses_placeholder_in_value(tmp_path):
    kpi = c.load_kpis(_write(tmp_path, AOV_YAML)).get("aov")
    assert "{" not in c.render(kpi, FULL_MAPPING)
    for name, value, found in [
        ("order_value", "price * {tax}", "tax"),
        ("order_value", "{order_id}", "order_id"),
        ("orders", "{orders}", "orders"),
    ]:
        with pytest.raises(CatalogueError, match=rf"aov.*{name} -> \{{{found}\}}"):
            c.render(kpi, dict(FULL_MAPPING, **{name: value}))


def test_render_refuses_placeholder_formed_from_fragments(tmp_path):
    # neither the value nor the template holds a placeholder for the other's
    # fragment, but together they form one after substitution
    for template, value, formed in [
        ("SELECT {order_value}b} FROM {orders}\n", "{x", "xb"),
        ("SELECT {{order_value} FROM {orders}\n", "x}", "x"),
    ]:
        data = _aov()
        _kpi(data)["template_sql"] = template
        kpi = c.load_kpis(_write(tmp_path, data)).get("aov")
        with pytest.raises(CatalogueError, match=rf"aov.*still contains placeholders.*'{formed}'"):
            c.render(kpi, {"order_value": value, "orders": "serve_analyst.orders"})


# --------------------------------------------------------------------------- blueprint

BLUEPRINT = """\
---
layers:
  bronze: {dbt: [sources]}
  silver: {dbt: [staging, intermediate]}
  gold: {dbt: [marts]}
rules:
  - {id: L1, severity: high, text: Every model belongs to one layer.}
  - {id: L9, severity: low, text: No type casts in gold.}
exceptions: []
---

# Prose
"""


def test_blueprint_fixture_loads(tmp_path):
    bp = c.load_blueprint(_write(tmp_path, BLUEPRINT, "blueprint.md")).model_dump()
    assert bp["layers"]["silver"]["dbt"] == ["staging", "intermediate"]
    assert [r["id"] for r in bp["rules"]] == ["L1", "L9"]
    assert bp["exceptions"] == []


@pytest.mark.parametrize(
    ("old", "new", "needle"),
    [
        ("{id: L9, severity: low", "{id: L1, severity: low", "duplicate"),
        ("severity: low", "severity: critical", "severity"),
        ("exceptions: []", "exceptions: [{rule: L7, target: fct_x, reason: r, owner: o}]", "l7"),
        ("exceptions: []", "exceptions: [{rule: L1, target: fct_x, reason: '', owner: o}]", "reason"),
        ("gold: {dbt: [marts]}", "gold: {dbt: [staging]}", "staging"),
    ],
)
def test_blueprint_validation(tmp_path, old, new, needle):
    with pytest.raises(CatalogueError) as exc:
        c.load_blueprint(_write(tmp_path, BLUEPRINT.replace(old, new), "blueprint.md"))
    assert needle in str(exc.value).lower()


def test_blueprint_exception_accepted(tmp_path):
    text = BLUEPRINT.replace("exceptions: []", "exceptions: [{rule: L9, target: fct_x, reason: r, owner: o}]")
    bp = c.load_blueprint(_write(tmp_path, text, "blueprint.md"))
    assert bp.exceptions[0].target == "fct_x"


def test_blueprint_needs_front_matter(tmp_path):
    with pytest.raises(CatalogueError, match="front matter"):
        c.load_blueprint(_write(tmp_path, "# no front matter\n", "blueprint.md"))
    with pytest.raises(CatalogueError, match="closed"):
        c.load_blueprint(_write(tmp_path, "---\nlayers: {}\n", "blueprint.md"))


# --------------------------------------------------------------------------- approved decisions

DECISION = {
    "id": "map-customer-key",
    "kind": "column_mapping",
    "subject": "kpi.repeat_purchase_rate.customer_key",
    "value": "raw.olist_customers_dataset.customer_unique_id",
    "reason": "customer_id is created per order",
    "approved_by": "amir",
    "approved_on": "2026-11-05",
    "source": "factory/C6",
}


def test_approved_decision_loads(tmp_path):
    a = c.load_approved(_write(tmp_path, {"version": 1, "decisions": [DECISION]}, "approved.yaml"))
    d = a.model_dump()["decisions"][0]
    assert d["kind"] == "column_mapping"
    assert str(d["approved_on"]) == "2026-11-05"


@pytest.mark.parametrize(
    ("change", "needle"),
    [
        ({"kind": "guess"}, "kind"),
        ({"reason": ""}, "reason"),
        ({"reason": None}, "reason"),
        ({"approved_by": " "}, "approved_by"),
        ({"approved_on": None}, "approved_on"),
        ({"approved_on": "soon"}, "approved_on"),
    ],
)
def test_approved_decision_validation(tmp_path, change, needle):
    bad = dict(DECISION, **change)
    with pytest.raises(CatalogueError) as exc:
        c.load_approved(_write(tmp_path, {"version": 1, "decisions": [bad]}, "approved.yaml"))
    assert needle in str(exc.value)


def test_approved_decision_missing_fields(tmp_path):
    for key in ("reason", "approved_by", "approved_on"):
        bad = {k: v for k, v in DECISION.items() if k != key}
        with pytest.raises(CatalogueError, match=key):
            c.load_approved(_write(tmp_path, {"version": 1, "decisions": [bad]}, "approved.yaml"))
    dup = {"version": 1, "decisions": [DECISION, DECISION]}
    with pytest.raises(CatalogueError, match="duplicate"):
        c.load_approved(_write(tmp_path, dup, "approved.yaml"))


# --------------------------------------------------------------------------- real knowledge files


def test_real_blueprint_loads():
    bp = c.load_blueprint(ROOT / "knowledge" / "blueprint.md").model_dump()
    assert {k: v["dbt"] for k, v in bp["layers"].items()} == {
        "bronze": ["sources"],
        "silver": ["staging", "intermediate"],
        "gold": ["marts"],
    }
    assert {r["id"]: r["severity"] for r in bp["rules"]} == {
        "L1": "high", "L2": "high", "L3": "high", "L4": "high", "L5": "medium",
        "L6": "high", "L7": "high", "L8": "high", "L9": "low",
    }
    assert bp["exceptions"] == []


def test_real_catalogue_and_approved_load():
    real = c.load_kpis(ROOT / "knowledge" / "kpis.yaml")  # filled with the definitions Amir approved on 4 Nov
    assert real.version == 1 and real.kpis
    assert all(k.status == "approved" and k.owner and k.source for k in real.kpis)
    assert c.load_approved(ROOT / "knowledge" / "approved.yaml").model_dump() == {"version": 1, "decisions": []}
