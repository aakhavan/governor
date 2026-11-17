"""D9 Slack app (batch2c section 17), offline: a fake Slack client, the fake build LLM, the sample design."""
import json
import uuid
from datetime import date
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest

from governor.build import events, graph
from governor.build.llm import FakeBuildLLM
from governor.core.catalogue import load_approved
from governor.integrations.slack import blocks, notifier
from governor.integrations.slack.app import GovernorSlack, UsageError, parse_command
from governor.integrations.slack.config import NOTIFIER_SPEC, SlackConfig

APPROVER, OTHER = "U_AMIR", "U_GUEST"
TID = "0f1e2d3c-4b5a-6978-8a9b-0c1d2e3f4a5b"


def _config(tmp_path, **kw) -> SlackConfig:
    env = {"GOVERNOR_SLACK_APPROVERS": APPROVER, "GOVERNOR_SLACK_NAMES": f"{APPROVER}=Amir Akhavan",
           "GOVERNOR_SLACK_TARGETS": f"olist={tmp_path / 'target'}", "GOVERNOR_SLACK_LLM": "fake:none", **kw}
    return SlackConfig.from_env(env)


class Responder:
    def __init__(self):
        self.said: list[dict] = []

    def __call__(self, **kw):
        self.said.append(kw)

    @property
    def text(self) -> str:
        return "\n".join(s.get("text", "") for s in self.said)


def _wire(monkeypatch, client) -> notifier.Notifier:
    """Register the Slack notifier for build events, with the fake client."""
    n = notifier.Notifier(client, "governor")
    notifier.configure(n)
    monkeypatch.setenv("GOVERNOR_BUILD_NOTIFIERS", NOTIFIER_SPEC)
    return n


def _to_gate(tmp_path, profile, good) -> str:
    llm = FakeBuildLLM({"propose": [json.dumps(good)]})
    out = graph.start(tmp_path / "target", "olist", llm, profile=profile)
    assert out["status"] == graph.AWAITING
    return out["thread_id"]


def _no_dbt(target, args):
    raise AssertionError("dbt must not run while SQL is refused")


def _inline(fn):
    fn()


def test_command_parsing_is_strict(tmp_path, fake, profile, good):
    # the real checkpoints file: a built thread is listed and its short id resolves
    tid = _to_gate(tmp_path, profile, good)
    listed = notifier.known_threads()
    assert tid in listed
    assert parse_command(f"approve {tid[:8]}", {"olist"}, listed).thread_id == tid

    targets, threads = {"olist"}, [TID]
    assert parse_command("run olist", targets, threads).target == "olist"
    assert parse_command("status", targets, threads).action == "status"
    assert parse_command(f"approve {TID}", targets, threads).thread_id == TID
    assert parse_command(f"publish {TID[:8]}", targets, threads).thread_id == TID  # the short id the messages show
    r = parse_command(f"reject {TID}  use int_orders for delivery", targets, threads)
    assert (r.action, r.thread_id, r.note) == ("reject", TID, "use int_orders for delivery")
    for bad in ("", "run", "run shop", "run olist extra", "run ../olist", "status now", "approve",
                "approve 0f1e", f"approve {TID} now", "approve nope-nope-nope", f"reject {TID}",
                f"publish {TID} --open-pr", "certify olist", "RUN olist", "drop table raw.orders"):
        with pytest.raises(UsageError):
            parse_command(bad, targets, threads)
    with pytest.raises(UsageError):  # an ambiguous prefix is not a thread
        parse_command("approve 0f1e2d3c", targets, [TID, TID[:8] + "-other"])

    started = []
    gov = GovernorSlack(_config(tmp_path), fake, runner=lambda fn: started.append(fn), threads=lambda: threads,
                        build=SimpleNamespace(start=lambda *a, **k: pytest.fail("no build")))
    resp = Responder()
    gov.handle_command(APPROVER, "run elsewhere", resp)
    assert "Usage:" in resp.text and "`olist`" in resp.text and resp.said[0]["response_type"] == "ephemeral"
    assert started == [] and fake.calls == []
    gov.handle_command(APPROVER, "run olist", resp)
    assert len(started) == 1  # the work is handed to the background runner after the answer

    # The background job prepares the target like the CLI run does (init_target), then starts the build.
    calls, llm = [], object()
    gov.llm_factory = lambda spec: llm
    gov.build = SimpleNamespace(start=lambda *a, **k: calls.append((a, k)) or {"status": "design_gate"})
    started[0]()
    assert len(calls) == 1, fake.calls
    args, kwargs = calls[0]
    target = gov.config.targets["olist"]
    assert args[:3] == (target, "olist", llm)
    uuid.UUID(str(kwargs["thread_id"]))
    assert (Path(target) / "dbt_project.yml").exists()


