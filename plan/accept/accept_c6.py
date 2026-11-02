"""C6 acceptance: KPI catalogue, layer blueprint and approved-decisions loaders, validation and rendering."""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import ROOT, check, finish, guarded, py_json, pytest_check  # noqa: E402

AOV = """version: 1
kpis:
  - id: aov
    label: Average order value
    status: proposed
    definition: Item value of valid orders divided by the number of valid orders, per month.
    grain: month
    relations:
      orders: {description: one row per order}
    inputs:
      order_id: {relation: orders, type: key}
      order_value: {relation: orders, type: money}
      order_date: {relation: orders, type: timestamp}
      valid_order: {relation: orders, type: boolean}
    template_sql: |
      SELECT date_trunc('month', {order_date}) AS month, SUM({order_value}) / COUNT(DISTINCT {order_id}) AS aov
      FROM {orders} WHERE {valid_order} GROUP BY 1
    requires: [orders]
    prerequisites: []
    sources: []
"""

BAD = {
    "duplicate_id": AOV + AOV.split("kpis:\n", 1)[1],
    "bad_status": AOV.replace("status: proposed", "status: certified"),
    "undeclared_placeholder": AOV.replace("GROUP BY 1", "AND {region} GROUP BY 1"),
    "unknown_relation": AOV.replace("order_id: {relation: orders, type: key}", "order_id: {relation: customers, type: key}"),
}

PROBE = r'''
import json, os
from pathlib import Path
from governor.core import catalogue as c
d = Path(os.environ["C6_DIR"])
out = {}
cat = c.load_kpis(d / "ok.yaml")
out["ok_loads"] = len(cat.kpis) == 1
for name in ["duplicate_id", "bad_status", "undeclared_placeholder", "unknown_relation"]:
    try:
        c.load_kpis(d / f"{name}.yaml"); out[name] = "loaded"
    except Exception as e:
        out[name] = "aov" in str(e).lower() or name == "duplicate_id" and "dup" in str(e).lower()
kpi = cat.kpis[0]
full = {"orders": "analytics.orders", "order_id": "order_id", "order_value": "item_value",
        "order_date": "purchased_at", "valid_order": "is_valid"}
sql = c.render(kpi, full)
out["render_ok"] = "{" not in sql and "analytics.orders" in sql
try:
    c.render(kpi, {k: v for k, v in full.items() if k != "order_value"}); out["render_missing"] = "rendered"
except Exception:
    out["render_missing"] = "refused"
try:
    c.render(kpi, dict(full, extra="x")); out["render_unknown"] = "rendered"
except Exception:
    out["render_unknown"] = "refused"
bp = c.load_blueprint(Path("knowledge/blueprint.md")).model_dump()
out["layers"] = {k: v.get("dbt") for k, v in bp.get("layers", {}).items()}
out["rules"] = {r["id"]: r["severity"] for r in bp.get("rules", [])}
out["exceptions"] = bp.get("exceptions")
k = c.load_kpis(Path("knowledge/kpis.yaml")).model_dump()
out["kpis_real"] = k.get("kpis")
a = c.load_approved(Path("knowledge/approved.yaml")).model_dump()
out["decisions_real"] = a.get("decisions")
print(json.dumps(out, default=str))
'''

RULES = {"L1": "high", "L2": "high", "L3": "high", "L4": "high", "L5": "medium", "L6": "high", "L7": "high", "L8": "high", "L9": "low"}


def probe():
    for rel in ("src/governor/core/catalogue.py", "knowledge/blueprint.md", "knowledge/kpis.yaml", "knowledge/approved.yaml"):
        check(f"{rel} exists", (ROOT / rel).is_file(), "missing")
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "ok.yaml").write_text(AOV, encoding="utf-8")
        for name, text in BAD.items():
            (Path(d) / f"{name}.yaml").write_text(text, encoding="utf-8")
        import os
        out, err = py_json(PROBE, env=dict(os.environ, C6_DIR=d))
    if not check("catalogue module runs", out is not None, err):
        return
    check("a valid catalogue loads", out["ok_loads"] is True, "")
    for name in BAD:
        check(f"validation catches {name} and names the KPI", out[name] is True, str(out[name]))
    check("render fills every placeholder", out["render_ok"] is True, "")
    check("render refuses a missing mapping", out["render_missing"] == "refused", out["render_missing"])
    check("render refuses an unknown name", out["render_unknown"] == "refused", out["render_unknown"])
    layers = out["layers"]
    check("blueprint maps bronze/silver/gold to sources, staging+intermediate, marts",
          layers.get("bronze") == ["sources"] and sorted(layers.get("silver") or []) == ["intermediate", "staging"]
          and layers.get("gold") == ["marts"], str(layers))
    check("blueprint rules L1-L9 with the agreed severities", out["rules"] == RULES, str(out["rules"]))
    check("blueprint starts with no exceptions", out["exceptions"] == [], str(out["exceptions"]))
    check("no KPI definitions invented (catalogue empty)", out["kpis_real"] == [], str(out["kpis_real"])[:200])
    check("approved decisions start empty", out["decisions_real"] == [], str(out["decisions_real"])[:200])


guarded("catalogue", probe)
pytest_check("tests/core/test_catalogue.py")
finish("C6")
