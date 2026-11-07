"""D9b Slack clean-up (batch2c section 20), offline: terminal states, superseded and interrupted records, the
escalation reason, the runner allowlist, design.md without mappings and the PR link from the event."""
import json
from types import SimpleNamespace

from governor.build import graph
from governor.build.llm import FakeBuildLLM
from governor.integrations.slack import blocks, notifier
from governor.integrations.slack.app import RUN_REFUSAL, GovernorSlack
from test_slack import APPROVER, OTHER, Responder, _config, _inline, _no_dbt, _to_gate, _wire

TA, TB, TC, TD = (f"{c * 8}-0000-4000-8000-000000000000" for c in "abcd")


def _header(update: dict) -> str:
    return update["blocks"][0]["text"]["text"]


def _checklist(update: dict) -> str:
    return update["blocks"][1]["text"]["text"]


def _last_update(fake, ts: str) -> dict:
    return [u for u in fake.named("chat_update") if u["ts"] == ts][-1]


def _seed(n: notifier.Notifier) -> None:
    """A: olist, building silver (open). B: olist, at the gate. C: shop, open. D: olist, built."""
    for tid, project in ((TA, "olist"), (TB, "olist"), (TC, "shop"), (TD, "olist")):
        n.handle({"kind": "run_started", "thread_id": tid, "project": project})
    n.handle({"kind": "design_gate", "thread_id": TB, "status": graph.AWAITING})
    n.handle({"kind": "approved", "thread_id": TA, "by": "amir"})
    n.handle({"kind": "built", "thread_id": TD, "status": graph.BUILT, "kpis_built": 8})


def test_escalation_marks_progress_failed(tmp_path, monkeypatch, fake, profile, good):
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    # the write model gives no SQL: the intermediate models are refused, repaired, and the build escalates in silver
    assert graph.approve(tid, "amir", FakeBuildLLM({}), dbt_runner=_no_dbt)["status"] == graph.ESCALATED
    rec = notifier.MessageStore().get(tid)
    assert rec["outcome"] == blocks.FAILED and rec["failed_stage"] == "silver_built"
    last = _last_update(fake, rec["ts"])
    head, checklist = _header(last), _checklist(last)
    assert head.startswith(":red_circle: stopped at silver")
    reason = head.split("\n", 1)[1]
    assert reason and len(reason) <= 200 and "no error recorded" not in reason
    for label in ("profiled", "design proposed", "validated", "waiting for approval", "approved"):
        assert f":white_check_mark: {label}" in checklist
    assert ":x: silver built" in checklist
    assert ":heavy_minus_sign: gold built" in checklist and ":heavy_minus_sign: published" in checklist
    assert ":white_large_square:" not in checklist
    # the escalation reply names the failing node and its error
    esc = [c for c in fake.named("chat_postMessage") if c.get("thread_ts") == rec["ts"] and "escalated" in c["text"]]
    assert len(esc) == 1 and "`int_" in esc[0]["blocks"][0]["text"]["text"]

    # gold: the blueprint check stops the run at gold
    n = notifier.Notifier(fake, "governor")
    n.handle({"kind": "run_started", "thread_id": TA, "project": "olist"})
    n.handle({"kind": "silver_built", "thread_id": TA})
    n.handle({"kind": "escalated", "thread_id": TA, "stage": "gold", "status": graph.BLUEPRINT_FAILED,
              "blueprint_findings": 2})
    last = _last_update(fake, n.store.get(TA)["ts"])
    assert _header(last).startswith(":red_circle: stopped at gold (blueprint check)")
    assert "2 blueprint findings" in _header(last)
    assert ":white_check_mark: silver built" in _checklist(last) and ":x: gold built" in _checklist(last)
    assert ":heavy_minus_sign: published" in _checklist(last)


