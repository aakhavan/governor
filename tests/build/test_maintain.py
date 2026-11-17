"""Up-to-date runs and drift-aware design (batch3.md section 29), offline: the fake build LLM and a dbt runner that
must never be called."""
import datetime as dt
import json

from governor.build import design, events, graph
from governor.build.llm import FakeBuildLLM

APPROVED_ON = dt.date(2026, 11, 17)


def _no_dbt(target, args):
    raise AssertionError("dbt must not run")


def _start(tmp_path, profile, replies, **kw):
    llm = FakeBuildLLM({"propose": [json.dumps(r) for r in replies]} if replies else {})  # no replies: empty script
    out = graph.start(tmp_path / "target", "shop", llm, profile=profile,
                      checkpoints=tmp_path / "state" / graph.CHECKPOINT_FILE, dbt_runner=_no_dbt, **kw)
    return out, llm


def _built(tmp_path, profile, good, status="built") -> str:
    """A target as an approved, built design leaves it: design.json, the fingerprint and build.json."""
    out, _ = _start(tmp_path, profile, [good])
    assert out["status"] == graph.AWAITING
    target = tmp_path / "target"
    graph.write_fingerprint(target, profile, APPROVED_ON, out["thread_id"])
    (target / "governor" / "build.json").write_text(json.dumps({"status": status, "thread_id": out["thread_id"]}),
                                                    encoding="utf-8")
    return out["thread_id"]


def _models(tmp_path) -> dict:
    root = tmp_path / "target" / "models"
    return {p.relative_to(root).as_posix(): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


def _drifted(profile) -> dict:
    prof = json.loads(json.dumps(profile))
    table = prof["tables"][0]
    table["columns"].append({**table["columns"][0], "name": "loaded_by", "pii": False})
    return prof


def test_unchanged_target_is_up_to_date_without_model_calls(tmp_path, profile, good):
    last = _built(tmp_path, profile, good)
    before = _models(tmp_path)
    out, llm = _start(tmp_path, profile, [])
    assert out["status"] == graph.UP_TO_DATE and out["last_build"] == last
    assert llm.calls == [] and llm.prompts == [] and out["llm_calls"] == 0
    assert _models(tmp_path) == before  # no file under models/ touched
    text = (tmp_path / "target" / "governor" / "drift.md").read_text(encoding="utf-8")
    assert text.strip() == f"No change in the raw schema since build {last[:8]}, approved on 2026-11-17."
    evs = [json.loads(ln) for ln in events.events_path().read_text(encoding="utf-8").splitlines()]
    up = [e for e in evs if e["kind"] == "up_to_date"]
    assert len(up) == 1 and up[0]["thread_id"] == out["thread_id"] and up[0]["last_build"] == last
    assert not any(e["kind"] == "proposed" and e["thread_id"] == out["thread_id"] for e in evs)


def test_failed_last_build_is_not_up_to_date(tmp_path, profile, good):
    _built(tmp_path, profile, good, status="escalated")
    out, llm = _start(tmp_path, profile, [good])
    assert out["status"] == graph.AWAITING and len(llm.prompts) == 1
    # same schema: a full design from nothing, no drift note and no previous design
    assert "Your previous proposal" not in llm.prompts[0][1] and graph.DRIFT_HEAD not in llm.prompts[0][1]


def test_force_runs_full_design(tmp_path, profile, good):
    _built(tmp_path, profile, good)
    out, llm = _start(tmp_path, profile, [good], force=True)
    assert out["status"] == graph.AWAITING and len(llm.prompts) == 1
    assert "Your previous proposal" not in llm.prompts[0][1]


def test_drift_passes_previous_design_and_note(tmp_path, profile, good):
    _built(tmp_path, profile, good)
    table = profile["tables"][0]["name"]
    out, llm = _start(tmp_path, _drifted(profile), [good])
    assert out["status"] == graph.AWAITING and out["drift"] == [f"column added: {table}.loaded_by"]
    assert len(llm.prompts) == 1
    prompt = llm.prompts[0][1]
    assert graph.DRIFT_HEAD in prompt and f"column added: {table}.loaded_by" in prompt and graph.DRIFT_TAIL in prompt
    assert "Your previous proposal" in prompt and good["silver_models"][0]["name"] in prompt
    gov = tmp_path / "target" / "governor"
    assert f"column added: {table}.loaded_by" in (gov / "drift.md").read_text(encoding="utf-8")
    report = (gov / "design.md").read_text(encoding="utf-8")
    assert "## Drift since the last approved build" in report and f"- column added: {table}.loaded_by" in report
    config = {"configurable": {"thread_id": out["thread_id"]}}
    with graph.open_checkpointer(tmp_path / "state" / graph.CHECKPOINT_FILE) as saver:
        values = graph.build_graph(FakeBuildLLM({}), saver).get_state(config).values
    assert values["repairs"] == 0  # the first drift proposal is a normal proposal, not a repair


def test_design_report_lists_drift(good):
    lines = ["column added: orders.loaded_by", "table removed: old_table"]
    text = design.render_report(good, [], "t-1", drift=lines)
    assert "## Drift since the last approved build" in text
    assert "- column added: orders.loaded_by" in text and "- table removed: old_table" in text
    assert "Drift since the last approved build" not in design.render_report(good, [], "t-1")


def test_target_without_fingerprint_runs_as_before(tmp_path, profile, good):
    out, llm = _start(tmp_path, profile, [good])
    assert out["status"] == graph.AWAITING and len(llm.prompts) == 1 and "drift" not in out
    gov = tmp_path / "target" / "governor"
    assert not (gov / "drift.md").exists() and not (gov / "profile_fingerprint.json").exists()
    assert "Drift since the last approved build" not in (gov / "design.md").read_text(encoding="utf-8")
    assert "Your previous proposal" not in llm.prompts[0][1]
