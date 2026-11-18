"""Block Kit rendering for the Slack app (batch2c section 17). Pure functions: no network, no tokens.

Every function returns ``(text, blocks)`` (``text`` is the notification fallback) or a view dict. Inputs are build
state the notifier already holds: names, counts, codes, statuses and cost. Nothing here reads a profile, and free
text that could quote data (model replies, validation problems, dbt errors) goes through :func:`safe_text`, which
drops quoted literals and ``DETAIL`` lines.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import Any, Iterable

APPROVE_ACTION = "governor_approve"
REJECT_ACTION = "governor_reject"
PUBLISH_ACTION = "governor_publish"
REJECT_MODAL = "governor_reject_modal"
NOTE_BLOCK = NOTE_ACTION = "note"

# stage key (an event kind) -> checklist label, in build order
STAGES: tuple[tuple[str, str], ...] = (
    ("profiled", "profiled"),
    ("proposed", "design proposed"),
    ("validated", "validated"),
    ("design_gate", "waiting for approval"),
    ("approved", "approved"),
    ("silver_built", "silver built"),
    ("gold_built", "gold built"),
    ("published", "published"),
)

USAGE = ("Usage:\n"
         "• `/governor run <target> [force]`: start a build (targets: {targets}); `force` designs again even "
         "when nothing changed\n"
         "• `/governor status`: recent build threads\n"
         "• `/governor approve <thread>`: approve the design at the gate\n"
         "• `/governor reject <thread> <note>`: send the design back with a note\n"
         "• `/governor publish <thread>`: commit the built project to a branch and open the pull request\n"
         "• `/governor ask <question>`: a certified answer from the published KPIs (3 to 300 characters)\n"
         "`<thread>` is the full build thread id or its first 8 characters.")

_MAX_ITEMS = 25
_MAX_TEXT = 2800  # Block Kit section text limit is 3000
_QUOTED = re.compile(r"'(?:[^'\\]|\\.|'')*'")
_DQUOTED = re.compile(r'"(?:[^"\\]|\\.|"")*"')  # Postgres quotes values as "..." (identifiers too; both go)
_DETAIL = re.compile(r"^\s*(DETAIL|HINT|Failing row|Key \().*$", re.IGNORECASE | re.MULTILINE)
_LONG_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,.]{3,}\d(?![\w.])")
# failure counts are not data values: "(131707 failures)" and "Got 131707 results" keep their digits
_COUNT = re.compile(r"(?<=\()\d+(?= failures?\))|(?<=Got )\d+(?= results?)", re.IGNORECASE)


def short(thread_id: str | None) -> str:
    return str(thread_id or "")[:8]


def _long_numbers(s: str) -> str:
    """Long numbers become ``#``; failure counts survive (also when the text is scrubbed a second time)."""
    out, pos = [], 0
    for m in _COUNT.finditer(s):
        out += [_LONG_NUMBER.sub("#", s[pos:m.start()]), m.group(0)]
        pos = m.end()
    return "".join(out) + _LONG_NUMBER.sub("#", s[pos:])


def safe_text(text: Any, limit: int = 200) -> str:
    """One line without data values: quoted literals become '…', DETAIL/HINT/Key lines and long numbers go
    (failure counts stay)."""
    s = _DETAIL.sub("", str(text or ""))
    s = _QUOTED.sub("'…'", s)
    s = _DQUOTED.sub('"…"', s)
    s = _long_numbers(s)
    s = " ".join(s.split())
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _section(text: str) -> dict:
    return {"type": "section", "text": {"type": "mrkdwn", "text": text[:_MAX_TEXT]}}


def _context(text: str) -> dict:
    return {"type": "context", "elements": [{"type": "mrkdwn", "text": text[:_MAX_TEXT]}]}


def _bullets(items: Iterable[str], empty: str = "(none)") -> str:
    items = list(items)
    more = len(items) - _MAX_ITEMS
    lines = [f"• {i}" for i in items[:_MAX_ITEMS]] + ([f"… and {more} more"] if more > 0 else [])
    return "\n".join(lines) or empty


def _cost(value: Any) -> str:
    return f"${value:.4f}" if isinstance(value, (int, float)) else "unknown"


# --------------------------------------------------------------------------- progress message