def test_escalation_reason_names_failing_tests(tmp_path, fake):
    target = tmp_path / "target"
    (target / "target").mkdir(parents=True)
    (target / "target" / "run_results.json").write_text(json.dumps({"results": [
        {"unique_id": "model.olist.stg_orders", "status": "success", "message": "SELECT 99441", "failures": None},
        {"unique_id": "test.olist.unique_stg_orders_order_id.a1b2c3", "status": "fail", "failures": 3,
         "message": "Got 3 results, configured to fail if != 0 SENTINEL_ROW_1177",
         "agate_table": [["SENTINEL_ROW_2288"]]},
        {"unique_id": "test.olist.not_null_stg_items_price.d4e5f6", "status": "fail", "failures": 1,
         "message": "Got 1 result, configured to fail if != 0"},
        {"unique_id": "test.olist.accepted_values_stg_orders_status.0a0a", "status": "pass", "failures": 0},
    ]}), encoding="utf-8")
    # the checkpoint has no error for the stage (model null, empty error): run_results.json is the fallback
    n = notifier.Notifier(fake, "governor", values=lambda t: {"target": str(target), "silver": {"escalated": None}})
    n.handle({"kind": "run_started", "thread_id": TA, "project": "olist"})
    n.handle({"kind": "approved", "thread_id": TA, "by": "amir"})
    n.handle({"kind": "escalated", "thread_id": TA, "stage": "silver", "model": None, "repairs": 0})
    rec = n.store.get(TA)
    head = _header(_last_update(fake, rec["ts"]))
    assert head.startswith(":red_circle: stopped at silver")
    assert "unique_stg_orders_order_id (3 failures)" in head and "not_null_stg_items_price (1 failure)" in head
    esc = [c for c in fake.named("chat_postMessage") if c.get("thread_ts") == rec["ts"]][-1]
    text = json.dumps(esc["blocks"])
    assert "`unique_stg_orders_order_id`" in esc["blocks"][0]["text"]["text"]  # the failing node, never "null"
    assert "unique_stg_orders_order_id (3 failures)" in text and "not_null_stg_items_price (1 failure)" in text
    payload = json.dumps(fake.calls) + json.dumps(n.store.all())
    assert "SENTINEL_ROW" not in payload and "accepted_values" not in payload and "no single model" not in payload

    # the checkpointed error wins over run_results.json; a gold error with no owner still names its node
    n2 = notifier.Notifier(fake, "governor", values=lambda t: {"target": str(target), "gold": {"escalated": {
        "model": None, "error": "dbt test.olist.x fail: x\ndbt test test.olist.unique_kpi_gmv_day.ff fail: Got 2 results, "
                                "configured to fail if != 0"}}})
    n2.store = n.store
    for tid in (TB, TC):
        n.handle({"kind": "run_started", "thread_id": tid, "project": "olist"})
    n2.handle({"kind": "escalated", "thread_id": TB, "stage": "gold", "model": None, "status": graph.ESCALATED})
    head = _header(_last_update(fake, n.store.get(TB)["ts"]))
    assert "unique_kpi_gmv_day (2 failures)" in head and "unique_stg_orders" not in head
    # gold.py's own spelling ("dbt test.<package>.<name>.<hash> <status>: ..."), two tests, one count >= 10000
    # (the geolocation case): every test is named with its full count; a row token in the message never shows
    gold_error = ("dbt test.olist.unique_stg_geolocation_zip.9f8e fail: Got 131707 results, configured to fail "
                  "if != 0 ROWTOK7\ndbt test.olist.not_null_kpi_gmv_day_gmv.77aa fail: Got 4 results, configured "
                  "to fail if != 0")
    n4 = notifier.Notifier(fake, "governor", values=lambda t: {"target": str(target), "gold": {"escalated": {
        "model": None, "error": gold_error}}}, store=n.store)
    n.handle({"kind": "run_started", "thread_id": TD, "project": "olist"})
    n4.handle({"kind": "escalated", "thread_id": TD, "stage": "gold", "model": None, "status": graph.ESCALATED})
    rec = n.store.get(TD)
    head = _header(_last_update(fake, rec["ts"]))
    esc = [c for c in fake.named("chat_postMessage") if c.get("thread_ts") == rec["ts"]][-1]
    reply = json.dumps(esc["blocks"])
    for shown in (head, reply):
        assert "unique_stg_geolocation_zip (131707 failures)" in shown
        assert "not_null_kpi_gmv_day_gmv (4 failures)" in shown
        assert "ROWTOK7" not in shown
    assert "ROWTOK7" not in json.dumps(fake.calls) + json.dumps(n.store.all())
    # nothing at all: the stage stands in, the error is never empty
    n3 = notifier.Notifier(fake, "governor", values=lambda t: None, store=n.store)
    n3.handle({"kind": "escalated", "thread_id": TC, "stage": "silver"})
    esc = fake.named("chat_postMessage")[-1]
    assert "`silver stage`" in esc["blocks"][0]["text"]["text"] and "no error recorded" in esc["blocks"][1]["text"]["text"]