def test_non_approver_cannot_approve(tmp_path, fake):
    def nope(*a, **k):
        pytest.fail("a non-approver reached the build")

    build = SimpleNamespace(approve=nope, reject=nope, start=nope)
    gov = GovernorSlack(_config(tmp_path), fake, runner=_inline, threads=lambda: [TID], build=build, publisher=nope)
    for text in (f"approve {TID}", f"reject {TID} no", f"publish {TID}"):
        resp = Responder()
        gov.handle_command(OTHER, text, resp)
        assert "Only approvers" in resp.text and resp.said[0]["response_type"] == "ephemeral"
    resp = Responder()
    gov.handle_approve_button(OTHER, TID, resp)
    assert "Only approvers" in resp.text and resp.said[0]["replace_original"] is False
    gov.handle_reject_button(OTHER, TID, "trig", resp)
    assert fake.named("views_open") == []
    errors = gov.handle_reject_submit(OTHER, TID, "change it")
    assert errors["response_action"] == "errors" and "Only approvers" in errors["errors"][blocks.NOTE_BLOCK]
    # an empty allowlist means nobody approves
    gov2 = GovernorSlack(_config(tmp_path, GOVERNOR_SLACK_APPROVERS=""), fake, runner=_inline, threads=lambda: [TID],
                         build=build)
    gov2.handle_approve_button(APPROVER, TID, resp)
    assert "Only approvers" in resp.said[-1]["text"]


def test_approve_button_calls_graph_with_mapped_name(tmp_path, monkeypatch, fake, profile, good):
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    calls = []

    def approve(thread_id, by, llm):
        calls.append((thread_id, by))
        return graph.approve(thread_id, by, llm, dbt_runner=_no_dbt)

    gov = GovernorSlack(_config(tmp_path), fake, runner=_inline, llm_factory=lambda spec: FakeBuildLLM({}),
                        build=SimpleNamespace(approve=approve))
    resp = Responder()
    gov.handle_approve_button(APPROVER, tid, resp)
    assert calls == [(tid, "Amir Akhavan")]
    assert "working on it" in resp.text
    decisions = load_approved(tmp_path / "target" / "governor" / "approved.yaml").decisions
    assert decisions and {d.approved_by for d in decisions} == {"Amir Akhavan"}
    # the outcome lands in the Slack thread under the build message
    ts = notifier.MessageStore().get(tid)["ts"]
    replies = [c["text"] for c in fake.named("chat_postMessage") if c.get("thread_ts") == ts]
    assert any("Approved by Amir Akhavan" in t for t in replies)
    # a second click on the (stale) button is answered ephemerally and changes nothing (batch2c section 21)
    posted = len(fake.calls)
    gov.handle_approve_button(APPROVER, tid, resp)
    assert "out of date" in resp.said[-1]["text"] and resp.said[-1]["response_type"] == "ephemeral"
    assert len(fake.calls) == posted and len(calls) == 1

    # Reject: the button opens the note modal; its submission calls graph.reject with the note
    tid2 = _to_gate(tmp_path, profile, good)
    rejected = []
    gov.build = SimpleNamespace(reject=lambda t, note, llm: rejected.append((t, note)) or {"status": graph.AWAITING})
    gov.handle_reject_button(APPROVER, tid2, "trigger-1", resp)
    view = fake.named("views_open")[-1]
    assert view["trigger_id"] == "trigger-1" and view["view"]["private_metadata"] == tid2
    assert gov.handle_reject_submit(APPROVER, tid2, "  ") is not None
    assert gov.handle_reject_submit(APPROVER, tid2, "use int_orders") is None
    assert rejected == [(tid2, "use int_orders")]


