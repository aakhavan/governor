"""Build notifier for Slack (batch2c section 17), registered as
``GOVERNOR_BUILD_NOTIFIERS=governor.integrations.slack.notifier:notify``.

One message per build thread in ``GOVERNOR_SLACK_CHANNEL``, updated in place with the stage checklist, repairs and
cost; details go in the Slack thread under it:

- ``design_gate``: the design card (silver models, KPIs to build and to decline with gap reasons, validation
  findings, Approve / Reject buttons) and ``governor/design.md`` attached as a file;
- ``escalated``: the failing model and its error, without data values;
- ``published``: the branch (the app adds the pull-request link when it ran the publish).

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

    def put(self, thread_id: str, rec: dict) -> None:
        with self._lock:
            data = self._load()
            data[thread_id] = rec
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
            tmp.replace(self.path)


# --------------------------------------------------------------------------- notifier


def _apply(rec: dict, event: dict) -> dict:
    """Fold one build event into the progress record (pure)."""
    rec = dict(rec)
    done = list(rec.get("done") or [])
    kind = event.get("kind")
    if kind == "run_started":
        rec["project"] = event.get("project")
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
    rec["status"] = event.get("status") or {
        "run_started": "started", "profiled": "profiled", "proposed": "design proposed", "validated": "validated",
        "approved": "approved, building silver", "silver_built": "silver built, building gold",
        "gold_built": "gold built", "repair": "repairing SQL", "published": "published",
        "certified": "certified"}.get(kind, rec.get("status"))
    return rec


class Notifier:
    def __init__(self, client: Any, channel: str, store: MessageStore | None = None,
                 values: Callable[[str], dict | None] = thread_values):
        self.client = client
        self.channel = channel
        self.store = store or MessageStore()
        self.values = values

    # ---- posting

    def _thread(self, thread_id: str) -> tuple[str, str | None]:
        rec = self.store.get(thread_id) or {}
        return rec.get("channel") or self.channel, rec.get("ts")

    def reply(self, thread_id: str, text: str, block_list: list[dict] | None = None) -> None:
        """A detail line under the thread's message (or in the channel when there is none yet)."""
        channel, ts = self._thread(thread_id)
        kwargs: dict[str, Any] = {"channel": channel, "text": text}
        if block_list:
            kwargs["blocks"] = block_list
        if ts:
            kwargs["thread_ts"] = ts
        self.client.chat_postMessage(**kwargs)

    def handle(self, event: dict) -> None:
        thread_id = event.get("thread_id")
        if not thread_id:
            return
        rec = _apply(self.store.get(thread_id) or {"done": []}, event)
        text, block_list = blocks.progress(thread_id, rec)
        if rec.get("ts"):
            self.client.chat_update(channel=rec["channel"], ts=rec["ts"], text=text, blocks=block_list)
        else:
            resp = self.client.chat_postMessage(channel=self.channel, text=text, blocks=block_list)
            rec["ts"], rec["channel"] = resp["ts"], resp.get("channel") or self.channel
        self.store.put(thread_id, rec)
        extra = getattr(self, f"_on_{event.get('kind')}", None)
        if extra is not None:
            extra(thread_id, event, rec)

    # ---- details in the thread

    def _on_design_gate(self, thread_id: str, event: dict, rec: dict) -> None:
        values = self.values(thread_id) or {}
        text, block_list = blocks.design_card(thread_id, values.get("proposal"), values.get("findings"),
                                              str(event.get("status") or values.get("status")))
        self.client.chat_postMessage(channel=rec["channel"], thread_ts=rec["ts"], text=text, blocks=block_list)
        report = Path(values["target"]) / "governor" / "design.md" if values.get("target") else None
        if report is not None and report.is_file():
            self.client.files_upload_v2(channel=rec["channel"], thread_ts=rec["ts"], file=str(report),
                                        filename="design.md", title=f"design.md (build {blocks.short(thread_id)})")

    def _on_rejected(self, thread_id: str, event: dict, rec: dict) -> None:
        final = event.get("status") == graph.REJECTED
        self.reply(thread_id, "Design rejected for the second time: the thread ends." if final
                   else "Design rejected: the plan model proposes again with the note.")

    def _on_repair(self, thread_id: str, event: dict, rec: dict) -> None:
        models = ", ".join(f"`{m}`" for m in event.get("models") or []) or "(none)"
        self.reply(thread_id, f"SQL repair {int(event.get('repairs') or 0)}: {models}")

    def _on_escalated(self, thread_id: str, event: dict, rec: dict) -> None:
        values = self.values(thread_id) or {}
        stage = event.get("stage")
        stage_state = (values.get(stage) or {}) if stage in ("silver", "gold") else {}
        esc = stage_state.get("escalated") or {}
        model = event.get("model") or esc.get("model")
        error = esc.get("error")
        if not error and model:
            # the escalation is emitted inside the node, before its return is checkpointed:
            # the previous checkpoint still holds the failing model's error
            error = ((stage_state.get("failures") or {}).get(model) or "")[-3000:] or None
        if event.get("status") == graph.BLUEPRINT_FAILED:
            error = f"{int(event.get('blueprint_findings') or 0)} blueprint findings (high severity); see governor/build.json"
        text, block_list = blocks.escalation(thread_id, stage, model, error)
        self.reply(thread_id, text, block_list)

    def _on_built(self, thread_id: str, event: dict, rec: dict) -> None:
        gaps = ", ".join(f"`{g}`" for g in event.get("gaps") or []) or "none"
        self.reply(thread_id, f"Built: {int(event.get('kpis_built') or 0)} KPIs, {int(event.get('tests_passed') or 0)} "
                              f"tests passed, gaps: {gaps}. Publish with `/governor publish {blocks.short(thread_id)}`.")

    def _on_published(self, thread_id: str, event: dict, rec: dict) -> None:
        text, block_list = blocks.published(thread_id, event.get("branch"), pr_opened=bool(event.get("pr")))
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

            _default = Notifier(WebClient(token=cfg.bot_token), cfg.channel)
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


__all__ = ["MESSAGES_FILE", "MessageStore", "Notifier", "configure", "known_threads", "notify", "thread_values"]
