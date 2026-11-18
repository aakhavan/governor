"""Raw-schema profile tests. Type inference and models run offline; the live ones skip without the database."""
import csv
import json
import os
import re
from pathlib import Path

import pytest

from governor.build import __main__ as build_cli
from governor.build.models import ColumnProfile, Profile
from governor.build.profile import PATTERNS, TYPE_ORDER, infer_type, load_policy, profile_schema
from governor.build.workspace import build_dsn

ROOT = Path(__file__).resolve().parents[2]
POLICY = ROOT / "knowledge" / "shop" / "policy.yaml"
SAMPLE = ROOT / "testbed" / "sample"


# ---- offline: type inference ----

@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["1", "2", "-3", "+4", "0"], "integer"),
        (["100.00", "50.00", "7"], "numeric"),
        (["1.5e3", ".5", "-0.25"], "numeric"),
        (["2026-01-03", "2026-12-31"], "date"),
        (["2026-01-03 09:00:00", "2026-01-03T09:30:00.123", "2026-01-03 10:00:00+02:00"], "timestamp"),
        (["2026-01-03 09:00:00", "2026-01-20"], "timestamp"),  # a date mixed in still reads as a timestamp
        (["true", "False", "T", "f"], "boolean"),
        (["01000", "02000"], "text"),  # leading zeros: a code, not a number
        (["ord-0001", "ord-0002"], "text"),
        (["1", "two"], "text"),
        (["1", "", "  ", None, "3"], "integer"),  # empty and blank strings count as null
        (["", None], "text"),
        ([], "text"),
        (["2026-01-03 9:00"], "text"),
    ],
)
def test_infer_type(values, expected):
    assert infer_type(values) == expected


def test_patterns_are_server_safe():
    """The same patterns go to Postgres as literals: no backslashes, anchored, one per type."""
    assert set(PATTERNS) == set(TYPE_ORDER)
    for p in PATTERNS.values():
        assert "\\" not in p and p.startswith("^") and p.endswith("$")


def test_shop_policy_loads():
    policy = load_policy(POLICY)
    assert policy["customer_unique_id"] == "customer_id" and "review_comment_message" in policy


def test_profile_model_dumps_section5_keys():
    p = Profile.model_validate({
        "schema": "raw", "profiled_at_rows": True,
        "tables": [{"name": "t", "rows": 1, "candidate_keys": [["id"]],
                    "columns": [{"name": "id", "inferred_type": "text", "null_rate": 0.0, "distinct": 1,
                                 "pii": False, "min": None, "max": None}]}],
        "relationships": [{"from": "u.id", "to": "t.id", "coverage": 1.0}],
    })
    d = p.to_json_dict()
    assert list(d) == ["schema", "profiled_at_rows", "tables", "relationships"]
    assert d["relationships"][0] == {"from": "u.id", "to": "t.id", "coverage": 1.0}


# ---- live ----

def _raw_ready() -> bool:
    if not os.environ.get("GOVERNOR_BUILD_PASSWORD"):
        return False
    try:
        import psycopg

        with psycopg.connect(build_dsn(), connect_timeout=3) as conn:
            n = conn.execute("select count(*) from information_schema.tables where table_schema = 'raw' "
                             "and table_name in ('olist_orders_dataset', 'olist_customers_dataset')").fetchone()[0]
            return n == 2
    except Exception:  # noqa: BLE001
        return False


live = pytest.mark.skipif(not _raw_ready(), reason="needs GOVERNOR_BUILD_PASSWORD and Olist tables in raw")


@pytest.fixture(scope="module")
def profile():
    return profile_schema(build_dsn(), "raw", load_policy(POLICY))


def _cols(profile):
    return {(t["name"], c["name"]): c for t in profile["tables"] for c in t["columns"]}


def _sample_pii_values() -> set[str]:
    policy = load_policy(POLICY)
    vals = set()
    for f in SAMPLE.glob("*.csv"):
        with f.open(newline="", encoding="utf-8") as fh:
            for row in csv.DictReader(fh):
                vals |= {v.strip() for c, v in row.items() if c in policy and v and len(v.strip()) >= 4}
    return vals