def test_progress_message_updates_in_place(tmp_path, monkeypatch, fake, profile, good):
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    tops = [c for c in fake.named("chat_postMessage") if "thread_ts" not in c]
    assert len(tops) == 1 and tops[0]["channel"] == "governor"  # one message per build thread
    rec = json.loads((graph.state_dir() / notifier.MESSAGES_FILE).read_text(encoding="utf-8"))[tid]
    updates = fake.named("chat_update")
    assert len(updates) >= 3 and {(u["channel"], u["ts"]) for u in updates} == {(rec["channel"], rec["ts"])}
    checklist = updates[-1]["blocks"][1]["text"]["text"]
    for label in ("profiled", "design proposed", "validated", "waiting for approval"):
        assert f":white_check_mark: {label}" in checklist
    for label in ("approved", "silver built", "gold built", "published"):
        assert f":white_large_square: {label}" in checklist
    assert "awaiting_design_approval" in updates[-1]["text"] and "SQL repairs: 0" in json.dumps(updates[-1])

    # later events (a new process, the same state file) keep updating the same message
    events.emit("approved", thread_id=tid, by="Amir Akhavan")
    events.emit("repair", thread_id=tid, models=["int_orders"], repairs=1, cost_usd=0.001)
    assert len([c for c in fake.named("chat_postMessage") if "thread_ts" not in c]) == 1
    last = fake.named("chat_update")[-1]
    assert last["ts"] == rec["ts"] and ":white_check_mark: approved" in last["blocks"][1]["text"]["text"]
    assert "SQL repairs: 1" in json.dumps(last)


def test_design_card_has_counts_gaps_and_buttons(tmp_path, monkeypatch, fake, profile, good):
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    ts = notifier.MessageStore().get(tid)["ts"]
    cards = [c for c in fake.named("chat_postMessage") if c.get("thread_ts") == ts and c.get("blocks")]
    assert len(cards) == 1
    card = json.dumps(cards[0]["blocks"])
    assert "7 silver models, 8 KPIs to build, 2 to decline, 0 validation findings" in card
    assert "`int_orders` (intermediate)" in card and "`gmv`" in card
    assert "`conversion_rate`: no session or visit data in raw" in card
    assert "`gross_margin`: no product cost data in raw" in card
    actions = next(b for b in cards[0]["blocks"] if b["type"] == "actions")["elements"]
    assert [(a["action_id"], a["value"], a["text"]["text"]) for a in actions] == [
        (blocks.APPROVE_ACTION, tid, "Approve"), (blocks.REJECT_ACTION, tid, "Reject")]
    upload = fake.named("files_upload_v2")
    assert len(upload) == 1 and upload[0]["filename"] == "design.md" and upload[0]["thread_ts"] == ts
    assert upload[0]["content"].startswith("#") and "## KPIs" in upload[0]["content"]

    # an invalid design has its findings and no buttons
    _, invalid = blocks.design_card(tid, good, [{"code": "MAPPING_UNKNOWN_COLUMN", "subject": "kpi.gmv",
                                                 "problem": "no column item_price"}], graph.INVALID)
    text = json.dumps(invalid)
    assert "1 validation findings" in text and "MAPPING_UNKNOWN_COLUMN" in text
    assert not any(b["type"] == "actions" for b in invalid)
    modal = blocks.reject_modal(tid)
    assert modal["callback_id"] == blocks.REJECT_MODAL and modal["blocks"][1]["block_id"] == blocks.NOTE_BLOCK


def test_notifier_failure_never_breaks_a_build(tmp_path, monkeypatch, failing, profile, good):
    _wire(monkeypatch, failing)
    tid = _to_gate(tmp_path, profile, good)  # every Slack call raises; the build still reaches the gate
    assert failing.calls and graph.approve(tid, "amir", FakeBuildLLM({}), dbt_runner=_no_dbt)["status"] == graph.ESCALATED
    notifier.notify({"kind": "design_gate"})  # no thread id
    notifier.notify(None)  # not even a dict
    # without a token the notifier is a no-op
    notifier.configure(None)
    notifier.notify({"kind": "profiled", "thread_id": tid})
    # an unwritable message store is logged, not raised
    broken = notifier.Notifier(failing, "governor", store=notifier.MessageStore(tmp_path / "missing" / "x" / "\0bad"))
    notifier.configure(broken)
    assert events.emit("profiled", thread_id=tid, tables=1)["kind"] == "profiled"