def test_new_run_supersedes_open_thread(tmp_path, fake):
    n = notifier.Notifier(fake, "governor")
    _seed(n)
    before = n.store.all()
    started = []
    gov = GovernorSlack(_config(tmp_path), fake, notifier=n, runner=_inline, llm_factory=lambda spec: object(),
                        build=SimpleNamespace(start=lambda *a, **k: started.append(k["thread_id"]) or
                                              {"status": graph.AWAITING}))
    resp = Responder()
    gov.handle_command(APPROVER, "run olist", resp)
    assert len(started) == 1
    new = started[0]
    after = n.store.all()
    assert after[TA]["outcome"] == blocks.SUPERSEDED and after[TA]["superseded_by"] == new
    head = _header(_last_update(fake, after[TA]["ts"]))
    assert head.startswith(f":white_circle: superseded by `{new[:8]}`")
    assert ":heavy_minus_sign: silver built" in _checklist(_last_update(fake, after[TA]["ts"]))
    # a design waiting at the gate is not superseded; other projects and ended runs are untouched
    for tid in (TB, TC, TD):
        assert after[tid] == before[tid], tid
    assert new not in after  # the new build thread itself is not touched
    assert not any("Run finished" in c["text"] for c in fake.named("chat_postMessage"))


def test_startup_marks_interrupted_threads(tmp_path, fake):
    n = notifier.Notifier(fake, "governor")
    _seed(n)
    before = n.store.all()
    gov = GovernorSlack(_config(tmp_path), fake, notifier=n, runner=_inline)
    assert sorted(gov.mark_interrupted()) == sorted([TA, TC])
    after = n.store.all()
    for tid in (TA, TC):
        assert after[tid]["outcome"] == blocks.INTERRUPTED
        assert _header(_last_update(fake, after[tid]["ts"])).startswith(":white_circle: interrupted (bot restarted)")
    assert after[TB] == before[TB] and after[TB]["status"] == graph.AWAITING  # the gate survives a restart
    assert after[TD] == before[TD]
    assert gov.mark_interrupted() == []  # already ended


