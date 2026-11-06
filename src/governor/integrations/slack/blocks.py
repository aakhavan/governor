"""Block Kit rendering for the Slack app (batch2c section 17). Pure functions: no network, no tokens.

Every function returns ``(text, blocks)`` (``text`` is the notification fallback) or a view dict. Inputs are build
state the notifier already holds: names, counts, codes, statuses and cost. Nothing here reads a profile, and free
text that could quote data (model replies, validation problems, dbt errors) goes through :func:`safe_text`, which
drops quoted literals and ``DETAIL`` lines.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

APPROVE_ACTION = "governor_approve"
REJECT_ACTION = "governor_reject"
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
         "• `/governor run <target>`: start a build (targets: {targets})\n"
         "• `/governor status`: recent build threads\n"
         "• `/governor approve <thread>`: approve the design at the gate\n"
         "• `/governor reject <thread> <note>`: send the design back with a note\n"
         "• `/governor publish <thread>`: commit the built project to a branch and open the pull request\n"
         "`<thread>` is the full build thread id or its first 8 characters.")

_MAX_ITEMS = 25
_MAX_TEXT = 2800  # Block Kit section text limit is 3000
_QUOTED = re.compile(r"'(?:[^'\\]|\\.|'')*'")
_DQUOTED = re.compile(r'"(?:[^"\\]|\\.|"")*"')  # Postgres quotes values as "..." (identifiers too; both go)
_DETAIL = re.compile(r"^\s*(DETAIL|HINT|Failing row|Key \().*$", re.IGNORECASE | re.MULTILINE)
_LONG_NUMBER = re.compile(r"(?<![\w.])-?\d[\d,.]{3,}\d(?![\w.])")


def short(thread_id: str | None) -> str:
    return str(thread_id or "")[:8]


def safe_text(text: Any, limit: int = 200) -> str:
    """One line without data values: quoted literals become '…', DETAIL/HINT/Key lines and long numbers go."""
    s = _DETAIL.sub("", str(text or ""))
    s = _QUOTED.sub("'…'", s)
    s = _DQUOTED.sub('"…"', s)
    s = _LONG_NUMBER.sub("#", s)
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


def progress(thread_id: str, rec: dict) -> tuple[str, list[dict]]:
    """The one message per build thread: a stage checklist, status, repairs and cost."""
    done = set(rec.get("done") or [])
    project = rec.get("project") or "build"
    status = rec.get("status") or "running"
    lines = [f"{':white_check_mark:' if key in done else ':white_large_square:'} {label}" for key, label in STAGES]
    head = f"*governor build `{short(thread_id)}`* ({project}): {status}"
    facts = (f"design repairs: {int(rec.get('design_repairs') or 0)} · SQL repairs: {int(rec.get('sql_repairs') or 0)}"
             f" · model cost: {_cost(rec.get('cost_usd'))} · thread `{thread_id}`")
    text = f"governor build {short(thread_id)} ({project}): {status}"
    return text, [_section(head), _section("\n".join(lines)), _context(facts)]


# --------------------------------------------------------------------------- design card


def _gap_reason(k: dict) -> str:
    gap = k.get("gap") or {}
    missing = ", ".join(str(m) for m in (gap.get("missing") or [])[:6])
    reason = safe_text(k.get("reason") or "no reason given", 160)
    return f"`{k.get('id')}`: {reason}" + (f" (missing: {safe_text(missing, 120)})" if missing else "")


def design_card(thread_id: str, proposal: dict | None, findings: list[dict] | None, status: str) -> tuple[str, list[dict]]:
    """Silver models, KPIs to build and to decline with gap reasons, validation findings, and (when the design
    waits at the gate) Approve / Reject buttons. Mappings are not shown: they can hold SQL literals."""
    proposal = proposal or {}
    findings = findings or []
    silver = proposal.get("silver_models") or []
    kpis = proposal.get("kpis") or []
    build = [k for k in kpis if k.get("decision") == "build"]
    decline = [k for k in kpis if k.get("decision") == "decline"]
    waiting = status == "awaiting_design_approval"
    title = (f"*Design for build `{short(thread_id)}`*: {len(silver)} silver models, {len(build)} KPIs to build, "
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
    if waiting:
        blocks.append({"type": "actions", "block_id": f"gate_{short(thread_id)}", "elements": [
            {"type": "button", "action_id": APPROVE_ACTION, "style": "primary", "value": thread_id,
             "text": {"type": "plain_text", "text": "Approve"}},
            {"type": "button", "action_id": REJECT_ACTION, "style": "danger", "value": thread_id,
             "text": {"type": "plain_text", "text": "Reject"}},
        ]})
        blocks.append(_context("The full report is `governor/design.md` (attached). Approving builds silver and gold."))
    else:
        blocks.append(_context(f"Status `{status}`: the design cannot be approved. See `governor/design.md`."))
    text = f"Design for build {short(thread_id)}: {len(build)} KPIs to build, {len(decline)} to decline"
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
    """The failing model and its error, without data values."""
    where = f"`{model}`" if model else "no single model"
    head = f":rotating_light: *Build `{short(thread_id)}` escalated* at {stage or 'build'}: {where}"
    blocks = [_section(head)]
    if error:
        blocks.append(_section(f"```{safe_text(error, 600)}```"))
    blocks.append(_context("Fix the model in the target project or reject and re-run; details in `governor/build.json`."))
    return f"Build {short(thread_id)} escalated at {stage or 'build'}: {model or 'no single model'}", blocks


def published(thread_id: str, branch: Any, pr_url: str | None = None, pr_opened: bool = False) -> tuple[str, list[dict]]:
    if pr_url:
        text = f":rocket: Build `{short(thread_id)}` published: <{pr_url}|pull request> (branch `{branch}`)"
    else:
        state = "pull request opened" if pr_opened else "no pull request opened"
        text = f":rocket: Build `{short(thread_id)}` published on branch `{branch}` ({state})"
    return text, [_section(text)]


def line(text: str) -> tuple[str, list[dict]]:
    return text, [_section(text)]


def status_list(threads: list[dict]) -> str:
    """``/governor status``: one line per recent thread (newest first)."""
    if not threads:
        return "No build threads yet."
    return "Recent builds:\n" + "\n".join(
        f"• `{short(t.get('thread_id'))}` {t.get('project') or ''}: {t.get('kind')}"
        + (f" ({t.get('status')})" if t.get("status") else "") + f", {t.get('ts') or ''}" for t in threads)


def usage(targets: Iterable[str], error: str | None = None) -> str:
    names = ", ".join(f"`{t}`" for t in sorted(targets)) or "none configured"
    return (f"{error}\n" if error else "") + USAGE.format(targets=names)


__all__ = ["APPROVE_ACTION", "NOTE_ACTION", "NOTE_BLOCK", "REJECT_ACTION", "REJECT_MODAL", "STAGES", "design_card",
           "escalation", "line", "progress", "published", "reject_modal", "safe_text", "short", "status_list", "usage"]
