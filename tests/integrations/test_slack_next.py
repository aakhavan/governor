"""D9c next steps in the channel (batch2c section 21), offline: the "Next" line and the Open pull request button,
the published header with the PR link (or the branch), decided buttons replaced, stale presses answered ephemerally."""
import json
from types import SimpleNamespace

import pytest

from governor.build import graph
from governor.build.llm import FakeBuildLLM
from governor.integrations.slack import blocks, notifier
from governor.integrations.slack.app import GovernorSlack
from test_slack import APPROVER, OTHER, Responder, _config, _inline, _no_dbt, _to_gate, _wire

TA = "aaaaaaaa-0000-4000-8000-000000000000"
URL = "https://github.com/example/olist-dbt/pull/7"
BRANCH = "governor/build-aaaaaaaa"


def _built(fake, tmp_path) -> notifier.Notifier:
    n = notifier.Notifier(fake, "governor", values=lambda t: {}, targets=_config(tmp_path).targets)
    n.handle({"kind": "run_started", "thread_id": TA, "project": "olist"})
    n.handle({"kind": "approved", "thread_id": TA, "by": "Amir Akhavan", "ts": "2026-11-08T09:30:00+00:00"})
    n.handle({"kind": "built", "thread_id": TA, "status": graph.BUILT, "kpis_built": 8, "tests_passed": 40,
              "gaps": ["conversion_rate"]})
    return n


def _certify(tmp_path) -> str:
    return f'python -m governor.build certify --target {_config(tmp_path).targets["olist"]} --by "Amir Akhavan"'


def _progress(fake, n) -> list[dict]:
    ts = n.store.get(TA)["ts"]
    return [u for u in fake.named("chat_update") if u["ts"] == ts][-1]["blocks"]


def _actions(block_list) -> list[tuple[str, str, str]]:
    return [(e["action_id"], e["value"], e["text"]["text"]) for b in block_list if b["type"] == "actions"
            for e in b["elements"]]


def _texts(block_list) -> str:
    return "\n".join(b["text"]["text"] for b in block_list if b["type"] == "section")


def _replies(fake, n) -> list[dict]:
    ts = n.store.get(TA)["ts"]
    return [c for c in fake.named("chat_postMessage") if c.get("thread_ts") == ts]


def test_built_message_shows_next_step_and_pr_button(tmp_path, fake):
    n = _built(fake, tmp_path)
    progress = _progress(fake, n)
    text = json.dumps(progress)
    assert progress[0]["text"]["text"].startswith(":large_green_circle: built")
    assert "*Next:* press *Open pull request* below" in text and "/governor publish" not in text
    assert _actions(progress) == [(blocks.PUBLISH_ACTION, TA, "Open pull request")]
    # the thread's Built reply: the summary, the three steps with the certify line, the same button
    built = _replies(fake, n)[-1]
    reply = "\n".join(b["text"]["text"] for b in built["blocks"] if b["type"] == "section")
    assert reply.startswith("Built: 8 KPIs, 40 tests passed, gaps: `conversion_rate`.")
    assert "① press *Open pull request* below" in reply and "/governor publish" not in reply
    assert "② review and merge it on GitHub" in reply
    # the certify command alone on its own line in a code block, so it copies cleanly (17 Nov)
    assert f"③ certify in a terminal:\n```{_certify(tmp_path)}```" in reply
    assert _actions(built["blocks"]) == [(blocks.PUBLISH_ACTION, TA, "Open pull request")]
    assert n.store.get(TA)["built_ts"]


def test_pr_button_requires_approver(tmp_path, fake):
    n = _built(fake, tmp_path)
    published = []
    target = tmp_path / "target"
    gov = GovernorSlack(_config(tmp_path), fake, notifier=n, runner=_inline, values=lambda t: {"target": str(target)},
                        publisher=lambda t, open_pr: published.append((t, open_pr)) or {"status": "published"})
    before = len(fake.calls)
    resp = Responder()
    gov.handle_publish_button(OTHER, TA, resp)
    assert "Only approvers" in resp.text and resp.said[-1]["response_type"] == "ephemeral"
    assert resp.said[-1]["replace_original"] is False
    assert published == [] and len(fake.calls) == before
    gov.handle_publish_button(APPROVER, TA, resp)
    assert published == [(target, False)]  # no git origin: no pull request is opened


def test_published_header_links_pr_and_says_certify(tmp_path, fake):
    n = _built(fake, tmp_path)
    built_ts = n.store.get(TA)["built_ts"]
    n.handle({"kind": "published", "thread_id": TA, "branch": BRANCH, "pr": True, "pr_url": URL})
    progress = _progress(fake, n)
    assert progress[0]["text"]["text"].startswith(f":large_green_circle: published: <{URL}>")
    nxt = f"*Next:* Review and merge on GitHub, then certify in a terminal:\n```{_certify(tmp_path)}```"
    assert nxt in _texts(progress)
    assert _actions(progress) == []  # the button is gone from the channel message
    # the Built reply's button is replaced by the link
    upd = [u for u in fake.named("chat_update") if u["ts"] == built_ts][-1]
    assert _actions(upd["blocks"]) == [] and f"<{URL}|pull request>" in json.dumps(upd["blocks"])
    # the thread gets the link and the same line
    last = _replies(fake, n)[-1]
    sections = [b["text"]["text"] for b in last["blocks"]]
    assert f"<{URL}|pull request>" in sections[0] and sections[1] == nxt


