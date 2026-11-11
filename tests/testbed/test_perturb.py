"""Perturbed test bed (batch2d section 24), offline on testbed/sample/ in a temp folder."""
import csv
import filecmp
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SAMPLE = ROOT / "testbed" / "sample"
POLICY = ROOT / "knowledge" / "shop" / "policy.yaml"

sys.path.insert(0, str(ROOT / "testbed"))
_spec = importlib.util.spec_from_file_location("perturb", ROOT / "testbed" / "perturb.py")
perturb = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(perturb)
EXPECTED = perturb.EXPECTED  # the loader's list, imported by perturb.py


def _rows(path):
    with path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.reader(f))
    return rows[0], rows[1:]


def _run(out):
    assert perturb.main(["--source", str(SAMPLE), "--out", str(out), "--policy", str(POLICY)]) == 0
    return json.loads((out / "mapping.json").read_text(encoding="utf-8"))


@pytest.fixture
def out(tmp_path):
    d = tmp_path / "p"
    _run(d)
    return d


def _originals():
    return ({n.removesuffix(".csv") for n in EXPECTED}, {c for cols in EXPECTED.values() for c in cols})


def test_perturb_is_deterministic(tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    _run(a)
    _run(b)
    names = sorted(p.name for p in a.iterdir())
    assert names == sorted(p.name for p in b.iterdir())
    assert all(filecmp.cmp(a / n, b / n, shallow=False) for n in names)


def test_no_original_table_or_column_name_survives(out):
    tables, cols = _originals()
    csvs = list(out.glob("*.csv"))
    assert {p.stem for p in csvs} == {*perturb.TABLES.values(), perturb.DELIVERY_TABLE, perturb.JUNK_TABLE}
    assert not ({p.stem for p in csvs} & tables)
    for p in csvs:
        header, _ = _rows(p)
        assert not (set(header) & cols), p.name
        assert len(set(header)) == len(header)
    policy_keys = {line.split(":")[0] for line in (out / "policy.yaml").read_text(encoding="utf-8").splitlines()
                   if line and not line.startswith("#")}
    assert not (policy_keys & cols)


def test_values_and_row_counts_are_unchanged(out):
    mapping = json.loads((out / "mapping.json").read_text(encoding="utf-8"))
    assert set(mapping) == {"tables", "columns"}
    files = {}
    for p in out.glob("*.csv"):
        header, rows = _rows(p)
        files[p.stem] = {c: [r[i] for r in rows] for i, c in enumerate(header)}
    for name, want_cols in EXPECTED.items():
        old = name.removesuffix(".csv")
        header, rows = _rows(SAMPLE / name)
        assert header == want_cols
        for i, col in enumerate(header):
            new_table, new_col = mapping["columns"][f"{old}.{col}"].split(".")
            assert files[new_table][new_col] == [r[i] for r in rows], f"{old}.{col}"
    # column order is reversed
    header, _ = _rows(out / "cust.csv")
    assert header == [perturb.COLUMNS[c] for c in reversed(EXPECTED["olist_customers_dataset.csv"])]


def test_orders_split_keeps_every_order(out):
    _, orders = _rows(SAMPLE / "olist_orders_dataset.csv")
    key = perturb.COLUMNS["order_id"]
    hdr_h, hdr = _rows(out / "ord_hdr.csv")
    dlv_h, dlv = _rows(out / "ord_dlv.csv")
    ids = [r[0] for r in orders]
    assert [r[hdr_h.index(key)] for r in hdr] == ids
    assert [r[dlv_h.index(key)] for r in dlv] == ids
    assert set(dlv_h) == {key, *(perturb.COLUMNS[c] for c in perturb.DELIVERY_COLUMNS)}
    assert set(hdr_h) == {perturb.COLUMNS[c] for c in ("order_id", "customer_id", "order_status",
                                                        "order_purchase_timestamp", "order_approved_at")}


def test_policy_is_renamed_through_the_mapping(out):
    mapping = json.loads((out / "mapping.json").read_text(encoding="utf-8"))
    new_cols = {v.split(".")[1] for v in mapping["columns"].values()}
    want = [(perturb.COLUMNS[k], t) for k, t in perturb.read_policy(POLICY)]
    got = perturb.read_policy(out / "policy.yaml")
    assert got == want and len(got) == len(perturb.read_policy(POLICY))
    assert all(k in new_cols for k, _ in got)
    assert ("cust_ref", "customer_id") in got
    bad = out / "bad.yaml"
    bad.write_text("not_an_olist_column: free_text\n", encoding="utf-8")
    with pytest.raises(perturb.PerturbError, match="not_an_olist_column"):
        perturb.rename_policy(perturb.read_policy(bad))


def test_junk_table_is_written(out):
    header, rows = _rows(out / "etl_audit_log.csv")
    assert header == ["batch_id", "loaded_at", "row_count", "status"]
    assert len(rows) == 20 and len({r[0] for r in rows}) == 20
    mapping = json.loads((out / "mapping.json").read_text(encoding="utf-8"))
    assert "etl_audit_log" not in json.dumps(mapping)


def test_perturb_validates_the_source_headers(tmp_path):
    bad = tmp_path / "bad"
    bad.mkdir()
    for p in SAMPLE.glob("*.csv"):
        (bad / p.name).write_bytes(p.read_bytes())
    p = bad / "olist_orders_dataset.csv"
    p.write_text(p.read_text(encoding="utf-8").replace("order_status", "status", 1), encoding="utf-8")
    assert perturb.main(["--source", str(bad), "--out", str(tmp_path / "o"), "--policy", str(POLICY)]) == 2
    assert not (tmp_path / "o").exists()


def test_mapping_is_complete_and_never_reuses_a_name():
    perturb.check_mapping()