FAILED, BUILT, PUBLISHED, SUPERSEDED, INTERRUPTED = "failed", "built", "published", "superseded", "interrupted"
UP_TO_DATE = "up_to_date"  # batch3.md section 29: nothing changed since the last approved build
TERMINAL = (FAILED, BUILT, PUBLISHED, SUPERSEDED, INTERRUPTED, UP_TO_DATE)
_LABELS = dict(STAGES)


def _checklist(rec: dict) -> list[str]:
    """``:x:`` on the failed stage, ``:heavy_minus_sign:`` on the stages an ended run will never reach."""
    done = set(rec.get("done") or [])
    outcome = rec.get("outcome")
    failed = rec.get("failed_stage") if outcome == FAILED else None
    ended = outcome in (FAILED, SUPERSEDED, INTERRUPTED, UP_TO_DATE)
    lines = []
    seen_failed = False
    for key, label in STAGES:
        if key == failed:
            mark, seen_failed = ":x:", True
        elif key in done:
            mark = ":white_check_mark:"
        elif seen_failed or ended:
            mark = ":heavy_minus_sign:"
        else:
            mark = ":white_large_square:"
        lines.append(f"{mark} {label}")
    return lines


def _headline(thread_id: str, rec: dict) -> tuple[str, str]:
    """(mrkdwn header, plain fallback). Ended runs read as ended."""
    if rec.get("tenant"):  # batch3 section 32.3: multi-tenant mode names the tenant
        who = f"governor build `{short(thread_id)}` (tenant {safe_text(rec['tenant'], 60)})"
    else:
        who = f"governor build `{short(thread_id)}` ({rec.get('project') or 'build'})"
    outcome = rec.get("outcome")
    if outcome == FAILED:
        where = rec.get("stopped_at") or _LABELS.get(rec.get("failed_stage") or "", "build")
        reason = safe_text(rec.get("reason") or "no error recorded", 200)
        return f":red_circle: stopped at {where}: *{who}*\n{reason}", f"stopped at {where}: {who}: {reason}"
    if outcome == PUBLISHED:
        if rec.get("pr_url"):
            return f":large_green_circle: published: <{rec['pr_url']}> · *{who}*", f"published: {rec['pr_url']}: {who}"
        where = f"branch `{rec['branch']}`" if rec.get("branch") else "no pull request"
        return f":large_green_circle: published: {where} · *{who}*", f"published: {where}: {who}"
    if outcome == BUILT:
        return f":large_green_circle: built: *{who}*", f"built: {who}"
    if outcome == SUPERSEDED:
        what = f"superseded by `{short(rec.get('superseded_by'))}`"
        return f":white_circle: {what}: *{who}*", f"{what}: {who}"
    if outcome == UP_TO_DATE:
        line = f"up to date: no change since build {short(rec.get('last_build'))}"
        return f":white_check_mark: {line}\n*{who}*", f"{line}: {who}"
    if outcome == INTERRUPTED:
        return f":white_circle: interrupted (bot restarted): *{who}*", f"interrupted (bot restarted): {who}"
    status = rec.get("status") or "running"
    return f"*{who}*: {status}", f"{who}: {status}"


def progress(thread_id: str, rec: dict, certify: str | None = None) -> tuple[str, list[dict]]:
    """The one message per build thread: a header (the terminal state once the run ended), a stage checklist,
    the next step once the run is built or published (batch2c section 21), repairs and cost."""
    head, text = _headline(thread_id, rec)
    facts = (f"design repairs: {int(rec.get('design_repairs') or 0)} · SQL repairs: {int(rec.get('sql_repairs') or 0)}"
             f" · model cost: {_cost(rec.get('cost_usd'))} · thread `{thread_id}`")
    out = [_section(head), _section("\n".join(_checklist(rec)))]
    outcome = rec.get("outcome")
    if outcome == BUILT:
        out += [_section("*Next:* press *Open pull request* below"), publish_actions(thread_id)]
    elif outcome == PUBLISHED:
        out.append(_section(f"*Next:* {after_publish(rec.get('pr_url'), rec.get('branch'), certify)}"))
    return text.replace("`", ""), out + [_context(facts)]


