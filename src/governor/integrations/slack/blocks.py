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
TERMINAL = (FAILED, BUILT, PUBLISHED, SUPERSEDED, INTERRUPTED)
_LABELS = dict(STAGES)


def _checklist(rec: dict) -> list[str]:
    """``:x:`` on the failed stage, ``:heavy_minus_sign:`` on the stages an ended run will never reach."""
    done = set(rec.get("done") or [])
    outcome = rec.get("outcome")
    failed = rec.get("failed_stage") if outcome == FAILED else None
    ended = outcome in (FAILED, SUPERSEDED, INTERRUPTED)
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
    who = f"governor build `{short(thread_id)}` ({rec.get('project') or 'build'})"
    outcome = rec.get("outcome")
    if outcome == FAILED:
        where = rec.get("stopped_at") or _LABELS.get(rec.get("failed_stage") or "", "build")
        reason = safe_text(rec.get("reason") or "no error recorded", 200)
        return f":red_circle: stopped at {where}: *{who}*\n{reason}", f"stopped at {where}: {who}: {reason}"
    if outcome in (BUILT, PUBLISHED):
        link = f" <{rec['pr_url']}|pull request>" if outcome == PUBLISHED and rec.get("pr_url") else ""
        return f":large_green_circle: {outcome}{link}: *{who}*", f"{outcome}: {who}"
    if outcome == SUPERSEDED:
        what = f"superseded by `{short(rec.get('superseded_by'))}`"
        return f":white_circle: {what}: *{who}*", f"{what}: {who}"
    if outcome == INTERRUPTED:
        return f":white_circle: interrupted (bot restarted): *{who}*", f"interrupted (bot restarted): {who}"
    status = rec.get("status") or "running"
    return f"*{who}*: {status}", f"{who}: {status}"


def progress(thread_id: str, rec: dict) -> tuple[str, list[dict]]:
    """The one message per build thread: a header (the terminal state once the run ended), a stage checklist,
    repairs and cost."""
    head, text = _headline(thread_id, rec)
    facts = (f"design repairs: {int(rec.get('design_repairs') or 0)} · SQL repairs: {int(rec.get('sql_repairs') or 0)}"
             f" · model cost: {_cost(rec.get('cost_usd'))} · thread `{thread_id}`")
    return text.replace("`", ""), [_section(head), _section("\n".join(_checklist(rec))), _context(facts)]


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


__all__ = ["BUILT", "FAILED", "INTERRUPTED", "MAPPINGS_OMITTED", "PUBLISHED", "SUPERSEDED", "TERMINAL",
           "design_without_mappings", "failing_tests", "first_line", "node_name", "reason_line",
           "run_results_failures", "tests_reason", "APPROVE_ACTION","NOTE_ACTION", "NOTE_BLOCK", "REJECT_ACTION", "REJECT_MODAL", "STAGES", "design_card",
           "escalation", "line", "progress", "published", "reject_modal", "safe_text", "short", "status_list", "usage"]
