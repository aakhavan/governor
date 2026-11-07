"""Build graph to the design gate: repairs, design_invalid, interrupt, reject and approve (also across processes).
Offline runs inject the profile; the live run profiles raw and skips without the database."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from governor.build import graph
from governor.build.llm import FakeBuildLLM
from governor.core.catalogue import load_approved

ROOT = Path(__file__).resolve().parents[2]
BUILT = {"gmv", "net_revenue", "aov", "on_time_delivery_rate", "avg_review_score", "repeat_purchase_rate",
         "cohort_retention", "historical_clv"}


def _bad(good):
    bad = json.loads(json.dumps(good))
    next(k for k in bad["kpis"] if k["id"] == "gmv")["mapping"]["item_price"] = "no_such_column"
    return bad


def _start(tmp_path, profile, replies, **kw):
    llm = FakeBuildLLM({"propose": [json.dumps(r) if isinstance(r, dict) else r for r in replies]})
    out = graph.start(tmp_path / "target", "shop", llm, profile=profile,
                      checkpoints=tmp_path / "state" / graph.CHECKPOINT_FILE, **kw)
    return out, llm


def test_pauses_at_gate_and_writes_report(tmp_path, profile, good):
    out, llm = _start(tmp_path, profile, [good])
    assert out["status"] == graph.AWAITING and out["thread_id"] and len(llm.prompts) == 1
    gov = tmp_path / "target" / "governor"
    assert json.loads((gov / "design.json").read_text(encoding="utf-8")) == json.loads(json.dumps(good))
    text = (gov / "design.md").read_text(encoding="utf-8")
    assert f"approve {out['thread_id']}" in text and out["report"] == str(gov / "design.md")
    assert (tmp_path / "state" / graph.CHECKPOINT_FILE).is_file()


def test_bad_proposal_is_repaired(tmp_path, profile, good):
    out, llm = _start(tmp_path, profile, [_bad(good), good])
    assert out["status"] == graph.AWAITING and len(llm.prompts) == 2
    assert "MAPPING_UNKNOWN_COLUMN kpi.gmv" in llm.prompts[1][1] and "Your previous proposal" in llm.prompts[1][1]


def test_design_repair_fixes_key_before_the_gate(tmp_path, profile, good):
    first = json.loads(json.dumps(good))
    next(m for m in first["silver_models"] if m["name"] == "stg_order_items")["primary_key"] = ["order_id"]
    out, llm = _start(tmp_path, profile, [first, good])
    assert out["status"] == graph.AWAITING and len(llm.prompts) == 2
    assert "KEY_NOT_UNIQUE stg_order_items" in llm.prompts[1][1]
    assert "[order_id, order_item_id]" in llm.prompts[1][1]
    config = {"configurable": {"thread_id": out["thread_id"]}}
    with graph.open_checkpointer(tmp_path / "state" / graph.CHECKPOINT_FILE) as saver:
        values = graph.build_graph(FakeBuildLLM({}), saver).get_state(config).values
    assert values["findings"] == [] and values["repairs"] == 1  # design_repairs == 1
    pk = next(m for m in values["proposal"]["silver_models"] if m["name"] == "stg_order_items")["primary_key"]
    assert pk == ["order_id", "order_item_id"]


def test_two_repairs_then_design_invalid(tmp_path, profile, good):
    out, llm = _start(tmp_path, profile, [_bad(good)] * 5)
    assert out["status"] == graph.INVALID and out["findings"] == ["MAPPING_UNKNOWN_COLUMN"]
    assert len(llm.prompts) == 1 + graph.MAX_REPAIRS
    gov = tmp_path / "target" / "governor"
    assert "MAPPING_UNKNOWN_COLUMN" in (gov / "design.md").read_text(encoding="utf-8")
    assert not (gov / "design.json").exists()


def test_unparseable_reply_is_a_finding(tmp_path, profile):
    out, _ = _start(tmp_path, profile, ["this is not json"])
    assert out["status"] == graph.INVALID and out["findings"] == ["PROPOSAL_UNPARSEABLE"]


def test_reject_then_approve_with_a_fresh_saver(tmp_path, profile, good):
    out, _ = _start(tmp_path, profile, [good])
    tid, cp = out["thread_id"], tmp_path / "state" / graph.CHECKPOINT_FILE
    llm2 = FakeBuildLLM({"propose": [json.dumps(good)]})
    r = graph.reject(tid, "use int_orders for on-time delivery", llm2, checkpoints=cp)
    assert r["status"] == graph.AWAITING and len(llm2.prompts) == 1
    assert "use int_orders for on-time delivery" in llm2.prompts[0][1]
    # no intermediate SQL in the script: silver escalates before dbt runs (never called here)
    a = graph.approve(tid, "amir", FakeBuildLLM({}), checkpoints=cp, dbt_runner=_no_dbt)
    assert a["status"] == graph.ESCALATED and a["escalated"]["model"].startswith("int_")
    decisions = load_approved(tmp_path / "target" / "governor" / "approved.yaml").decisions
    assert {d.subject.split(".")[1] for d in decisions} == BUILT
    assert all(d.kind == "column_mapping" and d.approved_by == "amir" for d in decisions)
    with pytest.raises(graph.BuildError, match="not waiting"):
        graph.approve(tid, "amir", FakeBuildLLM({}), checkpoints=cp)


def _no_dbt(target, args):
    raise AssertionError("dbt must not run while SQL is refused")


def test_second_reject_ends_the_thread(tmp_path, profile, good):
    out, _ = _start(tmp_path, profile, [good])
    cp = tmp_path / "state" / graph.CHECKPOINT_FILE
    llm = FakeBuildLLM({"propose": [json.dumps(good)]})
    assert graph.reject(out["thread_id"], "first", llm, checkpoints=cp)["status"] == graph.AWAITING
    assert graph.reject(out["thread_id"], "second", llm, checkpoints=cp)["status"] == graph.REJECTED
    assert len(llm.prompts) == 1


def test_unknown_thread(tmp_path):
    with pytest.raises(graph.BuildError, match="unknown build thread"):
        graph.approve("nope", "amir", FakeBuildLLM({}), checkpoints=tmp_path / "cp.sqlite")


# ---- new processes through the CLI ----

def _cli(args, env):
    r = subprocess.run([sys.executable, "-m", "governor.build", *args], capture_output=True, text=True,
                       env=env, cwd=ROOT, timeout=300)
    lines = [ln for ln in r.stdout.splitlines() if ln.strip().startswith("{")]
    assert r.returncode == 0 and lines, r.stderr[-2000:]
    return json.loads(lines[-1])


def _script(path, *replies):
    path.write_text(json.dumps({"propose": [json.dumps(r) for r in replies]}), encoding="utf-8")
    return f"fake:{path}"


def _env(tmp_path):
    return {**os.environ, "GOVERNOR_STATE_DIR": str(tmp_path / "state"), "PYTHONIOENCODING": "utf-8"}


def _gate_cycle(tmp_path, good, run_extra, env):
    target = tmp_path / "olist-dbt"
    d = _cli(["run", "--target", str(target), "--project-name", "shop",
              "--llm", _script(tmp_path / "s1.json", good), *run_extra], env)
    assert d["status"] == "awaiting_design_approval" and d["thread_id"]
    tid = d["thread_id"]
    d = _cli(["reject", tid, "--note", "use int_orders", "--llm", _script(tmp_path / "s2.json", good)], env)
    assert d["status"] == "awaiting_design_approval"
    d = _cli(["approve", tid, "--by", "amir", "--llm", _script(tmp_path / "s3.json", good)], env)
    # the approve script has no intermediate SQL: silver escalates without reaching dbt
    assert d["status"] == "escalated" and d["escalated"]["model"].startswith("int_") and d["repairs"] == 9
    decisions = load_approved(target / "governor" / "approved.yaml").decisions
    assert len(decisions) >= len(BUILT) and all(x.approved_by == "amir" for x in decisions)


def test_cli_gate_across_processes(tmp_path, profile, good):
    saved = tmp_path / "profile.json"
    saved.write_text(json.dumps(profile), encoding="utf-8")
    _gate_cycle(tmp_path, good, ["--profile", str(saved)], _env(tmp_path))


def _raw_ready() -> bool:
    if not os.environ.get("GOVERNOR_BUILD_PASSWORD"):
        return False
    try:
        import psycopg

        from governor.build.workspace import build_dsn

        with psycopg.connect(build_dsn(), connect_timeout=3) as c:
            n = c.execute("select count(*) from information_schema.tables where table_schema = 'raw' "
                          "and table_name in ('olist_orders_dataset', 'olist_customers_dataset')").fetchone()[0]
            return n == 2
    except Exception:  # noqa: BLE001
        return False


@pytest.mark.skipif(not _raw_ready(), reason="needs GOVERNOR_BUILD_PASSWORD and Olist tables in raw")
def test_live_gate_across_processes(tmp_path, good):
    _gate_cycle(tmp_path, good, [], _env(tmp_path))