def test_no_data_values_in_slack_payloads(tmp_path, monkeypatch, fake, profile, good):
    for t in profile["tables"]:
        for c in t["columns"]:
            c["min"], c["max"] = "SENTINEL_MIN_7731", "SENTINEL_MAX_8842"
    good["kpis"][-1]["reason"] = "raw has no cost column; 'SENTINEL_REASON_5519' is a status, not a cost"
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    out = graph.approve(tid, "Amir Akhavan", FakeBuildLLM({}), dbt_runner=_no_dbt)  # escalates: an error in Slack
    assert out["status"] == graph.ESCALATED
    ts = notifier.MessageStore().get(tid)["ts"]
    posted = [c for c in fake.named("chat_postMessage")
              if c.get("thread_ts") == ts and "escalated" in c.get("text", "")]
    assert len(posted) == 1, "the real escalation is posted in the build thread"
    sections = [b["text"]["text"] for b in posted[0]["blocks"] if b.get("type") == "section"]
    assert any(s.startswith("```") and len(s) > 6 for s in sections), "the escalation carries the model's error"
    events.emit("published", thread_id=tid, branch="governor/build-x", commit="abc", kpis=8, gaps=2, pr=False)
    _, esc = blocks.escalation(tid, "silver", "stg_orders",
                               "invalid input syntax for type integer: 'SENTINEL_LITERAL_4410'\n"
                               "invalid input syntax for type integer: \"SENTINEL_DQ_6627\"\n"
                               "DETAIL: Key (order_id)=(SENTINEL_KEY_9921) already exists.\n"
                               "LINE 3: where amount > 123456789")
    payload = json.dumps(fake.calls) + json.dumps(esc)
    assert fake.named("chat_update") and "escalated" in payload
    for value in ("SENTINEL_MIN_7731", "SENTINEL_MAX_8842", "SENTINEL_REASON_5519", "SENTINEL_LITERAL_4410",
                  "SENTINEL_DQ_6627", "SENTINEL_KEY_9921", "123456789", "'delivered'", "unavailable", "'canceled'"):
        assert value not in payload, value


# ---- batch3 section 29: force and up-to-date runs

def test_slack_run_force_parses(tmp_path, fake):
    targets, threads = {"olist"}, [TID]
    plain = parse_command("run olist", targets, threads)
    assert (plain.action, plain.target, plain.force) == ("run", "olist", False)
    forced = parse_command("run olist force", targets, threads)
    assert (forced.action, forced.target, forced.force) == ("run", "olist", True)
    for bad in ("run olist FORCE", "run olist --force", "run olist force now", "run force", "run olist forced"):
        with pytest.raises(UsageError):
            parse_command(bad, targets, threads)

    started, calls = [], []
    gov = GovernorSlack(_config(tmp_path), fake, runner=lambda fn: started.append(fn), threads=lambda: threads,
                        llm_factory=lambda spec: object(),
                        build=SimpleNamespace(start=lambda *a, **k: calls.append(k) or {"status": "up_to_date"}))
    gov.handle_command(APPROVER, "run olist force", Responder())
    gov.handle_command(APPROVER, "run olist", Responder())
    for fn in started:
        fn()
    assert [k.get("force") for k in calls] == [True, None]  # a plain run calls start exactly as before


def test_slack_up_to_date_message(tmp_path, monkeypatch, fake, profile, good):
    last = _to_gate(tmp_path, profile, good)
    target = tmp_path / "target"
    graph.write_fingerprint(target, profile, date(2026, 11, 17), last)
    (target / "governor" / "build.json").write_text(json.dumps({"status": "built", "thread_id": last}),
                                                    encoding="utf-8")
    _wire(monkeypatch, fake)
    llm = FakeBuildLLM({})
    out = graph.start(target, "olist", llm, profile=profile, dbt_runner=_no_dbt)
    assert out["status"] == graph.UP_TO_DATE and llm.calls == []
    posts = fake.named("chat_postMessage")
    assert len(posts) == 1 and "thread_ts" not in posts[0]  # the one message, no thread replies
    assert fake.named("files_upload_v2") == []
    final = fake.named("chat_update")[-1]
    assert final["blocks"][0]["text"]["text"].startswith(
        f":white_check_mark: up to date: no change since build {last[:8]}")
    assert not any(b.get("type") == "actions" for b in final["blocks"])  # no buttons
    rec = notifier.MessageStore().get(out["thread_id"])
    assert rec["outcome"] == blocks.UP_TO_DATE and not notifier.is_open(rec)
    assert notifier.Notifier(fake, "governor").supersede("olist", "newer") == []  # terminal: never superseded
