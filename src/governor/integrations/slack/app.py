"""The Slack app (batch2c section 17): Socket Mode, ``/governor``, Approve / Reject buttons and the reject modal.

A thin client: every action calls the same ``governor.build`` function as the CLI (``graph.start``,
``graph.approve``, ``graph.reject``, ``publish.publish``). The slash command is parsed strictly (known target names,
a build thread that exists); anything else gets the usage message. Slack needs an acknowledgement within 3 seconds,
so the command is acknowledged first and the build work runs in a background thread; progress then arrives through
the build events and the notifier.

Only users in ``GOVERNOR_SLACK_RUNNERS`` (default: the approvers) may ``run``. A run supersedes the project's open
records; at start the app marks open records interrupted (a design waiting at the gate stays open).
Only users in ``GOVERNOR_SLACK_APPROVERS`` may approve, reject or publish; others get an ephemeral refusal. The
approver's mapped name (``GOVERNOR_SLACK_NAMES``) is passed as ``by``, so it lands in ``approved.yaml`` as
``approved_by``. ``certify`` stays a terminal command (it needs the admin login).

Buttons (batch2c section 21): Approve, Reject and **Open pull request** (approvers only). A stale press (the design
already decided or no longer at the gate, an older card, a build already published) is answered ephemerally and
changes nothing. A reject from Slack replaces the card's buttons with the name and the note before the plan model
proposes again.

``ask <question>`` (batch2d section 22) is a thin client of ``governor.ask.certified.answer`` with the role fixed by
``GOVERNOR_SLACK_ASK_ROLE``: answers go to the channel, refusals and errors are ephemeral to the asker.

Tenants (batch3.md section 32): with ``GOVERNOR_TENANTS`` set, the targets are the tenant names and every run,
approve, reject and publish (command or button) goes to one tenant: ``graph.start/approve/reject`` get
``tenant=<Tenant>``. A thread's tenant comes from each tenant's checkpoints; a short id that matches threads in two
tenants is a usage error naming both. ``ask`` stays single-tenant and is refused. Without a registry nothing changes.
"""

from __future__ import annotations

import json
import logging
import threading
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from governor.build import events, graph
from governor.build import publish as build_publish
from governor.integrations.slack import blocks
from governor.integrations.slack.config import SlackConfig, ensure_notifier_registered, tenant_list, workspace
from governor.integrations.slack.notifier import Notifier, TenantThreads, known_threads, thread_values

log = logging.getLogger(__name__)

APPROVER_ACTIONS = ("approve", "reject", "publish")
MAX_NOTE = 1000
MIN_PREFIX = 8
MIN_QUESTION, MAX_QUESTION = 3, 300
CHANNEL_OUTCOMES = ("answer", "not_available", "unanswerable")
REFUSAL = "Only approvers listed in GOVERNOR_SLACK_APPROVERS can {action} a build."
RUN_REFUSAL = "Only users listed in GOVERNOR_SLACK_RUNNERS (default: the approvers) can start a build."


class UsageError(ValueError):
    """The command does not parse; the message says why (shown above the usage text)."""


@dataclass(frozen=True)
class Command:
    action: str  # run | status | approve | reject | publish | ask
    target: str | None = None
    thread_id: str | None = None
    note: str | None = None
    question: str | None = None
    force: bool = False  # ``run <target> force``: skip the up-to-date check (batch3.md section 29)
    tenant: str | None = None  # multi-tenant mode (batch3.md section 32): the tenant the command goes to