def test_no_finished_reply_at_the_gate(tmp_path, monkeypatch, fake, profile, good):
    n = _wire(monkeypatch, fake)
    started = []

    def start(*a, **k):
        out = graph.start(*a, profile=profile, **k)
        started.append(out)
        return out

    gov = GovernorSlack(_config(tmp_path), fake, notifier=n, runner=_inline,
                        llm_factory=lambda spec: FakeBuildLLM({"propose": [json.dumps(good)]}),
                        build=SimpleNamespace(start=start))
    gov.handle_command(APPROVER, "run olist", Responder())
    assert started and started[0]["status"] == graph.AWAITING
    tid = started[0]["thread_id"]
    ts = n.store.get(tid)["ts"]
    replies = [c for c in fake.named("chat_postMessage") if c.get("thread_ts") == ts]
    assert len(replies) == 1 and replies[0]["text"].startswith("Design for build")  # the card is the message
    assert not any("finished" in c["text"] for c in fake.named("chat_postMessage"))
    assert "awaiting_design_approval" in _last_update(fake, ts)["text"]

    # an exception in the run itself still says so
    gov.build = SimpleNamespace(start=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    gov.handle_command(APPROVER, "run olist", Responder())
    assert fake.named("chat_postMessage")[-1]["text"].startswith(":warning: run failed: RuntimeError: boom")


def test_non_runner_cannot_start_a_build(tmp_path, fake):
    started = []
    build = SimpleNamespace(start=lambda *a, **k: started.append(k) or {"status": graph.AWAITING})
    gov = GovernorSlack(_config(tmp_path), fake, runner=lambda fn: started.append(fn), build=build)
    resp = Responder()
    gov.handle_command(OTHER, "run olist", resp)  # default: only the approvers may run
    assert resp.text == RUN_REFUSAL and resp.said[0]["response_type"] == "ephemeral"
    assert started == [] and fake.calls == []
    gov.handle_command(APPROVER, "run olist", resp)
    assert len(started) == 1

    started.clear()
    gov = GovernorSlack(_config(tmp_path, GOVERNOR_SLACK_RUNNERS="U_RUNNER, U_OTHER2"), fake,
                        runner=lambda fn: started.append(fn), build=build)
    for user in (APPROVER, OTHER):
        resp = Responder()
        gov.handle_command(user, "run olist", resp)
        assert resp.text == RUN_REFUSAL
    assert started == []
    gov.handle_command("U_RUNNER", "run olist", Responder())
    assert len(started) == 1
    # a runner is not an approver
    resp = Responder()
    gov.handle_command("U_RUNNER", "status", resp)
    assert "Only" not in resp.text
    gov_threads = GovernorSlack(_config(tmp_path, GOVERNOR_SLACK_RUNNERS="U_RUNNER"), fake, threads=lambda: [TA],
                                runner=_inline, build=build)
    gov_threads.handle_command("U_RUNNER", f"approve {TA}", resp)
    assert "Only approvers" in resp.said[-1]["text"]


def test_design_upload_omits_mappings(tmp_path, monkeypatch, fake, profile, good):
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    upload = fake.named("files_upload_v2")
    assert len(upload) == 1 and upload[0]["filename"] == "design.md" and "file" not in upload[0]
    content = upload[0]["content"]
    builds = [k for k in good["kpis"] if k["decision"] == "build"]
    rows = [ln for ln in content.splitlines() if ln.startswith("| ") and "| build |" in ln]
    assert len(rows) == len(builds)
    assert all(ln.rstrip().endswith(f"| {blocks.MAPPINGS_OMITTED} |") for ln in rows)
    kpis = content.split("## KPIs", 1)[1].split("\n## ", 1)[0]
    assert "NOT IN" not in kpis and "order_status" not in kpis and "int_order_lines" not in kpis
    assert "'delivered'" not in content and "'canceled'" not in content  # quoted literals go everywhere
    # the rest of the report is there: declined KPIs with their reason, the gap report
    assert "| conversion_rate | decline |" in content and "## Gap report" in content and "## Silver models" in content
    # the file in the target is unchanged
    on_disk = (tmp_path / "target" / "governor" / "design.md").read_text(encoding="utf-8")
    assert "NOT IN ('canceled', 'unavailable')" in on_disk and blocks.MAPPINGS_OMITTED not in on_disk
    assert tid


def test_published_header_and_link_from_the_event(tmp_path, fake):
    n = notifier.Notifier(fake, "governor")
    n.handle({"kind": "run_started", "thread_id": TA, "project": "olist"})
    n.handle({"kind": "built", "thread_id": TA, "status": graph.BUILT, "kpis_built": 8, "gaps": ["x"]})
    ts = n.store.get(TA)["ts"]
    assert _header(_last_update(fake, ts)).startswith(":large_green_circle: built")
    url = "https://github.com/example/olist-dbt/pull/7"
    n.handle({"kind": "published", "thread_id": TA, "branch": "governor/build-aaaaaaaa", "pr": True, "pr_url": url})
    head = _header(_last_update(fake, ts))
    assert head.startswith(f":large_green_circle: published <{url}|pull request>")
    assert f"<{url}|pull request>" in fake.named("chat_postMessage")[-1]["text"]
    assert ":white_check_mark: published" in _checklist(_last_update(fake, ts))
    # a publish without a pull request still reads as published, with no link
    n.handle({"kind": "published", "thread_id": TA, "branch": "b", "pr": False, "pr_url": None})
    assert _header(_last_update(fake, ts)).startswith(":large_green_circle: published:")