# --------------------------------------------------------------------------- next steps (batch2c section 21)


def certify_command(target: Any = None, name: Any = None) -> str:
    """The terminal certify line: the target path from ``GOVERNOR_SLACK_TARGETS`` and the approver's mapped name."""
    path = str(target) if target else "<target>"
    if " " in path:
        path = f'"{path}"'
    by = str(name).replace('"', "") if name else "<name>"
    return f'python -m governor.build certify --target {path} --by "{by}"'


def copyable(command: str) -> str:
    """A command on its own line as a Slack code block, so it is selected and copied whole (17 Nov: inline code in
    a sentence could not be copied cleanly)."""
    return f"\n```{command}```"


def after_publish(pr_url: str | None, branch: Any, certify: str | None) -> str:
    """The step after a publish: merge the pull request on GitHub, or (no ``origin``) the branch locally; then
    certify in a terminal (it needs the admin login)."""
    cmd = copyable(certify or certify_command())
    if pr_url:
        return f"Review and merge on GitHub, then certify in a terminal:{cmd}"
    where = f"branch `{branch}`" if branch else "the publish branch"
    return f"No pull request (the target has no `origin`): merge {where} into `main` locally, then certify in a terminal:{cmd}"


def publish_actions(thread_id: str) -> dict:
    """The **Open pull request** button (approvers only: the app checks every press)."""
    return {"type": "actions", "block_id": f"publish_{short(thread_id)}", "elements": [
        {"type": "button", "action_id": PUBLISH_ACTION, "style": "primary", "value": thread_id,
         "text": {"type": "plain_text", "text": "Open pull request"}}]}


def built_reply(thread_id: str, summary: str, certify: str | None = None,
                published_link: str | None = None) -> tuple[str, list[dict]]:
    """The thread's "Built" reply: the summary, the three next steps and the **Open pull request** button. Once
    published, the button gives way to the link (``published_link``)."""
    steps = ("*Next*\n① press *Open pull request* below\n"
             "② review and merge it on GitHub (or locally when the target has no `origin`)\n"
             f"③ certify in a terminal:{copyable(certify or certify_command())}")
    out = [_section(summary), _section(steps)]
    out.append(_section(published_link) if published_link else publish_actions(thread_id))
    return summary.replace("`", ""), out


def published_link(pr_url: str | None, branch: Any) -> str:
    """What replaces the **Open pull request** button after the publish."""
    if pr_url:
        return f":rocket: Published: <{pr_url}|pull request> (branch `{branch}`)"
    return f":rocket: Published on branch `{branch}` (no pull request: merge it locally)"


def _when(ts: Any) -> str:
    """An event timestamp as a Slack date (shown in the reader's time zone), UTC as the fallback text."""
    try:
        stamp = dt.datetime.fromisoformat(str(ts))
    except ValueError:
        return safe_text(ts, 40)
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=dt.timezone.utc)
    utc = stamp.astimezone(dt.timezone.utc)
    return f"<!date^{int(stamp.timestamp())}^{{date_short_pretty}} {{time}}|{utc:%Y-%m-%d %H:%M} UTC>"


def decided_line(action: str, name: Any = None, ts: Any = None, note: Any = None) -> str:
    """The line that replaces the design card's buttons once the design is decided."""
    if action == "approve":
        return f":white_check_mark: Approved by {safe_text(name or 'someone', 80)}" + (f" at {_when(ts)}" if ts else "")
    who = f" by {safe_text(name, 80)}" if name else ""
    return f":x: Rejected{who}" + (f": {safe_text(note, 300)}" if note else "")


# --------------------------------------------------------------------------- failure reasons (no data values)

# silver.py: "dbt test <unique_id> <status>: Got N results"; gold.py: "dbt test.<package>.<name>.<hash> <status>: ..."
_TEST_LINE = re.compile(r"dbt (?:test\s+)?(\S+)\s+(?:fail|error|runtime error):\s*Got (\d+) results?", re.IGNORECASE)
_FAILING = ("fail", "error", "runtime error")


def node_name(unique_id: Any) -> str:
    """``test.olist.unique_stg_orders_order_id.ab12`` -> ``unique_stg_orders_order_id``; ``model.p.x`` -> ``x``."""
    parts = str(unique_id or "").split(".")
    return parts[2] if len(parts) >= 3 else str(unique_id or "")