@live
def test_live_structure(profile):
    Profile.model_validate(profile)
    assert profile["schema"] == "raw" and profile["profiled_at_rows"] is True
    assert not any(c.startswith("_") for _, c in _cols(profile))


@live
def test_live_keys(profile):
    tables = {t["name"]: t for t in profile["tables"]}
    assert ["order_id"] in tables["olist_orders_dataset"]["candidate_keys"]
    keys = tables["olist_customers_dataset"]["candidate_keys"]
    assert ["customer_id"] in keys and ["customer_unique_id"] not in keys
    items = tables.get("olist_order_items_dataset")
    if items:  # no single-column key, so the pair is found
        assert ["order_id", "order_item_id"] in items["candidate_keys"]


@live
def test_live_relationship(profile):
    rel = {(r["from"], r["to"]): r["coverage"] for r in profile["relationships"]}
    assert rel[("olist_orders_dataset.customer_id", "olist_customers_dataset.customer_id")] >= 0.95
    assert all(c >= 0.95 for c in rel.values())


@live
def test_live_types(profile):
    cols = _cols(profile)
    ts = cols[("olist_orders_dataset", "order_purchase_timestamp")]
    assert ts["inferred_type"] == "timestamp" and ts["min"] <= ts["max"]
    price = cols[("olist_order_items_dataset", "price")]
    assert price["inferred_type"] == "numeric" and isinstance(price["min"], float)
    assert cols[("olist_orders_dataset", "order_id")]["inferred_type"] == "text"


@live
def test_live_no_pii_value(profile, capsys):
    for (_, name), c in _cols(profile).items():
        if c["pii"]:
            assert c["min"] is None and c["max"] is None, name
    assert _cols(profile)[("olist_customers_dataset", "customer_unique_id")]["pii"] is True
    text = json.dumps(profile)
    leaked = [v for v in _sample_pii_values() if re.search(re.escape(v), text)]
    assert not leaked


@live
def test_live_cli_out(tmp_path, capsys):
    out = tmp_path / "profile.json"
    assert build_cli.main(["profile", "--schema", "raw", "--policy", str(POLICY), "--out", str(out)]) == 0
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["out"] == str(out) and summary["tables"] >= 2
    assert json.loads(out.read_text(encoding="utf-8"))["schema"] == "raw"

def _fake_db(monkeypatch, data):
    """Column names stand in for SQL expressions; distinct counts come from ``data`` (a list of dicts)."""
    from governor.build import profile as prof

    monkeypatch.setattr(prof, "_value", lambda col: col)
    monkeypatch.setattr(prof, "_distinct", lambda conn, rel, exprs, limit=None:
                        len({tuple(r[e] for e in exprs) for r in (data[:limit] if limit else data)}))
    return prof


def test_triple_key_when_no_single_or_pair_key(monkeypatch):
    # 18 Nov, OULAD: an enrolment is unique only on module + presentation + student
    names = ["code_module", "code_presentation", "id_student"]
    data = [dict(zip(names, (m, p, s))) for m in ("AAA", "BBB") for p in ("2013J", "2014B") for s in (1, 2, 3)]
    data = [d | {"gender": "F" if d["id_student"] % 2 else "M"} for d in data]
    prof = _fake_db(monkeypatch, data)
    cols = [ColumnProfile(name=n, inferred_type="text", null_rate=0.0, distinct=len({d[n] for d in data}), pii=False)
            for n in names + ["gender"]]
    assert prof._pair_keys(None, None, len(data), cols) == []
    assert prof._triple_keys(None, None, len(data), cols) == [names]


def test_triple_search_skips_columns_with_nulls(monkeypatch):
    names = ["a", "b", "c"]
    data = [dict(zip(names, (a, b, c))) for a in (1, 2) for b in (1, 2) for c in (1, 2)]
    prof = _fake_db(monkeypatch, data)
    cols = [ColumnProfile(name="a", inferred_type="integer", null_rate=0.0, distinct=2, pii=False),
            ColumnProfile(name="b", inferred_type="integer", null_rate=0.0, distinct=2, pii=False),
            ColumnProfile(name="c", inferred_type="integer", null_rate=0.1, distinct=2, pii=False)]
    assert prof._triple_keys(None, None, len(data), cols) == []

