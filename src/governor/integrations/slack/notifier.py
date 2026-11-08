"""Build notifier for Slack (batch2c section 17), registered as
``GOVERNOR_BUILD_NOTIFIERS=governor.integrations.slack.notifier:notify``.

One message per build thread in ``GOVERNOR_SLACK_CHANNEL``, updated in place with the stage checklist, repairs and
cost; details go in the Slack thread under it:

- ``design_gate``: the design card (silver models, KPIs to build and to decline with gap reasons, validation
  findings, Approve / Reject buttons) and ``governor/design.md`` attached without its KPI mapping values;
- ``escalated``: the failing node and its error, without data values (checkpoint, then the target's
  ``target/run_results.json``, then the stage);
- ``published``: the branch and the pull-request link (the event's ``pr_url``).

Ended runs read as ended (batch2c section 20): the header turns red (``stopped at <stage>`` and a one-line reason)
or green (built, published); records left open by a newer run of the project or by a restart are marked
superseded or interrupted. A record waiting at the design gate stays open.

Next steps in the channel (batch2c section 21): a built run's message carries a "Next" line and the **Open pull
request** button, and so does the thread's "Built" reply (with the three steps and the certify line: the target path
from ``GOVERNOR_SLACK_TARGETS`` and the approver's mapped name). Once published, the header links the pull request
(or names the branch to merge locally) and the button gives way to the link. After approve or reject the design
card's buttons give way to the decision (``card_ts`` and ``built_ts`` in the record name those replies).

The card and the escalation read the build thread's checkpoint (proposal, findings, target, escalation); events
themselves carry only counts, names and codes. Build thread id to message timestamp lives in
``GOVERNOR_STATE_DIR/slack_messages.json``. ``notify`` never raises: a Slack failure is logged and the build goes on.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from pathlib import Path
from typing import Any, Callable

from governor.build import graph
from governor.integrations.slack import blocks
from governor.integrations.slack.config import SlackConfig

log = logging.getLogger(__name__)

MESSAGES_FILE = "slack_messages.json"
_STAGE_KEYS = {k for k, _ in blocks.STAGES}


# --------------------------------------------------------------------------- build state (read only)


def checkpoints_path() -> Path:
    return graph.state_dir() / graph.CHECKPOINT_FILE


def thread_values(thread_id: str, checkpoints: str | Path | None = None) -> dict | None:
    """The latest checkpointed state of a build thread, or None when the thread is unknown."""
    from langgraph.checkpoint.sqlite import SqliteSaver

    path = Path(checkpoints) if checkpoints else checkpoints_path()
    if not path.is_file():
        return None
    conn = sqlite3.connect(str(path), check_same_thread=False)
    try:
        tup = SqliteSaver(conn).get_tuple({"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}})
    finally:
        conn.close()
    if tup is None:
        return None
    return dict(tup.checkpoint.get("channel_values") or {})


def known_threads(checkpoints: str | Path | None = None) -> list[str]:
    path = Path(checkpoints) if checkpoints else checkpoints_path()
    if not path.is_file():
        return []
    try:
        conn = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    except sqlite3.Error as exc:
        log.warning("cannot open build checkpoints %s: %s", path, exc)
        return []
    try:
        return [r[0] for r in conn.execute("select distinct thread_id from checkpoints").fetchall()]
    except sqlite3.Error as exc:
        log.warning("cannot list build threads in %s: %s", path, exc)
        return []
    finally:
        conn.close()


# --------------------------------------------------------------------------- message state


class MessageStore:
    """Build thread id -> {channel, ts, progress fields} in ``slack_messages.json``."""

    def __init__(self, path: Path | None = None):
        self._path = path
        self._lock = threading.Lock()

    @property
    def path(self) -> Path:
        return self._path or graph.state_dir() / MESSAGES_FILE

    def _load(self) -> dict:
        try:
            return json.loads(self.path.read_text(encoding="utf-8")) if self.path.is_file() else {}
        except (OSError, ValueError):
            return {}

    def get(self, thread_id: str) -> dict | None:
        with self._lock:
            rec = self._load().get(thread_id)
        return dict(rec) if isinstance(rec, dict) else None

    def all(self) -> dict[str, dict]:
        with self._lock:
            return {k: dict(v) for k, v in self._load().items() if isinstance(v, dict)}

    def put(self, thread_id: str, rec: dict) -> None:
        with self._lock:
            data = self._load()
            data[thread_id] = rec
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)


# --------------------------------------------------------------------------- notifier


_FAILED_STAGE = {"silver": "silver_built", "gold": "gold_built"}


def _terminal(rec: dict, event: dict) -> None:
    """Set the record's terminal state (``outcome`` and what the header needs) from an ending event."""
    kind, status = event.get("kind"), event.get("status")
    end: dict | None = None
    if kind == "escalated":
        stage = str(event.get("stage") or "build")
        blueprint = status == graph.BLUEPRINT_FAILED
        end = {"outcome": blocks.FAILED, "failed_stage": _FAILED_STAGE.get(stage, "gold_built"),
               "stopped_at": f"{stage} (blueprint check)" if blueprint else stage,
               "reason": event.get("_reason") or f"the {stage} stage ended with no error recorded"}
    elif kind == "design_gate" and status == graph.INVALID:
        codes = ", ".join(str(c) for c in event.get("codes") or []) or "findings"
        end = {"outcome": blocks.FAILED, "failed_stage": "validated", "stopped_at": "validation",
               "reason": f"design invalid ({codes}); see governor/design.md"}
    elif kind == "rejected" and status == graph.REJECTED:
        end = {"outcome": blocks.FAILED, "failed_stage": "design_gate", "stopped_at": "the design gate",
               "reason": "design rejected for the second time"}
    elif kind == "built":
        end = {"outcome": blocks.BUILT}
    elif kind == "published":
        end = {"outcome": blocks.PUBLISHED, "pr_url": event.get("pr_url"), "branch": event.get("branch")}
    if end is not None:
        for k in ("outcome", "failed_stage", "stopped_at", "reason", "pr_url", "branch", "superseded_by"):
            rec.pop(k, None)
        rec.update({k: v for k, v in end.items() if v is not None})