def tests_reason(tests: list[tuple[str, int]]) -> str:
    return "failing tests: " + ", ".join(f"{name} ({n} failure{'' if n == 1 else 's'})" for name, n in tests)


def failing_tests(error: Any) -> list[tuple[str, int]]:
    """(test name, failure count) for every failing dbt test named in an error text."""
    return [(node_name(uid), int(n)) for uid, n in _TEST_LINE.findall(str(error or ""))]


def first_line(text: Any) -> str:
    return next((ln.strip() for ln in str(text or "").splitlines() if ln.strip()), "")


def reason_line(error: Any) -> str:
    """One scrubbed line (at most 200 characters): the failing tests with their counts, else the error's first line."""
    tests = failing_tests(error)
    return safe_text(tests_reason(tests) if tests else first_line(error), 200)


def run_results_failures(results: list[dict]) -> tuple[str | None, str | None]:
    """(first failing node, error text) from ``run_results.json`` results: test names with failure counts, and a
    failing model's first message line (scrubbed). Never rows."""
    tests: list[tuple[str, int]] = []
    others: list[tuple[str, str]] = []
    for r in results or []:
        status = str(r.get("status") or "").lower()
        if status not in _FAILING:
            continue
        uid = str(r.get("unique_id") or "")
        if uid.startswith("test."):
            n = r.get("failures")
            tests.append((node_name(uid), int(n) if isinstance(n, (int, float)) else 0))
        else:
            msg = safe_text(first_line(r.get("message")) or status, 200)
            others.append((node_name(uid), f"dbt {node_name(uid)} {status}: {msg}"))
    if not tests and not others:
        return None, None
    lines = [m for _, m in others] + ([tests_reason(tests)] if tests else [])
    return (others or tests)[0][0], "\n".join(lines)


_CELL_SPLIT = re.compile(r"(?<!\\)\|")
MAPPINGS_OMITTED = "mappings omitted here; they are in the pull request"


def design_without_mappings(text: str) -> str:
    """``design.md`` for Slack: KPI mapping values (they can hold SQL literals) give way to a note, and model free
    text (reasons, gaps, assumptions) loses quoted literals and DETAIL lines, as everywhere else in Slack."""
    out, in_kpis = [], False
    for ln in _DETAIL.sub("", text).splitlines():
        ln = _DQUOTED.sub('"…"', _QUOTED.sub("'…'", ln))
        if ln.startswith("## "):
            in_kpis = ln.strip() == "## KPIs"
        elif in_kpis and ln.startswith("|"):
            cells = _CELL_SPLIT.split(ln)
            if len(cells) >= 6 and cells[2].strip() == "build":
                ln = "|".join(cells[:4] + [f" {MAPPINGS_OMITTED} "] + cells[-1:])
        out.append(ln)
    return "\n".join(out) + ("\n" if text.endswith("\n") else "")


# --------------------------------------------------------------------------- design card


def _gap_reason(k: dict) -> str:
    gap = k.get("gap") or {}
    missing = ", ".join(str(m) for m in (gap.get("missing") or [])[:6])
    reason = safe_text(k.get("reason") or "no reason given", 160)
    return f"`{k.get('id')}`: {reason}" + (f" (missing: {safe_text(missing, 120)})" if missing else "")


