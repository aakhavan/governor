"""Profile fingerprint and drift (batch3.md section 28): value-free, order-stable, and diffable; written at approval."""
import copy
import csv
import json
import random
from pathlib import Path

from governor.build import drift, graph
from governor.build.llm import FakeBuildLLM

SAMPLE = Path(__file__).resolve().parents[2] / "testbed" / "sample"
FORBIDDEN_KEYS = {"rows", "null_rate", "distinct", "min", "max", "coverage"}


def _keys(obj):
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield k
            yield from _keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _keys(v)


def _with_values(profile: dict) -> dict:
    """The fixture profile with min/max and a relationship filled in, so leaking them would show."""
    p = copy.deepcopy(profile)
    for t in p["tables"]:
        for c in t["columns"]:
            if c["inferred_type"] in ("integer", "numeric") and not c["pii"]:
                c["min"], c["max"] = 987654321, 987654329
            elif c["inferred_type"] in ("timestamp", "date") and not c["pii"]:
                c["min"], c["max"] = "1999-12-31", "2099-01-01"
    names = [t["name"] for t in p["tables"]]
    p["relationships"] = [{"from": f"{names[0]}.x", "to": f"{names[-1]}.y", "coverage": 0.123457}]
    return p


def _table(profile: dict, name: str) -> dict:
    return next(t for t in profile["tables"] if t["name"] == name)


def test_fingerprint_has_no_counts_or_values(profile):
    p = _with_values(profile)
    fp = drift.fingerprint(p)
    assert fp["version"] == 1 and fp["schema"] == "raw"
    assert not FORBIDDEN_KEYS & set(_keys(fp))
    text = json.dumps(fp)
    for t in p["tables"]:
        assert set(fp["tables"][t["name"]]["columns"]) == {c["name"] for c in t["columns"]}
        for c in t["columns"]:
            for v in (c["min"], c["max"]):
                if v is not None:
                    assert str(v) not in text
    assert "0.123457" not in text and "987654321" not in text
    # no cell of the sample data appears as a JSON string, unless it is itself a table, column or type name
    names = set(_keys(fp)) | {"raw", "integer", "numeric", "timestamp", "date", "boolean", "text"}
    for f in sorted(SAMPLE.glob("*.csv")):
        with f.open(newline="", encoding="utf-8") as fh:
            cells = {(v or "").strip() for r in csv.DictReader(fh) for v in r.values()}
        leaked = [v for v in cells - names if v and json.dumps(v) in text]
        assert not leaked, f"{f.name}: {leaked[:3]}"
    # no row count or distinct count of the fixture appears as a value either
    numbers = [v for v in _scalars(fp) if isinstance(v, (int, float)) and not isinstance(v, bool)]
    assert numbers == [1]  # only the version


def _scalars(obj):
    if isinstance(obj, dict):
        for v in obj.values():
            yield from _scalars(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _scalars(v)
    else:
        yield obj


def test_fingerprint_is_stable_across_order(profile):
    shuffled = copy.deepcopy(profile)
    rnd = random.Random(7)
    rnd.shuffle(shuffled["tables"])
    for t in shuffled["tables"]:
        rnd.shuffle(t["columns"])
        t["candidate_keys"] = [list(reversed(k)) for k in reversed(t["candidate_keys"])]
    a, b = drift.fingerprint(profile), drift.fingerprint(shuffled)
    assert a == b and drift.fingerprint_hash(a) == drift.fingerprint_hash(b)
    assert len(drift.fingerprint_hash(a)) == 64
    assert list(a["tables"]) == sorted(a["tables"])


def test_diff_empty_for_same_profile(profile):
    d = drift.diff(drift.fingerprint(profile), drift.fingerprint(copy.deepcopy(profile)))
    assert d.empty and d.summary_lines() == []


def test_diff_reports_added_and_removed(profile):
    new = copy.deepcopy(profile)
    gone = new["tables"].pop(0)["name"]
    new["tables"].append({"name": "zz_new_table", "rows": 0, "columns": [], "candidate_keys": []})
    t = new["tables"][0]
    dropped = t["columns"].pop()["name"]
    t["columns"].append({"name": "zz_new_col", "inferred_type": "text", "null_rate": 0.0, "distinct": 0,
                         "pii": False})
    t["candidate_keys"] = [k for k in t["candidate_keys"] if dropped not in k]
    d = drift.diff(drift.fingerprint(profile), drift.fingerprint(new))
    assert not d.empty
    assert d.tables_added == ["zz_new_table"] and d.tables_removed == [gone]
    assert d.columns_added == {t["name"]: ["zz_new_col"]} and d.columns_removed == {t["name"]: [dropped]}
    lines = d.summary_lines()
    assert lines == sorted(lines)
    assert f"table removed: {gone}" in lines and f"column added: {t['name']}.zz_new_col" in lines


def test_diff_reports_type_pii_and_key_changes(profile):
    new = copy.deepcopy(profile)
    t = new["tables"][0]
    c0 = t["columns"][0]
    old_type = c0["inferred_type"]
    c0["inferred_type"] = "boolean" if old_type != "boolean" else "text"
    c1 = t["columns"][1]
    c1["pii"] = not c1["pii"]
    t["candidate_keys"] = t["candidate_keys"] + [[c0["name"], c1["name"]]]
    d = drift.diff(drift.fingerprint(profile), drift.fingerprint(new))
    assert d.type_changes == {t["name"]: {c0["name"]: [old_type, c0["inferred_type"]]}}
    assert d.pii_changes == {t["name"]: [c1["name"]]}
    assert d.keys_changed == [t["name"]]
    assert not d.tables_added and not d.columns_added and not d.columns_removed
    assert f"type changed: {t['name']}.{c0['name']} {old_type} -> {c0['inferred_type']}" in d.summary_lines()


def test_approval_writes_fingerprint(tmp_path, profile, good):
    llm = FakeBuildLLM({"propose": [json.dumps(good)]})
    cp = tmp_path / "state" / graph.CHECKPOINT_FILE
    out = graph.start(tmp_path / "target", "shop", llm, profile=profile, checkpoints=cp)
    path = tmp_path / "target" / "governor" / "profile_fingerprint.json"
    assert out["status"] == graph.AWAITING and not path.exists()  # nothing before approval

    def _no_dbt(target, args):
        raise AssertionError("dbt must not run while SQL is refused")

    graph.approve(out["thread_id"], "amir", FakeBuildLLM({}), checkpoints=cp, dbt_runner=_no_dbt)
    doc = json.loads(path.read_text(encoding="utf-8"))
    assert set(doc) == {"thread_id", "approved_on", "hash", "fingerprint"}
    assert doc["thread_id"] == out["thread_id"]
    assert doc["fingerprint"] == drift.fingerprint(profile)
    assert doc["hash"] == drift.fingerprint_hash(doc["fingerprint"])
    assert (path.parent / "approved.yaml").is_file()