def is_open(rec: dict) -> bool:
    """Not ended and not waiting at the design gate (a gate survives a restart and can still be approved)."""
    return rec.get("outcome") not in blocks.TERMINAL and rec.get("status") != graph.AWAITING


def read_run_results(target: str | Path | None) -> list[dict]:
    """``target/run_results.json`` in the target project: unique id, status, failure count and message only."""
    if not target:
        return []
    path = Path(target) / "target" / "run_results.json"
    try:
        raw = json.loads(path.read_text(encoding="utf-8")).get("results") or []
    except (OSError, ValueError, AttributeError):
        return []
    return [{"unique_id": r.get("unique_id"), "status": r.get("status"), "failures": r.get("failures"),
             "message": r.get("message")} for r in raw if isinstance(r, dict)]


def _apply(rec: dict, event: dict) -> dict:
    """Fold one build event into the progress record (pure)."""
    rec = dict(rec)
    done = list(rec.get("done") or [])
    kind = event.get("kind")
    if kind == "run_started":
        rec["project"] = event.get("project")
    if kind == "approved" and event.get("by"):
        rec["approved_by"] = event["by"]  # the mapped name, for the certify line
    if kind == "proposed":
        rec["design_repairs"] = int(event.get("repair") or 0)
    if kind == "repair":
        rec["sql_repairs"] = int(event.get("repairs") or 0)
    if kind in ("proposed", "repair") and isinstance(event.get("cost_usd"), (int, float)):
        rec["cost_usd"] = round(float(rec.get("cost_usd") or 0.0) + event["cost_usd"], 6)
    if kind in ("design_gate", "built") and isinstance(event.get("cost_usd"), (int, float)):
        rec["cost_usd"] = event["cost_usd"]  # cumulative over the thread's calls
    if kind == "rejected":
        done = [d for d in done if d not in ("proposed", "validated", "design_gate")]
    gate_ok = kind != "design_gate" or event.get("status") == graph.AWAITING
    if kind in _STAGE_KEYS and gate_ok and kind not in done:
        done.append(kind)
    rec["done"] = done
    _terminal(rec, event)
    rec["status"] = event.get("status") or {
        "run_started": "started", "profiled": "profiled", "proposed": "design proposed", "validated": "validated",
        "approved": "approved, building silver", "silver_built": "silver built, building gold",
        "gold_built": "gold built", "repair": "repairing SQL", "published": "published",
        "certified": "certified"}.get(kind, rec.get("status"))
    return rec