def resolve_tenant_thread(token: str, tenant_threads: Mapping[str, Iterable[str]]) -> tuple[str | None, str | None]:
    """``(tenant, thread id)`` for a full id or a short id (batch3 section 32.2), ``(None, None)`` when no tenant
    holds it. A token that matches threads of two or more tenants raises :class:`UsageError` naming them."""
    by_tenant = {name: list(ts) for name, ts in tenant_threads.items()}
    exact = sorted(name for name, ts in by_tenant.items() if token in ts)
    if len(exact) == 1:
        return exact[0], token
    hits = exact or (sorted(name for name, ts in by_tenant.items() if any(t.startswith(token) for t in ts))
                     if len(token) >= MIN_PREFIX else [])
    if len(hits) > 1:
        raise UsageError(f"Build thread `{blocks.safe_text(token, 40)}` matches threads of tenants "
                         f"{' and '.join(f'`{n}`' for n in hits)}; give the full thread id.")
    if not hits:
        return None, None
    thread_id = resolve_thread(token, by_tenant[hits[0]])
    return (hits[0], thread_id) if thread_id else (None, None)


def dbt_project_name(tenant: str) -> str:
    """dbt project names allow letters, digits and ``_`` and start with a letter or ``_``: ``-`` becomes ``_``."""
    name = tenant.replace("-", "_")
    return name if not name[:1].isdigit() else f"t_{name}"


def resolve_thread(token: str, threads: Iterable[str]) -> str | None:
    """A full thread id, or a unique prefix of at least 8 characters (the short id the messages show)."""
    threads = list(threads)
    if token in threads:
        return token
    if len(token) < MIN_PREFIX:
        return None
    hits = [t for t in threads if t.startswith(token)]
    return hits[0] if len(hits) == 1 else None


def parse_command(text: str, targets: Iterable[str], threads: Iterable[str], *,
                  tenant_threads: Mapping[str, Iterable[str]] | None = None) -> Command:
    """Strict parsing of the ``/governor`` text. Raises :class:`UsageError` for anything else.

    ``tenant_threads`` (multi-tenant mode: tenant name -> its build threads) puts the tenant on the command: the
    target for ``run``, the thread's tenant for ``approve``, ``reject`` and ``publish``; ``threads`` is unused then."""
    targets = set(targets)
    head = (text or "").strip().split(maxsplit=1)
    if head and head[0] == "ask":
        question = head[1].strip() if len(head) > 1 else ""
        if not MIN_QUESTION <= len(question) <= MAX_QUESTION:
            raise UsageError(f"`ask` needs a question of {MIN_QUESTION} to {MAX_QUESTION} characters.")
        return Command("ask", question=question)
    parts = (text or "").strip().split(maxsplit=2)
    if not parts:
        raise UsageError("No command given.")
    verb, args = parts[0], parts[1:]
    if verb == "status":
        if args:
            raise UsageError("`status` takes no arguments.")
        return Command("status")
    if verb == "run":
        if not args or args[0] not in targets or (len(args) == 2 and args[1] != "force"):
            raise UsageError("`run` needs exactly one known target name, optionally followed by `force`.")
        if tenant_threads is not None:
            return Command("run", target=args[0], force=len(args) == 2, tenant=args[0])
        return Command("run", target=args[0], force=len(args) == 2)
    if verb in ("approve", "publish", "reject"):
        if not args:
            raise UsageError(f"`{verb}` needs a build thread id.")
        tenant = None
        if tenant_threads is not None:
            tenant, thread_id = resolve_tenant_thread(args[0], tenant_threads)
        else:
            thread_id = resolve_thread(args[0], threads)
        if thread_id is None:
            raise UsageError(f"Unknown build thread `{blocks.safe_text(args[0], 40)}`.")
        if verb == "reject":
            note = args[1].strip() if len(args) > 1 else ""
            if not note:
                raise UsageError("`reject` needs a note: `/governor reject <thread> <what to change>`.")
            if len(note) > MAX_NOTE:
                raise UsageError(f"The note is longer than {MAX_NOTE} characters.")
            return Command("reject", thread_id=thread_id, note=note, tenant=tenant)
        if len(args) != 1:
            raise UsageError(f"`{verb}` takes only a build thread id.")
        return Command(verb, thread_id=thread_id, tenant=tenant)
    raise UsageError(f"Unknown command `{blocks.safe_text(verb, 40)}`.")