def design_card(thread_id: str, proposal: dict | None, findings: list[dict] | None, status: str,
                decided: str | None = None, tenant: str | None = None) -> tuple[str, list[dict]]:
    """Silver models, KPIs to build and to decline with gap reasons, validation findings, and (when the design
    waits at the gate) Approve / Reject buttons. Once decided, the ``decided`` line replaces the buttons.
    Mappings are not shown: they can hold SQL literals. ``tenant`` (multi-tenant mode) is named in the title."""
    of = f" (tenant {safe_text(tenant, 60)})" if tenant else ""
    proposal = proposal or {}
    findings = findings or []
    silver = proposal.get("silver_models") or []
    kpis = proposal.get("kpis") or []
    build = [k for k in kpis if k.get("decision") == "build"]
    decline = [k for k in kpis if k.get("decision") == "decline"]
    waiting = status == "awaiting_design_approval"
    title = (f"*Design for build `{short(thread_id)}`*{of}: {len(silver)} silver models, {len(build)} KPIs to build, "
             f"{len(decline)} to decline, {len(findings)} validation findings")
    blocks: list[dict] = [_section(title)]
    blocks.append(_section("*Silver models*\n" + _bullets(f"`{m.get('name')}` ({m.get('folder') or 'silver'})"
                                                          for m in silver)))
    blocks.append(_section("*KPIs to build*\n" + _bullets(
        f"`{k.get('id')}`" + (f" ({k.get('domain')})" if k.get("domain") else "") for k in build)))
    blocks.append(_section("*KPIs to decline*\n" + _bullets((_gap_reason(k) for k in decline), "No KPI is declined.")))
    blocks.append(_section("*Validation findings*\n" + _bullets(
        (f"`{f.get('code')}` {safe_text(f.get('subject'), 80)}: {safe_text(f.get('problem'), 160)}" for f in findings),
        "No findings.")))
    if decided:
        blocks.append(_section(decided))
        blocks.append(_context("The full report is `governor/design.md`."))
    elif waiting:
        blocks.append({"type": "actions", "block_id": f"gate_{short(thread_id)}", "elements": [
            {"type": "button", "action_id": APPROVE_ACTION, "style": "primary", "value": thread_id,
             "text": {"type": "plain_text", "text": "Approve"}},
            {"type": "button", "action_id": REJECT_ACTION, "style": "danger", "value": thread_id,
             "text": {"type": "plain_text", "text": "Reject"}},
        ]})
        blocks.append(_context("The full report is `governor/design.md` (attached). Approving builds silver and gold."))
    else:
        blocks.append(_context(f"Status `{status}`: the design cannot be approved. See `governor/design.md`."))
    text = f"Design for build {short(thread_id)}{of}: {len(build)} KPIs to build, {len(decline)} to decline"
    return text, blocks


def reject_modal(thread_id: str) -> dict:
    return {
        "type": "modal", "callback_id": REJECT_MODAL, "private_metadata": thread_id,
        "title": {"type": "plain_text", "text": "Reject the design"},
        "submit": {"type": "plain_text", "text": "Reject"},
        "close": {"type": "plain_text", "text": "Cancel"},
        "blocks": [
            _section(f"Build `{short(thread_id)}`: the note goes back to the plan model for one more proposal."),
            {"type": "input", "block_id": NOTE_BLOCK, "label": {"type": "plain_text", "text": "What should change?"},
             "element": {"type": "plain_text_input", "action_id": NOTE_ACTION, "multiline": True, "max_length": 1000}},
        ],
    }


# --------------------------------------------------------------------------- thread replies


def escalation(thread_id: str, stage: Any, model: Any, error: Any) -> tuple[str, list[dict]]:
    """The failing node and its error, without data values. Neither is ever empty: the stage stands in."""
    stage = stage or "build"
    node = str(model) if model else f"{stage} stage"
    error = error or f"the {stage} stage ended with no error recorded; see governor/build.json"
    head = f":rotating_light: *Build `{short(thread_id)}` escalated* at {stage}: `{node}`"
    tests = failing_tests(error)
    # failing tests: names and counts only (a dbt test message can carry row text); else the scrubbed error
    body = safe_text(tests_reason(tests), 600) if tests else safe_text(error, 600)
    blocks = [_section(head), _section(f"```{body}```"),
              _context("Fix the model in the target project or reject and re-run; details in `governor/build.json`.")]
    return f"Build {short(thread_id)} escalated at {stage}: {node}", blocks


def published(thread_id: str, branch: Any, pr_url: str | None = None, pr_opened: bool = False,
              certify: str | None = None) -> tuple[str, list[dict]]:
    if pr_url:
        text = f":rocket: Build `{short(thread_id)}` published: <{pr_url}|pull request> (branch `{branch}`)"
    else:
        state = "pull request opened" if pr_opened else "no pull request opened"
        text = f":rocket: Build `{short(thread_id)}` published on branch `{branch}` ({state})"
    return text, [_section(text), _section(f"*Next:* {after_publish(pr_url, branch, certify)}")]