class Notifier:
    def __init__(self, client: Any, channel: str, store: MessageStore | None = None,
                 values: Callable[[str], dict | None] = thread_values, targets: dict[str, Any] | None = None):
        self.client = client
        self.channel = channel
        self.store = store or MessageStore()
        self.values = values
        self.targets = dict(targets or {})  # GOVERNOR_SLACK_TARGETS: project name -> target path

    # ---- posting

    def _thread(self, thread_id: str) -> tuple[str, str | None]:
        rec = self.store.get(thread_id) or {}
        return rec.get("channel") or self.channel, rec.get("ts")

    def reply(self, thread_id: str, text: str, block_list: list[dict] | None = None) -> Any:
        """A detail line under the thread's message (or in the channel when there is none yet). Returns Slack's
        response (its ``ts`` names the reply)."""
        channel, ts = self._thread(thread_id)
        kwargs: dict[str, Any] = {"channel": channel, "text": text}
        if block_list:
            kwargs["blocks"] = block_list
        if ts:
            kwargs["thread_ts"] = ts
        return self.client.chat_postMessage(**kwargs)

    def _values(self, thread_id: str) -> dict:
        try:
            return self.values(thread_id) or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("slack: cannot read the checkpoint of %s: %s", blocks.short(thread_id), type(exc).__name__)
            return {}

    def certify_line(self, thread_id: str, rec: dict) -> str:
        """``python -m governor.build certify --target <path> --by "<name>"``: the path from
        ``GOVERNOR_SLACK_TARGETS`` (else the checkpointed target), the approver's mapped name."""
        target = self.targets.get(rec.get("project") or "") or self._values(thread_id).get("target")
        return blocks.certify_command(target, rec.get("approved_by"))

    def _save(self, thread_id: str, **fields: Any) -> dict | None:
        rec = self.store.get(thread_id)
        if rec is None:
            return None
        rec.update(fields)
        self.store.put(thread_id, rec)
        return rec

    # ---- decided messages (batch2c section 21)

    def decide_card(self, thread_id: str, decision: str) -> bool:
        """Replace the open design card's buttons with ``decision``. False when there is no open card (already
        decided, or none posted): nothing changes then."""
        rec = self.store.get(thread_id)
        if not rec or not rec.get("card_ts") or rec.get("card_decided"):
            return False
        self._save(thread_id, card_decided=True)
        values = self._values(thread_id)
        text, block_list = blocks.design_card(thread_id, values.get("proposal"), values.get("findings"),
                                              str(values.get("status") or ""), decided=decision)
        self.client.chat_update(channel=rec.get("channel") or self.channel, ts=rec["card_ts"], text=text,
                                blocks=block_list)
        return True

    def handle(self, event: dict) -> None:
        thread_id = event.get("thread_id")
        if not thread_id:
            return
        if event.get("kind") == "escalated":
            failure = self.failure(thread_id, event)
            event = {**event, "_failure": failure, "_reason": failure["reason"]}
        rec = _apply(self.store.get(thread_id) or {"done": []}, event)
        self._render(thread_id, rec)
        extra = getattr(self, f"_on_{event.get('kind')}", None)
        if extra is not None:
            extra(thread_id, event, rec)

    def _render(self, thread_id: str, rec: dict) -> None:
        """Post or update the thread's progress message and store the record."""
        certify = self.certify_line(thread_id, rec) if rec.get("outcome") in (blocks.BUILT, blocks.PUBLISHED) else None
        text, block_list = blocks.progress(thread_id, rec, certify)
        if rec.get("ts"):
            self.client.chat_update(channel=rec["channel"], ts=rec["ts"], text=text, blocks=block_list)
        else:
            resp = self.client.chat_postMessage(channel=self.channel, text=text, blocks=block_list)
            rec["ts"], rec["channel"] = resp["ts"], resp.get("channel") or self.channel
        self.store.put(thread_id, rec)

    # ---- ended without an event (a newer run, a restart)

    def open_threads(self, project: str | None = None) -> list[str]:
        """Records that are not terminal and not waiting at the design gate (of one project, when given)."""
        return [tid for tid, rec in self.store.all().items()
                if is_open(rec) and (project is None or rec.get("project") == project)]

    def mark(self, thread_id: str, outcome: str, **fields: Any) -> None:
        """Give an open record a terminal state (superseded or interrupted) and update its message."""
        rec = self.store.get(thread_id)
        if rec is None:
            return
        rec.update({"outcome": outcome, **fields})
        if rec.get("ts"):
            self._render(thread_id, rec)
        else:
            self.store.put(thread_id, rec)

    def supersede(self, project: str, new_thread_id: str) -> list[str]:
        """``/governor run``: every open record of the project is superseded by the new build thread."""
        marked = [t for t in self.open_threads(project) if t != new_thread_id]
        for tid in marked:
            self._safe_mark(tid, blocks.SUPERSEDED, superseded_by=new_thread_id)
        return marked

    def interrupt_open(self) -> list[str]:
        """At app start: open records cannot finish any more (their run died with the old process)."""
        marked = self.open_threads()
        for tid in marked:
            self._safe_mark(tid, blocks.INTERRUPTED)
        return marked

    def _safe_mark(self, thread_id: str, outcome: str, **fields: Any) -> None:
        try:
            self.mark(thread_id, outcome, **fields)
        except Exception as exc:  # noqa: BLE001
            log.warning("slack: cannot mark %s %s: %s", blocks.short(thread_id), outcome, type(exc).__name__)

    # ---- the failure behind an escalation

    def failure(self, thread_id: str, event: dict) -> dict:
        """``{stage, node, error, reason}``: the checkpointed error first, then ``target/run_results.json``, then
        the stage. ``node`` and ``error`` may be None (the escalation reply names the stage then); ``reason`` is one
        scrubbed line for the progress header."""
        stage = str(event.get("stage") or "build")
        if event.get("status") == graph.BLUEPRINT_FAILED:
            error = f"{int(event.get('blueprint_findings') or 0)} blueprint findings (high severity); see governor/build.json"
            return {"stage": stage, "node": "blueprint check", "error": error, "reason": error}
        try:
            values = self.values(thread_id) or {}
        except Exception as exc:  # noqa: BLE001
            log.warning("slack: cannot read the checkpoint of %s: %s", blocks.short(thread_id), type(exc).__name__)
            values = {}
        stage_state = (values.get(stage) or {}) if stage in ("silver", "gold") else {}
        esc = stage_state.get("escalated") or {}
        node = event.get("model") or esc.get("model")
        error = esc.get("error")
        if not error and node:
            # the escalation is emitted inside the node, before its return is checkpointed:
            # the previous checkpoint still holds the failing model's error
            error = ((stage_state.get("failures") or {}).get(node) or "")[-3000:] or None
        if not error:
            rr_node, error = blocks.run_results_failures(read_run_results(values.get("target")))
            node = node or rr_node
        if not node and error:
            tests = blocks.failing_tests(error)
            node = tests[0][0] if tests else None
        reason = blocks.reason_line(error) if error else ""
        return {"stage": stage, "node": node, "error": error,
                "reason": reason or f"the {stage} stage ended with no error recorded"}

    # ---- details in the thread

    def _on_design_gate(self, thread_id: str, event: dict, rec: dict) -> None:
        values = self.values(thread_id) or {}
        text, block_list = blocks.design_card(thread_id, values.get("proposal"), values.get("findings"),
                                              str(event.get("status") or values.get("status")))
        resp = self.client.chat_postMessage(channel=rec["channel"], thread_ts=rec["ts"], text=text, blocks=block_list)
        if resp and resp.get("ts"):
            # the open card: its buttons are replaced once the design is decided (a new card after a reject)
            self._save(thread_id, card_ts=resp["ts"], card_decided=event.get("status") != graph.AWAITING)
        report = Path(values["target"]) / "governor" / "design.md" if values.get("target") else None
        if report is not None and report.is_file():
            # the uploaded copy omits the KPI mapping values (they can hold SQL literals); the file is unchanged
            content = blocks.design_without_mappings(report.read_text(encoding="utf-8"))
            self.client.files_upload_v2(channel=rec["channel"], thread_ts=rec["ts"], content=content,
                                        filename="design.md", title=f"design.md (build {blocks.short(thread_id)})")

    def _on_approved(self, thread_id: str, event: dict, rec: dict) -> None:
        self.decide_card(thread_id, blocks.decided_line("approve", event.get("by"), event.get("ts")))

    def _on_rejected(self, thread_id: str, event: dict, rec: dict) -> None:
        # a Slack reject decided the card already (with the name and note); a terminal reject has neither
        self.decide_card(thread_id, blocks.decided_line("reject"))
        final = event.get("status") == graph.REJECTED
        self.reply(thread_id, "Design rejected for the second time: the thread ends." if final
                   else "Design rejected: the plan model proposes again with the note.")

    def _on_repair(self, thread_id: str, event: dict, rec: dict) -> None:
        models = ", ".join(f"`{m}`" for m in event.get("models") or []) or "(none)"
        self.reply(thread_id, f"SQL repair {int(event.get('repairs') or 0)}: {models}")

    def _on_escalated(self, thread_id: str, event: dict, rec: dict) -> None:
        failure = event.get("_failure") or self.failure(thread_id, event)
        text, block_list = blocks.escalation(thread_id, failure["stage"], failure["node"], failure["error"])
        self.reply(thread_id, text, block_list)

    @staticmethod
    def _built_summary(event_or_rec: dict) -> str:
        gaps = ", ".join(f"`{g}`" for g in event_or_rec.get("gaps") or []) or "none"
        return (f"Built: {int(event_or_rec.get('kpis_built') or 0)} KPIs, "
                f"{int(event_or_rec.get('tests_passed') or 0)} tests passed, gaps: {gaps}.")

    def _on_built(self, thread_id: str, event: dict, rec: dict) -> None:
        summary = self._built_summary(event)
        text, block_list = blocks.built_reply(thread_id, summary, self.certify_line(thread_id, rec))
        resp = self.reply(thread_id, text, block_list)
        if resp and resp.get("ts"):
            # the reply's button is replaced by the link after the publish
            self._save(thread_id, built_ts=resp["ts"], built_summary=summary)

    def _on_published(self, thread_id: str, event: dict, rec: dict) -> None:
        certify = self.certify_line(thread_id, rec)
        stored = self.store.get(thread_id) or rec
        if stored.get("built_ts"):
            text, block_list = blocks.built_reply(thread_id, stored.get("built_summary") or "Built.", certify,
                                                  published_link=blocks.published_link(event.get("pr_url"),
                                                                                       event.get("branch")))
            try:
                self.client.chat_update(channel=stored.get("channel") or self.channel, ts=stored["built_ts"],
                                        text=text, blocks=block_list)
            except Exception as exc:  # noqa: BLE001
                log.warning("slack: cannot replace the publish button of %s: %s", blocks.short(thread_id),
                            type(exc).__name__)
        text, block_list = blocks.published(thread_id, event.get("branch"), event.get("pr_url"),
                                            pr_opened=bool(event.get("pr")), certify=certify)
        self.reply(thread_id, text, block_list)