def recent_threads(limit: int = 10) -> list[dict]:
    """The last event per build thread from the event log, newest first."""
    path = events.events_path()
    last: dict[str, dict] = {}
    projects: dict[str, str] = {}
    if path.is_file():
        with path.open(encoding="utf-8") as fh:
            for raw in fh:
                try:
                    ev = json.loads(raw)
                except ValueError:
                    continue
                tid = ev.get("thread_id")
                if not tid:
                    continue
                if ev.get("kind") == "run_started" and ev.get("project"):
                    projects[tid] = ev["project"]
                last.pop(tid, None)
                last[tid] = ev
    out = [{"thread_id": t, "project": projects.get(t), "kind": e.get("kind"), "status": e.get("status"),
            "ts": e.get("ts")} for t, e in last.items()]
    return list(reversed(out))[:limit]


def _background(fn: Callable[[], None]) -> None:
    threading.Thread(target=fn, daemon=True, name="governor-slack-work").start()


def _error_line(exc: Exception) -> str:
    if isinstance(exc, (graph.BuildError, build_publish.PublishError)):
        return blocks.safe_text(exc, 300)
    return f"{type(exc).__name__}: {blocks.safe_text(str(exc).splitlines()[0] if str(exc) else '', 200)}"


class GovernorSlack:
    """The app's behaviour without Bolt: tests drive it with a fake client and an inline runner."""

    def __init__(self, config: SlackConfig, client: Any, *, notifier: Notifier | None = None,
                 runner: Callable[[Callable[[], None]], None] = _background,
                 llm_factory: Callable[[str], Any] | None = None,
                 threads: Callable[[], Iterable[str]] = known_threads,
                 values: Callable[[str], dict | None] = thread_values,
                 build: Any = graph, publisher: Callable[..., dict] = build_publish.publish,
                 asker: Callable[[str, str], Any] | None = None,
                 tenant_threads: Callable[[], Mapping[str, Iterable[str]]] | None = None):
        self.config = config
        self.client = client
        # batch3 section 32: with tenants, threads and their state come from each tenant's own checkpoints
        self.tenants = dict(config.tenants)
        self.registry = TenantThreads(self.tenants, tenant_threads) if self.tenants else None
        if self.registry is not None:
            if values is thread_values:
                values = self.registry.values
            if threads is known_threads:
                threads = lambda: [t for ts in self.registry.by_tenant().values() for t in ts]  # noqa: E731
        self.notifier = notifier or Notifier(client, config.channel, values=values, targets=config.targets,
                                             tenant_of=self.registry.tenant_of if self.registry else None)
        self.runner = runner
        self.llm_factory = llm_factory
        self.threads = threads
        self.values = values
        self.build = build
        self.publisher = publisher
        self.asker = asker or self._default_asker
        self._busy: set[str] = set()
        self._lock = threading.Lock()

    def _llm(self) -> Any:
        if self.llm_factory is not None:
            return self.llm_factory(self.config.llm)
        from governor.build.llm import make_llm

        return make_llm(self.config.llm)

    def _default_asker(self, question: str, role: str) -> Any:
        """``certified.answer`` with the ask model; imported here so the Slack modules import without a database."""
        from governor.ask import certified

        return certified.answer(question, role, certified.make_llm(self.config.ask_llm))

    # ---- entry points (each answers at once; long work goes to the runner)

    def _usage(self, error: str | None) -> str:
        if self.tenants:  # batch3 section 32.3: the footer lists each tenant and its database
            return blocks.usage(self.config.targets, error, tenants=tenant_list(self.tenants))
        knowledge, database = workspace()
        return blocks.usage(self.config.targets, error, (knowledge.name, database))

    def _of(self, tenant: str | None) -> str:
        """`` (tenant <name>)`` for replies in multi-tenant mode; empty otherwise."""
        return f" (tenant {tenant})" if tenant else ""

    def _tenant_kw(self, cmd: Command) -> dict:
        """``tenant=<Tenant>`` for the build calls in multi-tenant mode; nothing otherwise (the call is unchanged)."""
        return {"tenant": self.tenants[cmd.tenant]} if cmd.tenant else {}

    def _button_tenant(self, thread_id: str) -> str | None:
        """The tenant of a button's thread (multi-tenant mode). Raises :class:`UsageError` when no tenant or more
        than one tenant holds the thread."""
        if self.registry is None:
            return None
        names = self.registry.tenants_of(thread_id)
        if len(names) > 1:
            raise UsageError(f"Build thread `{blocks.short(thread_id)}` is in tenants "
                             f"{' and '.join(f'`{n}`' for n in names)}. Nothing changed.")
        if not names:
            raise UsageError(f"Build thread `{blocks.short(thread_id)}` is in no tenant. Nothing changed.")
        return names[0]

    def handle_command(self, user_id: str, text: str, respond: Callable[..., Any]) -> None:
        if self.tenants and (text or "").strip().split(maxsplit=1)[:1] == ["ask"]:
            # batch3 section 32.4: ask stays single-tenant; nothing runs
            respond(text=blocks.ASK_MULTI_TENANT, response_type="ephemeral")
            return
        try:
            if self.registry is not None:
                cmd = parse_command(text, self.config.targets, (), tenant_threads=self.registry.by_tenant())
            else:
                cmd = parse_command(text, self.config.targets, self.threads())
        except UsageError as exc:
            respond(text=self._usage(str(exc)), response_type="ephemeral")
            return
        if cmd.action == "status":
            respond(text=blocks.status_list(recent_threads()), response_type="ephemeral")
            return
        if cmd.action == "ask":
            if not self.config.is_asker(user_id):
                respond(text=blocks.ASK_REFUSAL, response_type="ephemeral")
                return
            respond(text=blocks.ASK_ACK, response_type="ephemeral")
            question = str(cmd.question)
            self.runner(lambda: self._ask(question, user_id, respond))
            return
        if cmd.action in APPROVER_ACTIONS and not self.config.is_approver(user_id):
            respond(text=REFUSAL.format(action=cmd.action), response_type="ephemeral")
            return
        if cmd.action == "run" and not self.config.is_runner(user_id):
            respond(text=RUN_REFUSAL, response_type="ephemeral")
            return
        if cmd.action == "run":
            thread_id = str(uuid.uuid4())
            what = f"tenant `{cmd.tenant}`" if cmd.tenant else f"`{cmd.target}`"
            respond(text=f"Starting build `{blocks.short(thread_id)}` for {what}; progress in #{self.config.channel}.",
                    response_type="ephemeral")
            self.runner(lambda: self._run(cmd.target, thread_id, force=cmd.force))
            return
        self._start(cmd, user_id, respond)

    # ---- buttons: approvers only; a stale button (the design decided, the build published) changes nothing

    def _card_stale(self, thread_id: str, message_ts: str | None = None) -> bool:
        """The design card's buttons are stale once the design is decided, when the press comes from an older card,
        or when the thread no longer waits at the design gate."""
        rec = self.notifier.store.get(thread_id) or {}
        if rec.get("card_decided"):
            return True
        if message_ts and rec.get("card_ts") and message_ts != rec["card_ts"]:
            return True
        try:
            status = (self.values(thread_id) or {}).get("status")
        except Exception:  # noqa: BLE001
            status = None
        return status != graph.AWAITING

    def _publish_stale(self, thread_id: str) -> bool:
        """The **Open pull request** button is live only while the build is built and not yet published."""
        return (self.notifier.store.get(thread_id) or {}).get("outcome") != blocks.BUILT

    @staticmethod
    def _stale(thread_id: str, respond: Callable[..., Any], what: str) -> None:
        respond(text=f"This button is out of date: build `{blocks.short(thread_id)}` {what}. Nothing changed.",
                response_type="ephemeral", replace_original=False)

    def handle_approve_button(self, user_id: str, thread_id: str, respond: Callable[..., Any],
                              message_ts: str | None = None) -> None:
        if not self.config.is_approver(user_id):
            respond(text=REFUSAL.format(action="approve"), response_type="ephemeral", replace_original=False)
            return
        try:
            tenant = self._button_tenant(thread_id)
        except UsageError as exc:
            respond(text=str(exc), response_type="ephemeral", replace_original=False)
            return
        if self._card_stale(thread_id, message_ts):
            self._stale(thread_id, respond, "is not waiting for this design decision")
            return
        self._start(Command("approve", thread_id=thread_id, tenant=tenant), user_id, respond)

    def handle_reject_button(self, user_id: str, thread_id: str, trigger_id: str, respond: Callable[..., Any],
                             message_ts: str | None = None) -> None:
        if not self.config.is_approver(user_id):
            respond(text=REFUSAL.format(action="reject"), response_type="ephemeral", replace_original=False)
            return
        try:
            self._button_tenant(thread_id)
        except UsageError as exc:
            respond(text=str(exc), response_type="ephemeral", replace_original=False)
            return
        if self._card_stale(thread_id, message_ts):
            self._stale(thread_id, respond, "is not waiting for this design decision")
            return
        self.client.views_open(trigger_id=trigger_id, view=blocks.reject_modal(thread_id))

    def handle_publish_button(self, user_id: str, thread_id: str, respond: Callable[..., Any]) -> None:
        if not self.config.is_approver(user_id):
            respond(text=REFUSAL.format(action="publish"), response_type="ephemeral", replace_original=False)
            return
        try:
            tenant = self._button_tenant(thread_id)
        except UsageError as exc:
            respond(text=str(exc), response_type="ephemeral", replace_original=False)
            return
        if self._publish_stale(thread_id):
            self._stale(thread_id, respond, "is not waiting to be published")
            return
        self._start(Command("publish", thread_id=thread_id, tenant=tenant), user_id, respond)

    def handle_reject_submit(self, user_id: str, thread_id: str, note: str) -> dict | None:
        """Returns a Bolt ``ack`` payload with input errors, or None when the rejection was started."""
        if not self.config.is_approver(user_id):
            return {"response_action": "errors", "errors": {blocks.NOTE_BLOCK: REFUSAL.format(action="reject")}}
        try:
            tenant = self._button_tenant(thread_id)
        except UsageError as exc:
            return {"response_action": "errors", "errors": {blocks.NOTE_BLOCK: str(exc)}}
        if self._card_stale(thread_id):
            return {"response_action": "errors",
                    "errors": {blocks.NOTE_BLOCK: "This design was already decided. Nothing changed."}}
        note = (note or "").strip()
        if not note:
            return {"response_action": "errors", "errors": {blocks.NOTE_BLOCK: "Write what should change."}}
        if len(note) > MAX_NOTE:
            return {"response_action": "errors", "errors": {blocks.NOTE_BLOCK: f"At most {MAX_NOTE} characters."}}
        self._start(Command("reject", thread_id=thread_id, note=note, tenant=tenant), user_id, None)
        return None

    # ---- work

    def _start(self, cmd: Command, user_id: str, respond: Callable[..., Any] | None) -> None:
        tid = str(cmd.thread_id)
        with self._lock:
            if tid in self._busy:
                if respond:
                    respond(text=f"Build `{blocks.short(tid)}` is already being worked on.", response_type="ephemeral",
                            replace_original=False)
                return
            self._busy.add(tid)
        if respond:
            respond(text=f"{cmd.action.capitalize()} build `{blocks.short(tid)}`{self._of(cmd.tenant)}: working on it.",
                    response_type="ephemeral", replace_original=False)

        def work() -> None:
            try:
                getattr(self, f"_{cmd.action}")(cmd, user_id)
            except Exception as exc:  # noqa: BLE001
                log.warning("slack %s failed: %s", cmd.action, type(exc).__name__)
                self._say(tid, f":warning: {cmd.action} failed: {_error_line(exc)}")
            finally:
                with self._lock:
                    self._busy.discard(tid)

        self.runner(work)

    def _say(self, thread_id: str, text: str, block_list: list[dict] | None = None) -> None:
        try:
            self.notifier.reply(thread_id, text, block_list)
        except Exception as exc:  # noqa: BLE001
            log.warning("slack reply failed: %s", type(exc).__name__)

    def _run(self, target: str, thread_id: str, force: bool = False) -> None:
        # Open records of the same project (not ended, not at the gate) will never finish now.
        try:
            self.notifier.supersede(target, thread_id)
        except Exception as exc:  # noqa: BLE001
            log.warning("slack: superseding older runs failed: %s", type(exc).__name__)
        try:
            # Same as the CLI run: make sure the target is a dbt project (dbt_project.yml, profiles) before the build.
            from governor.build.publish import ensure_on_main
            from governor.build.workspace import init_target

            tenant = self.tenants.get(target)  # batch3 section 32.1: the run goes to its tenant
            path = tenant.target if tenant else self.config.targets[target]
            ensure_on_main(path)  # publish branches from main (same as the CLI run)
            init_target(path, dbt_project_name(target) if tenant else target)
            # The outcome is the progress message (and the design card or escalation reply): no extra reply here.
            extra: dict[str, Any] = {"force": True} if force else {}  # without force, the call is exactly as before
            if tenant is not None:
                extra["tenant"] = tenant
            self.build.start(path, target, self._llm(), thread_id=thread_id, **extra)
        except Exception as exc:  # noqa: BLE001
            self._say(thread_id, f":warning: run failed: {_error_line(exc)}")

    def _ask(self, question: str, user_id: str, respond: Callable[..., Any]) -> None:
        """The certified path (batch2d section 22). The role is the configured one; the question never reaches a log."""
        role = self.config.ask_role
        try:
            out = self.asker(question, role)
        except Exception as exc:  # noqa: BLE001  (CertifiedError or anything else: same scrubbed ephemeral line)
            log.info("slack ask: outcome=error (%s) user=%s", type(exc).__name__, user_id)
            respond(text=blocks.ask_error(exc), response_type="ephemeral")
            return
        outcome, kpi_id = getattr(out, "outcome", None), getattr(out, "kpi_id", None)
        log.info("slack ask: outcome=%s kpi=%s user=%s", outcome, kpi_id, user_id)
        if outcome in CHANNEL_OUTCOMES:
            text, block_list = blocks.ask_answer(question, str(out.text), role, kpi_id)
            try:
                self.client.chat_postMessage(channel=self.config.channel, text=text, blocks=block_list)
            except Exception as exc:  # noqa: BLE001
                log.warning("slack ask: posting the answer failed: %s", type(exc).__name__)
                respond(text=blocks.ask_error("the answer could not be posted to the channel"),
                        response_type="ephemeral")
            return
        if outcome == "refused":
            respond(text=str(out.text), response_type="ephemeral")
            return
        respond(text=blocks.ask_error(f"unexpected outcome {blocks.safe_text(outcome, 40)}"), response_type="ephemeral")

    def mark_interrupted(self) -> list[str]:
        """At app start: open records (not ended, not waiting at the gate) were cut off by the restart."""
        try:
            return self.notifier.interrupt_open()
        except Exception as exc:  # noqa: BLE001
            log.warning("slack: marking interrupted runs failed: %s", type(exc).__name__)
            return []

    def _approve(self, cmd: Command, user_id: str) -> None:
        out = self.build.approve(cmd.thread_id, self.config.name_for(user_id), self._llm(), **self._tenant_kw(cmd))
        self._say(str(cmd.thread_id), f"Approved by {self.config.name_for(user_id)}; the build ended at "
                                      f"`{out.get('status')}`.")

    def _reject(self, cmd: Command, user_id: str) -> None:
        # the card is decided before the call: a successful reject posts a new card for the next proposal
        try:
            self.notifier.decide_card(str(cmd.thread_id), blocks.decided_line("reject", self.config.name_for(user_id),
                                                                              note=cmd.note))
        except Exception as exc:  # noqa: BLE001
            log.warning("slack: cannot replace the design card buttons: %s", type(exc).__name__)
        out = self.build.reject(cmd.thread_id, cmd.note, self._llm(), **self._tenant_kw(cmd))
        self._say(str(cmd.thread_id), f"Rejected by {self.config.name_for(user_id)}; the thread is at "
                                      f"`{out.get('status')}`.")

    def _publish(self, cmd: Command, user_id: str) -> None:
        tid = str(cmd.thread_id)
        if cmd.tenant:  # batch3 section 32.2: a tenant's build publishes its own target, nothing else
            target = Path(self.tenants[cmd.tenant].target)
        else:
            values = self.values(tid) or {}
            if not values.get("target"):
                self._say(tid, f"Build `{blocks.short(tid)}` has no target folder in its state.")
                return
            target = Path(values["target"])
        out = self.publisher(target, open_pr=_has_origin(target))
        if out.get("status") == "nothing_to_publish":  # batch3 section 30.3: a plain message, not an error
            self._say(tid, f"Nothing to publish: {blocks.safe_text(out.get('reason'), 300)}.")
        elif out.get("status") != "published":
            self._say(tid, f"Not published: {blocks.safe_text(out.get('reason'), 300)}")
        # published: the event carries pr_url and the notifier posts the link