def line(text: str) -> tuple[str, list[dict]]:
    return text, [_section(text)]


def with_tenant(text: str, block_list: list[dict] | None, tenant: str) -> tuple[str, list[dict]]:
    """A thread reply in multi-tenant mode (batch3 section 32.3): the fallback text and a context line name the
    tenant. A plain-text reply becomes one section plus that line."""
    name = safe_text(tenant, 60)
    out = list(block_list) if block_list else [_section(text)]
    return f"{text} (tenant {name})", out + [_context(f"tenant {name}")]


def status_list(threads: list[dict]) -> str:
    """``/governor status``: one line per recent thread (newest first)."""
    if not threads:
        return "No build threads yet."
    return "Recent builds:\n" + "\n".join(
        f"• `{short(t.get('thread_id'))}` {t.get('project') or ''}: {t.get('kind')}"
        + (f" ({t.get('status')})" if t.get("status") else "") + f", {t.get('ts') or ''}" for t in threads)


# --------------------------------------------------------------------------- /governor ask (batch2d section 22)

ASK_ACK = "Looking that up..."
ASK_REFUSAL = "Only users listed in GOVERNOR_SLACK_ASKERS (default: the runners) can ask for certified answers."
ASK_ERROR = "Certified answers are not available right now: {reason}"


def slack_escape(text: Any, limit: int = 300) -> str:
    """User text for a Slack message: one line, ``&``, ``<`` and ``>`` escaped (no mentions, no links)."""
    s = " ".join(str(text or "").split())
    if len(s) > limit:
        s = s[: limit - 1] + "…"
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def ask_context(role: str, kpi_id: Any = None) -> str:
    return f"certified path · role {role}" + (f" · KPI {kpi_id}" if kpi_id else "")


def ask_answer(question: str, answer_text: str, role: str, kpi_id: Any = None) -> tuple[str, list[dict]]:
    """The channel message for ``answer``, ``not_available`` and ``unanswerable``: the question (escaped, one line),
    the answer text unchanged (it carries the citation or the gap) and the context line. Never SQL."""
    q = f":speech_balloon: *{slack_escape(question)}*"
    blocks = [_section(q), _section(answer_text), _context(ask_context(role, kpi_id))]
    return answer_text, blocks


def ask_error(reason: Any) -> str:
    """The ephemeral error line; the reason is scrubbed (no data values)."""
    return ASK_ERROR.format(reason=safe_text(reason, 200) or "unknown error")


def usage(targets: Iterable[str], error: str | None = None, workspace: tuple[str, str] | None = None,
          tenants: str | None = None) -> str:
    """The usage text; ``workspace`` (knowledge folder name, ``host:port/db``) adds the footer line. ``tenants``
    (multi-tenant mode, ``<name>: <host>:<port>/<db>, ...``) replaces it with the tenant list."""
    names = ", ".join(f"`{t}`" for t in sorted(targets)) or "none configured"
    text = (f"{error}\n" if error else "") + USAGE.format(targets=names)
    if tenants:
        text += f"\ntenants: {tenants}"
    elif workspace:
        text += f"\nworkspace: knowledge {workspace[0]} · database {workspace[1]}"
    return text


ASK_MULTI_TENANT = "ask serves one tenant only; it is not available in multi-tenant mode yet"


__all__ = ["ASK_ACK", "ASK_ERROR", "ASK_MULTI_TENANT", "ASK_REFUSAL", "with_tenant", "ask_answer", "ask_context", "ask_error", "slack_escape",
           "PUBLISH_ACTION","after_publish", "copyable", "built_reply", "certify_command", "decided_line", "publish_actions",
           "published_link", "BUILT", "FAILED", "INTERRUPTED", "MAPPINGS_OMITTED", "PUBLISHED", "SUPERSEDED", "TERMINAL", "UP_TO_DATE",
           "design_without_mappings", "failing_tests", "first_line", "node_name", "reason_line",
           "run_results_failures", "tests_reason", "APPROVE_ACTION","NOTE_ACTION", "NOTE_BLOCK", "REJECT_ACTION", "REJECT_MODAL", "STAGES", "design_card",
           "escalation", "line", "progress", "published", "reject_modal", "safe_text", "short", "status_list", "usage"]