# --------------------------------------------------------------------------- module entry point

_default: Notifier | None = None
_default_lock = threading.Lock()


def configure(notifier: Notifier | None) -> None:
    """Use this notifier for ``notify`` (the app sets its own client; tests set a fake)."""
    global _default
    _default = notifier


def _from_env() -> Notifier | None:
    global _default
    with _default_lock:
        if _default is None:
            cfg = SlackConfig.from_env()
            if not cfg.bot_token:
                return None
            from slack_sdk import WebClient

            _default = Notifier(WebClient(token=cfg.bot_token), cfg.channel, targets=cfg.targets)
        return _default


def notify(event: dict) -> None:
    """``GOVERNOR_BUILD_NOTIFIERS`` entry point. Never raises; without ``SLACK_BOT_TOKEN`` it does nothing."""
    try:
        notifier = _default or _from_env()
        if notifier is not None and isinstance(event, dict):
            notifier.handle(event)
    except Exception as exc:  # noqa: BLE001
        kind = event.get("kind") if isinstance(event, dict) else None
        log.warning("slack notifier failed on %s: %s", kind, type(exc).__name__)


__all__ = ["MESSAGES_FILE", "MessageStore", "Notifier", "configure", "is_open", "known_threads", "notify",
           "read_run_results", "thread_values"]