def test_published_without_pr_url_names_branch(tmp_path, fake):
    n = _built(fake, tmp_path)
    n.handle({"kind": "published", "thread_id": TA, "branch": BRANCH, "pr": False, "pr_url": None})
    progress = _progress(fake, n)
    head = progress[0]["text"]["text"]
    assert head.startswith(f":large_green_circle: published: branch `{BRANCH}`") and "http" not in head
    text = _texts(progress)
    assert f"merge branch `{BRANCH}` into `main` locally, then certify in a terminal:\n```{_certify(tmp_path)}```" in text
    last = _replies(fake, n)[-1]
    assert f"merge branch `{BRANCH}` into `main` locally" in last["blocks"][1]["text"]["text"]
    assert _actions(progress) == []


def test_design_buttons_replaced_after_approve(tmp_path, monkeypatch, fake, profile, good):
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    card_ts = notifier.MessageStore().get(tid)["card_ts"]
    gov = GovernorSlack(_config(tmp_path), fake, runner=_inline, llm_factory=lambda spec: FakeBuildLLM({}),
                        build=SimpleNamespace(approve=lambda t, by, llm: graph.approve(t, by, llm, dbt_runner=_no_dbt)))
    gov.handle_approve_button(APPROVER, tid, Responder(), message_ts=card_ts)
    upd = [u for u in fake.named("chat_update") if u["ts"] == card_ts]
    assert len(upd) == 1 and _actions(upd[0]["blocks"]) == []
    decided = json.dumps(upd[0]["blocks"])
    assert ":white_check_mark: Approved by Amir Akhavan at <!date^" in decided
    assert "7 silver models, 8 KPIs to build" in decided  # the card itself stays
    assert notifier.MessageStore().get(tid)["card_decided"] is True

    # Reject from Slack: the card says who and why; the next proposal gets a fresh card with buttons
    tid2 = _to_gate(tmp_path, profile, good)
    card2 = notifier.MessageStore().get(tid2)["card_ts"]
    gov.llm_factory = lambda spec: FakeBuildLLM({"propose": [json.dumps(good)]})
    gov.build = graph
    assert gov.handle_reject_submit(APPROVER, tid2, "use int_orders for delivery") is None
    upd = [u for u in fake.named("chat_update") if u["ts"] == card2]
    assert len(upd) == 1 and _actions(upd[0]["blocks"]) == []
    assert ":x: Rejected by Amir Akhavan: use int_orders for delivery" in json.dumps(upd[0]["blocks"])
    rec = notifier.MessageStore().get(tid2)
    assert rec["card_ts"] != card2 and not rec["card_decided"]
    new_card = [c for c in fake.named("chat_postMessage") if c.get("ts") is None and c.get("blocks")
                and c.get("thread_ts") == rec["ts"]][-1]
    assert [a[0] for a in _actions(new_card["blocks"])] == [blocks.APPROVE_ACTION, blocks.REJECT_ACTION]


def test_stale_button_press_changes_nothing(tmp_path, monkeypatch, fake, profile, good):
    _wire(monkeypatch, fake)
    tid = _to_gate(tmp_path, profile, good)
    card_ts = notifier.MessageStore().get(tid)["card_ts"]

    def nope(*a, **k):
        pytest.fail("a stale button reached the build")

    gov = GovernorSlack(_config(tmp_path), fake, runner=_inline, llm_factory=lambda spec: FakeBuildLLM({}),
                        build=SimpleNamespace(approve=nope, reject=nope), publisher=nope)
    store_before, calls_before = json.dumps(notifier.MessageStore().all()), len(fake.calls)
    resp = Responder()
    # a press from an older card of the same thread
    gov.handle_approve_button(APPROVER, tid, resp, message_ts="1600000000.000001")
    gov.handle_reject_button(APPROVER, tid, "trig", resp, message_ts="1600000000.000001")
    # the build is not built yet: the publish button is stale
    gov.handle_publish_button(APPROVER, tid, resp)
    # the design decided (here from the terminal): approve, reject and the reject modal are stale
    notifier.Notifier(fake, "governor").decide_card(tid, blocks.decided_line("approve", "Amir Akhavan"))
    store_before, calls_before = json.dumps(notifier.MessageStore().all()), len(fake.calls)
    gov.handle_approve_button(APPROVER, tid, resp, message_ts=card_ts)
    gov.handle_reject_button(APPROVER, tid, "trig", resp, message_ts=card_ts)
    errors = gov.handle_reject_submit(APPROVER, tid, "change it")
    assert errors and "already decided" in errors["errors"][blocks.NOTE_BLOCK]
    assert len(resp.said) == 5
    assert all("out of date" in s["text"] and s["response_type"] == "ephemeral" and s["replace_original"] is False
               for s in resp.said)
    assert len(fake.calls) == calls_before and fake.named("views_open") == []
    assert json.dumps(notifier.MessageStore().all()) == store_before

    # a published build: the publish button is stale
    n = notifier.Notifier(fake, "governor", values=lambda t: {})
    n.handle({"kind": "run_started", "thread_id": TA, "project": "olist"})
    n.handle({"kind": "built", "thread_id": TA, "status": graph.BUILT})
    n.handle({"kind": "published", "thread_id": TA, "branch": BRANCH, "pr": True, "pr_url": URL})
    before = (len(fake.calls), json.dumps(notifier.MessageStore().all()))
    gov.handle_publish_button(APPROVER, TA, resp)
    assert "out of date" in resp.said[-1]["text"] and resp.said[-1]["response_type"] == "ephemeral"
    assert (len(fake.calls), json.dumps(notifier.MessageStore().all())) == before
