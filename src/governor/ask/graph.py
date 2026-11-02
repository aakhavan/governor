"""The governor-ask graph: question in, governed answer (or a refusal) out.

One LangGraph ``StateGraph``. Models only fill in plans, SQL and wording;
code owns every edge:

    guard -> retrieve_context -> plan -> (clarify -> plan) -> draft_sql
      -> validate -> dry_run -> execute -> answer -> record_trace
                 \\-> repair (at most MAX_REPAIRS) -> validate

Policy codes from the validator end in a refusal that names the rule. The
answer's data values are filled in by Python from the result rows; the model
only writes the wording around ``{rRcC}`` placeholders.

Relative dates resolve against ``paths.as_of()``. The only clock reads are the
trace timestamps (``started_at`` and ``ts``).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable

import duckdb
import pydantic
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from governor.ask import MODEL, executor, retrieval, traces
from governor.ask.policy import Policy
from governor.ask.schemas import AnswerDraft, AskState, QueryPlan, SqlDraft
from governor.ask.validator import validate as validate_sql
from governor.core import lineage, paths, security

PROMPTS = Path(__file__).resolve().parent / "prompts"
log = logging.getLogger(__name__)
MAX_REPAIRS = 2
RETRIEVE_K = 5
PREVIEW_ROWS = 5
PREVIEW_COLUMNS = 12

# Validator codes that end the question: retrying cannot make them allowed.
POLICY_RULES = {
    "PII_FORBIDDEN": "personal-data columns may not be shown, filtered, grouped or joined on for your role",
    "TABLE_NOT_ALLOWED": "only the governed mart tables may be queried",
    "UNKNOWN_ROLE": "the role is not defined in the access policy",
}

# Fixed refusal texts. None of them quotes the user's words.
MSG_GUARD = "I can only answer questions about the billing data. Please ask the question in plain language."
MSG_TOO_LONG = "That question is too long. Please ask it in a few sentences."
MSG_NO_LETTERS = "Please write the question in words."
MSG_UNANSWERABLE = "The governed billing marts do not hold the data this question needs."
MSG_CLARIFY_FAILED = "I still could not tell what the question needs after the clarification. Please ask it again with more detail."
MSG_REPAIR = "I could not write a query for this question that passes validation, so nothing was run."
MSG_EXEC = "The query could not be run within the warehouse limits, so there is no answer."
MSG_EMPTY = "The query ran and returned no rows."
MSG_FALLBACK = "The result is in the table below."

_PLACEHOLDER = re.compile(r"\{r(\d+)c(\d+)\}")
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_SQL_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)


# ---------------------------------------------------------------------------
# prompts, dates and model calls


def _prompt(name: str, **values: str) -> str:
    """Fill ``{key}`` slots in ``prompts/<name>.md``; other braces (JSON, placeholders) stay."""
    text = (PROMPTS / f"{name}.md").read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def _month_start(day: date) -> date:
    return day.replace(day=1)


def date_anchors(as_of: datetime) -> str:
    """Dates the prompts need, computed from as_of so the model does no calendar arithmetic."""
    today = as_of.date()
    this_month = _month_start(today)
    last_month = _month_start(this_month - timedelta(days=1))
    anchors = [
        ("as_of date", today),
        ("start of the as_of month (month so far)", this_month),
        ("start of the previous full month", last_month),
        ("end of the previous full month (exclusive)", this_month),
        ("start of the as_of year", today.replace(month=1, day=1)),
        ("start of the previous year", today.replace(year=today.year - 1, month=1, day=1)),
        ("thirty days before as_of", today - timedelta(days=30)),
    ]
    return "\n".join(f"- {label}: {value.isoformat()}" for label, value in anchors)


def _text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content or "")


def _parse(text: str, schema: type[pydantic.BaseModel]) -> pydantic.BaseModel | None:
    """The JSON object in ``text`` as ``schema``; bare SQL counts as a SqlDraft. None if neither."""
    body = _FENCE.sub("", text.strip()).strip()
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end > start:
        try:
            return schema.model_validate(json.loads(body[start : end + 1]))
        except (json.JSONDecodeError, pydantic.ValidationError):
            pass
    if schema is SqlDraft and _SQL_START.match(body):
        return SqlDraft(sql=body)
    return None


def _model_name(llm: Any) -> str:
    return str(getattr(llm, "model_name", None) or getattr(llm, "model", None) or type(llm).__name__)


def _usage(node: str, llm: Any, message: Any) -> dict:
    from governor.core.llm import usage_from_message

    usage = usage_from_message(message) if message is not None else {}
    return {
        "node": node,
        "model": _model_name(llm),
        "tokens_in": usage.get("input_tokens", 0),
        "tokens_out": usage.get("output_tokens", 0),
        "cost_usd": usage.get("cost_usd"),
    }


def _ask(llm: Any, node: str, prompt: str, schema: type[pydantic.BaseModel]):
    """One model call -> (parsed reply or None, usage row).

    A chat model with ``with_structured_output`` gets the schema as structured
    output (raw message kept for usage); anything else (the offline FakeLLM)
    is invoked and its text parsed as JSON.
    """
    if hasattr(llm, "with_structured_output"):
        reply = llm.with_structured_output(schema, include_raw=True).invoke(prompt)
        raw = reply.get("raw")
        parsed = reply.get("parsed")
        if parsed is None and raw is not None:
            parsed = _parse(_text(raw.content), schema)
        return parsed, _usage(node, llm, raw)
    message = llm.invoke(prompt)
    return _parse(_text(message.content), schema), _usage(node, llm, message)


# ---------------------------------------------------------------------------
# answer filling


def format_value(value: Any) -> str:
    """How one result cell is written into the answer text."""
    if value is None:
        return "n/a"
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value)


def _values_in(text: str, rows: list[list[Any]]) -> bool:
    """True when ``text`` contains a non-numeric result value (case-insensitive, whole words)."""
    lowered = text.lower()
    for row in rows:
        for value in row:
            if value is None or isinstance(value, (int, float, Decimal, bool, date, datetime)):
                continue
            needle = str(value).strip().lower()
            if len(needle) < 2:
                continue
            if re.search(r"(?<!\w)" + re.escape(needle) + r"(?!\w)", lowered):
                return True
    return False


def fill_answer(template: str, columns: list[str], rows: list[list[Any]]) -> str | None:
    """Fill ``{rRcC}`` from ``rows``; None when the wording breaks the rules.

    Rules: every placeholder points at a real cell; the text outside
    placeholders has no digits and no result values.
    """
    outside = _PLACEHOLDER.sub(" ", template)
    if re.search(r"\d", outside) or _values_in(outside, rows) or "{" in outside or "}" in outside:
        return None
    for match in _PLACEHOLDER.finditer(template):
        r, c = int(match.group(1)), int(match.group(2))
        if r >= len(rows) or c >= len(columns):
            return None
    return _PLACEHOLDER.sub(lambda m: format_value(rows[int(m.group(1))][int(m.group(2))]), template).strip()


def _cells_preview(columns: list[str], rows: list[list[Any]]) -> str:
    lines = []
    for r, row in enumerate(rows[:PREVIEW_ROWS]):
        for c, name in enumerate(columns[:PREVIEW_COLUMNS]):
            lines.append(f"- {{r{r}c{c}}} ({name}) = {format_value(row[c])}")
    return "\n".join(lines) or "(no rows)"


# ---------------------------------------------------------------------------
# lineage and freshness


def lineage_card(tables: list[str], as_of: datetime, meta_path: Path | None = None) -> dict:
    """Upstream sources of ``tables`` and their freshness against as_of, from the metadata store."""
    meta = Path(meta_path or paths.META)
    out = {"sources": [], "freshness": []}
    if not tables or not meta.is_file():
        return out
    connection = duckdb.connect(str(meta), read_only=True)
    try:
        present = {r[0] for r in connection.execute("SELECT table_name FROM information_schema.tables").fetchall()}
        if not {"nodes", "edges"} <= present:
            return out
        ids = [
            r[0]
            for r in connection.execute(
                "SELECT unique_id FROM nodes WHERE resource_type = 'model' AND lower(name) IN "
                f"({', '.join('?' for _ in tables)})",
                [t.lower() for t in tables],
            ).fetchall()
        ]
        graph = {
            "nodes": [r[0] for r in connection.execute("SELECT unique_id FROM nodes").fetchall()],
            "edges": [{"parent": p, "child": c} for p, c in connection.execute("SELECT parent, child FROM edges").fetchall()],
        }
        fresh = {}
        if "freshness" in present:
            fresh = {
                r[0]: (r[1], r[2])
                for r in connection.execute("SELECT unique_id, status, max_loaded_at FROM freshness").fetchall()
            }
    finally:
        connection.close()
    depth = max(len(graph["nodes"]), 1)
    sources: list[str] = []
    for uid in ids:
        for node in lineage.upstream(uid, graph, depth):
            if node.startswith("source.") and node not in sources:
                sources.append(node)
    sources.sort()
    out["sources"] = sources
    for source in sources:
        status, loaded = fresh.get(source, (None, None))
        age = None
        if loaded:
            loaded_at = loaded if isinstance(loaded, datetime) else datetime.fromisoformat(str(loaded))
            if loaded_at.tzinfo is None:
                loaded_at = loaded_at.replace(tzinfo=timezone.utc)
            age = round((as_of - loaded_at).total_seconds() / 3600, 2)
        out["freshness"].append(
            {"source": source, "status": status, "max_loaded_at": str(loaded) if loaded else None, "age_hours_at_as_of": age}
        )
    return out


# ---------------------------------------------------------------------------
# graph


def _hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, default=format_value, sort_keys=True).encode("utf-8")).hexdigest()


def _refuse(outcome: str, text: str, **extra: Any) -> dict:
    return {"outcome": outcome, "refusal": text, **extra}


def build_graph(
    *,
    llm: Any = None,
    checkpointer: Any = None,
    database: str | Path | None = None,
    access_path: Path | None = None,
    meta_path: Path | None = None,
    cards: list[dict] | None = None,
    retrieval_mode: retrieval.Mode = "bm25",
    embedder: Any = "fake",
    as_of: datetime | None = None,
    trace_path: Path | None = None,
    store_traces: bool = True,
):
    """Compile the ask graph.

    ``llm`` is one chat model for every node (tests pass a FakeLLM). With
    ``None`` the real models are built on first use: FAST_MODEL (gpt-5-nano)
    for ``plan``, gpt-5-mini for ``draft_sql``, ``repair`` and ``answer``, so
    compiling needs no network or key. ``checkpointer`` defaults to an
    ``InMemorySaver``. ``database``, ``access_path``, ``meta_path``, ``cards``
    and ``as_of`` point the graph at fixtures. Retrieval defaults to BM25
    (best tune recall in G4, no embedding call). ``record_trace`` writes each
    trace to ``trace_path`` (default ``paths.TRACES``) unless ``store_traces``
    is false; a failed write is logged and the answer is still returned.
    """
    models: dict[str, Any] = {}

    def model(kind: str) -> Any:
        if llm is not None:
            return llm
        if kind not in models:
            from governor.core.llm import get_chat_model

            models[kind] = get_chat_model(fast=True) if kind == "plan" else get_chat_model(model=MODEL)
        return models[kind]

    def instant() -> datetime:
        return as_of or paths.as_of()

    def common(state: AskState) -> dict[str, str]:
        moment = instant()
        return {
            "context": state.get("context") or "(no catalog cards matched)",
            "plan": json.dumps(state.get("plan") or {}, indent=1),
            "as_of": moment.isoformat(),
            "date_anchors": date_anchors(moment),
            "question": state["question"].strip(),
        }

    # -- nodes ---------------------------------------------------------------

    def guard(state: AskState) -> dict:
        started = {"started_at": datetime.now(timezone.utc).isoformat()}
        question = state.get("question")
        ok, why = security.validate_input(question, min_chars=security.MIN_ANSWER_CHARS)
        if not ok:
            text = {security.MSG_TOO_LONG: MSG_TOO_LONG, security.MSG_NO_LETTERS: MSG_NO_LETTERS}.get(why, MSG_GUARD)
            return {**started, **_refuse("refused_guard", text), "policy_decisions": [{"rule": "guard:input_bounds", "decision": "refuse"}]}
        flagged, rules = security.regex_screen(question)
        if flagged:
            return {
                **started,
                **_refuse("refused_guard", MSG_GUARD),
                "policy_decisions": [{"rule": f"guard:{name}", "decision": "refuse"} for name in rules],
            }
        return {**started, "refusal": None, "outcome": None, "repairs": 0}

    def retrieve_context(state: AskState) -> dict:
        hits = retrieval.search(state["question"], k=RETRIEVE_K, mode=retrieval_mode, embedder=embedder, cards=cards)
        by_id = {c["id"]: c for c in (cards if cards is not None else retrieval.load_cards())}
        context = "\n\n".join(by_id[h.card_id]["text"] for h in hits if h.card_id in by_id)
        return {"retrieved_ids": [h.card_id for h in hits], "context": context}

    def plan(state: AskState) -> dict:
        extra = ""
        if state.get("clarification"):
            c = state["clarification"]
            extra = (
                "The user was asked a clarifying question and answered it. Use the answer; "
                f"do not ask again.\nClarifying question: {c['slot']}\nUser's answer: {c['answer']}"
            )
        prompt = _prompt("plan", **{**common(state), "clarification": extra})
        parsed, usage = _ask(model("plan"), "plan", prompt, QueryPlan)
        if parsed is None:
            # The plan is advisory: an unreadable plan still lets draft_sql try.
            return {"plan": QueryPlan(intent="answer").model_dump(), "plan_error": "unparseable plan", "usage": [usage]}
        update: dict = {"plan": parsed.model_dump(), "plan_error": None, "usage": [usage]}
        if parsed.injection:
            update.update(_refuse("refused_guard", MSG_GUARD))
            update["policy_decisions"] = [{"rule": "guard:model_flag", "decision": "refuse"}]
        elif parsed.intent == "unanswerable":
            update.update(_refuse("unanswerable", MSG_UNANSWERABLE))
        elif parsed.intent == "clarify" and state.get("clarification"):
            update.update(_refuse("clarify_failed", MSG_CLARIFY_FAILED))
        return update

    def clarify(state: AskState) -> dict:
        slot = (state.get("plan") or {}).get("missing_slot") or "Please add the missing detail."
        answer = interrupt({"missing_slot": slot})
        answer = answer if isinstance(answer, str) else str(answer)
        ok, _ = security.validate_input(answer, min_chars=security.MIN_ANSWER_CHARS)
        flagged, rules = security.regex_screen(answer)
        if not ok or flagged:
            return {
                **_refuse("refused_guard", MSG_GUARD),
                "clarification": {"slot": slot, "answer": None},
                "policy_decisions": [{"rule": f"guard:{name}", "decision": "refuse"} for name in rules or ["input_bounds"]],
            }
        return {"clarification": {"slot": slot, "answer": answer.strip()}}

    def _draft(node: str, prompt: str) -> dict:
        parsed, usage = _ask(model("sql"), node, prompt, SqlDraft)
        if parsed is None:
            return {"sql": "", "rationale": "", "usage": [usage]}
        return {"sql": parsed.sql, "rationale": parsed.rationale, "usage": [usage]}

    def draft_sql(state: AskState) -> dict:
        return _draft("draft_sql", _prompt("draft_sql", **common(state)))

    def repair(state: AskState) -> dict:
        errors = [f"- {code}" for code in state.get("codes") or []]
        errors += [f"  {reason}" for reason in state.get("reasons") or []]
        if state.get("dry_run_error"):
            errors.append(f"- database: {state['dry_run_error']}")
        prompt = _prompt(
            "repair",
            **common(state),
            sql=state.get("sql") or "(no SQL)",
            errors="\n".join(errors) or "- unknown",
        )
        return {**_draft("repair", prompt), "repairs": state.get("repairs", 0) + 1}

    def _failed(state: AskState, codes: list[str], reasons: list[str], error: str | None, stage: str) -> dict:
        """State update for a failed check: policy refusal, out of repairs, or on to repair."""
        update: dict = {
            "codes": codes,
            "reasons": reasons,
            "dry_run_error": error,
            "validated_sql": None,
            "sql_attempts": [{"stage": stage, "sql": state.get("sql"), "codes": codes, "error": error}],
        }
        rules = [code for code in codes if code in POLICY_RULES]
        if rules:
            update["policy_decisions"] = [{"rule": code, "decision": "refuse"} for code in rules]
            text = "Refused by access policy. " + " ".join(f"{code}: {POLICY_RULES[code]}." for code in rules)
            update.update(_refuse("refused_policy", text))
        elif "TIMEOUT" in codes:
            update.update(_refuse("refused_error", MSG_EXEC))
        elif state.get("repairs", 0) >= MAX_REPAIRS:
            update.update(_refuse("refused_repair", MSG_REPAIR))
        return update

    def validate(state: AskState) -> dict:
        sql = state.get("sql") or ""
        if not sql:
            return _failed(state, ["PARSE_ERROR"], ["the model did not return SQL"], None, "validate")
        checked = validate_sql(sql, state["role"], access_path=access_path, meta_path=meta_path)
        if not checked.ok:
            return _failed(state, list(checked.codes), list(checked.reasons), None, "validate")
        return {"validated_sql": checked.sql, "tables": list(checked.tables), "codes": [], "reasons": [], "dry_run_error": None}

    def dry_run(state: AskState) -> dict:
        policy = Policy.for_role(state["role"], access_path=access_path, meta_path=meta_path)
        try:
            result = executor.dry_run(state["validated_sql"], timeout_s=policy.timeout_s, database=database)
        except executor.QueryTimeout as error:
            return _failed(state, ["TIMEOUT"], [], str(error), "dry_run")
        if not result.ok:
            return _failed(state, ["DRY_RUN_FAILED"], [], result.error, "dry_run")
        return {"dry_run_error": None}

    def execute(state: AskState) -> dict:
        result = executor.execute(
            state["sql"], state["role"], access_path=access_path, meta_path=meta_path, database=database
        )
        if not result.ok:
            error = result.reasons[0] if result.reasons and result.sql is not None else None
            reasons = [] if result.sql is not None else list(result.reasons)
            return _failed(state, list(result.codes), reasons, error, "execute")
        return {
            "executed_sql": result.sql,
            "columns": list(result.columns),
            "rows": [list(row) for row in result.rows],
            "row_count": result.row_count,
            "sql_attempts": [{"stage": "execute", "sql": state.get("sql"), "codes": [], "error": None}],
            "outcome": "answer",
        }

    def answer(state: AskState) -> dict:
        columns, rows = state.get("columns") or [], state.get("rows") or []
        usage: list[dict] = []
        if not rows:
            text = MSG_EMPTY
        else:
            prompt = _prompt(
                "answer",
                question=state["question"].strip(),
                columns=", ".join(f"c{i}={name}" for i, name in enumerate(columns)),
                row_count=str(len(rows)),
                cells=_cells_preview(columns, rows),
            )
            parsed, used = _ask(model("answer"), "answer", prompt, AnswerDraft)
            usage.append(used)
            filled = fill_answer(parsed.text_with_placeholders, columns, rows) if parsed else None
            text = filled or MSG_FALLBACK
        moment = instant()
        tables = state.get("tables") or []
        policy = Policy.for_role(state["role"], access_path=access_path, meta_path=meta_path)
        card = {
            "text": text,
            "wording": "model" if rows and text != MSG_FALLBACK else "fixed",
            "columns": columns,
            "rows": rows,
            "row_count": state.get("row_count", len(rows)),
            "truncated": len(rows) >= policy.row_cap,
            "sql": state.get("executed_sql"),
            "models": tables,
            "as_of": moment.isoformat(),
            **lineage_card(tables, moment, meta_path),
        }
        return {"answer": card, "usage": usage}

    def record_trace(state: AskState) -> dict:
        now = datetime.now(timezone.utc)
        started = state.get("started_at")
        latency = round((now - datetime.fromisoformat(started)).total_seconds(), 3) if started else None
        usage = state.get("usage") or []
        costs = [u.get("cost_usd") for u in usage]
        card = state.get("answer")
        if card is None:
            card = {"text": state.get("refusal") or MSG_EXEC, "refused": True}
        question = state.get("question") or ""
        rows = state.get("rows") or []
        trace = {
            "trace_id": str(uuid.uuid4()),
            "ts": now.isoformat(),
            "role": state.get("role"),
            "question_hash": hashlib.sha256(question.encode("utf-8")).hexdigest(),
            "question_len": len(question),
            "retrieved_ids": list(state.get("retrieved_ids") or []),
            "plan_json": json.dumps(state.get("plan"), sort_keys=True) if state.get("plan") else None,
            "sql_attempts": list(state.get("sql_attempts") or []),
            "policy_decisions": list(state.get("policy_decisions") or []),
            "executed_sql": state.get("executed_sql"),
            "row_count": state.get("row_count", 0) if state.get("executed_sql") else 0,
            "result_hash": _hash([state.get("columns") or [], rows]) if state.get("executed_sql") else None,
            "answer": card["text"],
            "outcome": state.get("outcome") or "refused_error",
            "models": sorted({u["model"] for u in usage}),
            "tokens_in": sum(int(u.get("tokens_in") or 0) for u in usage),
            "tokens_out": sum(int(u.get("tokens_out") or 0) for u in usage),
            "cost_usd": round(sum(costs), 6) if costs and all(c is not None for c in costs) else (0.0 if not costs else None),
            "latency_s": latency,
            "human_feedback": None,
        }
        return {"answer": card, "trace": trace, "trace_error": store(trace, question, state.get("columns") or [], rows)}

    def store(trace: dict, question: str, columns: list[str], rows: list[list[Any]]) -> str | None:
        """Write the trace; on any failure log it and return the error type (the answer stays)."""
        if not store_traces:
            return None
        try:
            secrets = traces.pii_values(
                trace["executed_sql"], columns, rows, access_path=access_path, meta_path=meta_path
            )
            traces.write_trace(
                trace, question=question, secrets=secrets, mask=traces.default_mask(access_path), path=trace_path
            )
        except Exception as exc:  # noqa: BLE001  (a trace store problem must not lose the answer)
            log.warning("trace %s was not written: %s", trace["trace_id"], type(exc).__name__)
            return type(exc).__name__
        return None

    # -- edges ---------------------------------------------------------------

    def stop_or(next_node: str) -> Callable[[AskState], str]:
        def route(state: AskState) -> str:
            return "record_trace" if state.get("refusal") else next_node

        return route

    def after_plan(state: AskState) -> str:
        if state.get("refusal"):
            return "record_trace"
        if (state.get("plan") or {}).get("intent") == "clarify":
            return "clarify"
        return "draft_sql"

    def after_check(next_node: str) -> Callable[[AskState], str]:
        def route(state: AskState) -> str:
            if state.get("refusal"):
                return "record_trace"
            if state.get("codes") or state.get("dry_run_error"):
                return "repair"
            return next_node

        return route

    builder = StateGraph(AskState)
    for name, fn in [
        ("guard", guard),
        ("retrieve_context", retrieve_context),
        ("plan", plan),
        ("clarify", clarify),
        ("draft_sql", draft_sql),
        ("validate", validate),
        ("dry_run", dry_run),
        ("repair", repair),
        ("execute", execute),
        ("answer", answer),
        ("record_trace", record_trace),
    ]:
        builder.add_node(name, fn)
    builder.add_edge(START, "guard")
    builder.add_conditional_edges("guard", stop_or("retrieve_context"), ["retrieve_context", "record_trace"])
    builder.add_edge("retrieve_context", "plan")
    builder.add_conditional_edges("plan", after_plan, ["clarify", "draft_sql", "record_trace"])
    builder.add_conditional_edges("clarify", stop_or("plan"), ["plan", "record_trace"])
    builder.add_edge("draft_sql", "validate")
    builder.add_edge("repair", "validate")
    builder.add_conditional_edges("validate", after_check("dry_run"), ["dry_run", "repair", "record_trace"])
    builder.add_conditional_edges("dry_run", after_check("execute"), ["execute", "repair", "record_trace"])
    builder.add_conditional_edges("execute", after_check("answer"), ["answer", "repair", "record_trace"])
    builder.add_edge("answer", "record_trace")
    builder.add_edge("record_trace", END)
    return builder.compile(checkpointer=checkpointer if checkpointer is not None else InMemorySaver())