def _has_origin(target: Path) -> bool:
    """Open a pull request only when the target is its own git repo with an ``origin`` remote."""
    if not (target / ".git").exists():
        return False
    try:
        return build_publish.git(target, "remote", "get-url", "origin", check=False).returncode == 0
    except Exception:  # noqa: BLE001
        return False


# --------------------------------------------------------------------------- Bolt wiring


def create_app(config: SlackConfig, gov: GovernorSlack | None = None):
    """The Bolt app with the command, the two buttons and the reject modal registered."""
    from slack_bolt import App

    from governor.integrations.slack import notifier as notifier_module

    app = App(token=config.bot_token)
    gov = gov or GovernorSlack(config, app.client)
    notifier_module.configure(gov.notifier)
    ensure_notifier_registered()
    gov.mark_interrupted()

    @app.command("/governor")
    def _command(ack, body, respond):  # noqa: ANN001
        ack()
        gov.handle_command(body.get("user_id", ""), body.get("text", ""), respond)

    def _message_ts(body: dict) -> str | None:
        return (body.get("container") or {}).get("message_ts") or (body.get("message") or {}).get("ts")

    @app.action(blocks.APPROVE_ACTION)
    def _approve(ack, body, respond):  # noqa: ANN001
        ack()
        gov.handle_approve_button(body["user"]["id"], body["actions"][0]["value"], respond, _message_ts(body))

    @app.action(blocks.REJECT_ACTION)
    def _reject(ack, body, respond):  # noqa: ANN001
        ack()
        gov.handle_reject_button(body["user"]["id"], body["actions"][0]["value"], body["trigger_id"], respond,
                                 _message_ts(body))

    @app.action(blocks.PUBLISH_ACTION)
    def _publish(ack, body, respond):  # noqa: ANN001
        ack()
        gov.handle_publish_button(body["user"]["id"], body["actions"][0]["value"], respond)

    @app.view(blocks.REJECT_MODAL)
    def _reject_note(ack, body, view):  # noqa: ANN001
        note = (((view.get("state") or {}).get("values") or {}).get(blocks.NOTE_BLOCK) or {}).get(blocks.NOTE_ACTION) or {}
        errors = gov.handle_reject_submit(body["user"]["id"], view.get("private_metadata", ""), note.get("value") or "")
        ack(**errors) if errors else ack()

    return app


__all__ = ["Command", "GovernorSlack", "UsageError", "create_app", "dbt_project_name", "parse_command", "recent_threads",
           "resolve_tenant_thread", "resolve_thread"]
