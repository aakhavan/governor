"""Certified answers: ask's path over the certified KPI registry (docs/capstone/batch2b.md section 14).

``answer(question, role, llm, adapter)``:

1. reads ``serve_<role>.governor_certified`` and ``serve_<role>.governor_gaps`` (and the column types of the
   role's serving views) through the Postgres adapter as ``governor_ask`` with the role's reader role set;
2. makes one structured model call (``certified_prompts/certified.md``) that sees the certified KPIs (label,
   definition, grain, value columns) and the gaps, never data values, and returns a ``CertifiedReply``;
3. builds the SQL in code from the chosen KPI's own table, grain column and value column only, runs it through
   the validator in the Postgres dialect with the allowlist = the certified models, and executes it read-only;
4. writes the answer text in Python, numbers included, and cites the KPI id, owner, source tier and reference,
   and who certified it when.

A reply naming a KPI that is not certified, a column that is not one of its value columns, or a period the KPI's
grain cannot express is ``unanswerable``: the model never contributes SQL text, only names checked against the
registry. Outcomes: ``answer``, ``not_available`` (a catalogue KPI that is declined or not certified, quoting its
gap), ``unanswerable`` and ``refused`` (person-level requests).

CLI: ``python -m governor.ask.certified "<question>" --role analyst|finance_admin [--llm fake:SCRIPT|openrouter]``.
A fake script is ``{"certified": ["<reply json>", ...]}``, consumed in order.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal

import pydantic
import yaml

from governor.ask import validator
from governor.ask.policy import Policy
from governor.core import paths
from governor.core.adapters.base import QueryError
from governor.core.serving import READER_ROLES, SERVING_PREFIX

PROMPT_PATH = Path(__file__).resolve().parent / "certified_prompts" / "certified.md"
DEFAULT_ACCESS = paths.KNOWLEDGE / "shop" / "access.yaml"
DEFAULT_KPIS = paths.KNOWLEDGE / "kpis.yaml"
REGISTRY = "governor_certified"
GAPS = "governor_gaps"
GRAIN_COLUMNS = {"month": "month", "cohort_month": "cohort_month"}
MSF = "months_since_first"
# Which period kinds each grain can express.
KINDS = {"month": {"month", "year", "all"}, "cohort_month": {"cohort", "year", "all"}, "total": {"all"}}
# KPIs whose monthly values add up to the period's value (amounts). Every other KPI is a ratio (rate, average, AOV,
# CLV, retention): over a period with several rows it is answered with the per-period values, never summed.
ADDITIVE_KPIS = frozenset({"gmv", "net_revenue"})
SERIES_CAP = 100  # per-period rows listed in one answer (the validator's default limit)
_MONTH = re.compile(r"^(\d{4})-(0[1-9]|1[0-2])$")
_YEAR = re.compile(r"^(\d{4})$")
_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)

Outcome = Literal["answer", "not_available", "unanswerable", "refused"]


class CertifiedError(RuntimeError):
    """The registry could not be read (database down, serving not applied); never carries a DSN."""


# --------------------------------------------------------------------------- model reply


class Period(pydantic.BaseModel):
    model_config = pydantic.ConfigDict(extra="forbid")
    kind: Literal["month", "year", "all", "cohort"]
    value: str | None = None

    @pydantic.field_validator("value", mode="before")
    @classmethod
    def _text(cls, raw: Any) -> Any:
        return str(raw) if isinstance(raw, int) and not isinstance(raw, bool) else raw


class CertifiedReply(pydantic.BaseModel):
    """What the model chooses. Names only: every one is checked against the registry before any SQL exists."""

    model_config = pydantic.ConfigDict(extra="forbid")
    kpi_id: str | None = None
    value_column: str | None = None
    period: Period | None = None
    months_since_first: int | None = pydantic.Field(default=None, ge=0, le=600)
    pick: Literal["value", "max", "sum"] = "value"
    category: Literal["answer", "not_available", "out_of_scope", "person_level"]


class CertifiedAnswer(pydantic.BaseModel):
    outcome: Outcome
    text: str
    value: float | None = None
    kpi_id: str | None = None
    sql: str | None = None
    citation: dict | None = None


# --------------------------------------------------------------------------- registry


@dataclass(frozen=True)
class CertifiedKpi:
    kpi_id: str
    model: str
    label: str
    definition: str
    grain: str
    value_columns: tuple[str, ...]
    owner: str | None = None
    source_tier: str | None = None
    source_ref: str | None = None
    certified_by: str | None = None
    certified_at: Any = None
    git_commit: str | None = None
    columns: tuple[str, ...] = ()  # every column of the serving view

    @property
    def has_msf(self) -> bool:
        return MSF in self.columns

    def citation(self) -> dict:
        at = self.certified_at
        return {
            "kpi_id": self.kpi_id, "label": self.label, "model": self.model, "owner": self.owner,
            "source_tier": self.source_tier, "source_ref": self.source_ref, "certified_by": self.certified_by,
            "certified_at": at.isoformat() if isinstance(at, (dt.date, dt.datetime)) else at,
            "git_commit": self.git_commit,
        }


@dataclass(frozen=True)
class Gap:
    kpi_id: str
    missing: tuple[str, ...]
    typical_sources: tuple[str, ...]
    next_step: str


@dataclass(frozen=True)
class Registry:
    role: str
    schema: str
    kpis: dict[str, CertifiedKpi]
    gaps: dict[str, Gap]
    types: dict[str, dict[str, str]]  # certified model -> column -> data type


def serving_schema(role: str) -> str:
    return f"{SERVING_PREFIX}{role}"


def reader_role(role: str) -> str:
    if role not in READER_ROLES:
        raise ValueError(f"unknown role {role!r}; expected one of {sorted(READER_ROLES)}")
    return READER_ROLES[role]


def default_adapter():
    from governor.core.adapters.postgres import PostgresAdapter

    return PostgresAdapter(allowed_roles=READER_ROLES.values())


def read_registry(adapter: Any, role: str) -> Registry:
    """The certified KPIs and gaps the role's serving schema exposes, read as the role's reader."""
    reader = reader_role(role)
    schema = serving_schema(role)  # role checked above: a fixed, known identifier
    try:
        _, krows = adapter.run(
            "SELECT kpi_id, model, label, definition, grain, value_columns, owner, source_tier, source_ref, "
            f"certified_by, certified_at, git_commit FROM {schema}.{REGISTRY} ORDER BY kpi_id",
            timeout_s=10, row_cap=1000, native=True, role=reader)
        _, grows = adapter.run(
            f"SELECT kpi_id, missing, typical_sources, next_step FROM {schema}.{GAPS} ORDER BY kpi_id",
            timeout_s=10, row_cap=1000, native=True, role=reader)
        _, crows = adapter.run(
            "SELECT table_name, column_name, data_type FROM information_schema.columns "
            f"WHERE table_schema = '{schema}' ORDER BY table_name, ordinal_position",
            timeout_s=10, row_cap=100000, native=True, role=reader)
    except QueryError as error:
        raise CertifiedError(f"cannot read the certified registry for {role}: {error}") from None
    columns: dict[str, dict[str, str]] = {}
    for table, column, data_type in crows:
        columns.setdefault(str(table).lower(), {})[str(column).lower()] = str(data_type)
    kpis: dict[str, CertifiedKpi] = {}
    for kid, model, label, definition, grain, values, owner, tier, ref, by, at, commit in krows:
        model = str(model).lower()
        if model not in columns:  # registered but not served to this role: not answerable
            continue
        kpis[str(kid)] = CertifiedKpi(
            kpi_id=str(kid), model=model, label=label or str(kid), definition=definition or "",
            grain=str(grain or ""), value_columns=tuple(str(v).lower() for v in (values or [])), owner=owner,
            source_tier=tier, source_ref=ref, certified_by=by, certified_at=at, git_commit=commit,
            columns=tuple(columns[model]))
    gaps = {str(k): Gap(str(k), tuple(m or []), tuple(t or []), n or "") for k, m, t, n in grows}
    types = {k.model: columns[k.model] for k in kpis.values()}
    return Registry(role=role, schema=schema, kpis=kpis, gaps=gaps, types=types)


def certified_policy(registry: Registry, access_path: Path | None = None) -> Policy:
    """The validator policy for the certified path: the allowlist is exactly the certified models."""
    access = yaml.safe_load(Path(access_path or DEFAULT_ACCESS).read_text(encoding="utf-8")) or {}
    spec = (access.get("roles") or {}).get(registry.role) or {}
    limits = access.get("limits") or {}
    return Policy(
        role=registry.role,
        pii_mode=spec.get("pii") or "aggregate_only",
        grants=frozenset(),
        models=tuple(sorted(registry.types)),
        schema={m: dict(cols) for m, cols in registry.types.items()},
        pii={},  # KPI tables are aggregates; the serving views already mask any PII
        default_limit=int(limits.get("default_limit", 100)),
        row_cap=int(limits.get("row_cap", 1000)),
        timeout_s=float(limits.get("timeout_s", 10)),
        mask_value=str(access.get("mask_value", "***")),
    )


def validate(sql_text: str, policy: Policy) -> validator.ValidationResult:
    """The ask validator in the Postgres dialect with the certified policy (not the access.yaml one)."""
    checks = validator._Checks(validator.POSTGRES)
    try:
        return validator._validate(sql_text, policy, checks)
    except validator._Reject:
        return validator._fail(checks)


# --------------------------------------------------------------------------- SQL builder


class Unanswerable(ValueError):
    """The reply cannot be expressed against the certified KPI; the message says why."""


def _month_start(value: str | None) -> dt.date:
    m = _MONTH.match(value or "")
    if not m:
        raise Unanswerable(f"period {value!r} is not a month (YYYY-MM)")
    return dt.date(int(m.group(1)), int(m.group(2)), 1)


def _year(value: str | None) -> int:
    m = _YEAR.match(value or "")
    if not m:
        raise Unanswerable(f"period {value!r} is not a year (YYYY)")
    return int(m.group(1))


def _q(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def is_additive(kpi: CertifiedKpi) -> bool:
    return kpi.kpi_id in ADDITIVE_KPIS


def _single_row(kpi: CertifiedKpi, period: Period) -> bool:
    return period.kind in ("month", "cohort") or kpi.grain == "total"


def wants_series(kpi: CertifiedKpi, reply: CertifiedReply) -> bool:
    """A ratio KPI asked as one value (or a sum) over a period with several rows: answered with per-period values."""
    period = reply.period or Period(kind="all")
    return (not is_additive(kpi) and reply.pick in ("value", "sum") and not _single_row(kpi, period)
            and GRAIN_COLUMNS.get(kpi.grain) is not None)


def drop_irrelevant_filters(kpi: CertifiedKpi, reply: CertifiedReply) -> tuple[CertifiedReply, list[str]]:
    """The reply without filters ``kpi`` has no column for, and one note per dropped filter."""
    notes: list[str] = []
    if reply.months_since_first is not None and not kpi.has_msf:
        notes.append(f"The filter {MSF}={reply.months_since_first} does not apply to {kpi.kpi_id} "
                     f"(it has no {MSF} column) and was ignored.")
        reply = reply.model_copy(update={"months_since_first": None})
    return reply, notes


def build_sql(kpi: CertifiedKpi, schema: str, reply: CertifiedReply) -> tuple[str, str]:
    """``(sql, value_column)`` for the reply against ``kpi``'s own table; ``Unanswerable`` when it cannot be.

    A ratio KPI over a period with several rows (``wants_series``) reads every period's value in grain order.
    """
    column = (reply.value_column or "").lower() or None
    if column is None and len(kpi.value_columns) == 1:
        column = kpi.value_columns[0]
    if column not in kpi.value_columns:
        raise Unanswerable(f"{reply.value_column!r} is not a value column of {kpi.kpi_id}")
    period = reply.period or Period(kind="all")
    if period.kind not in KINDS.get(kpi.grain, set()):
        raise Unanswerable(f"{kpi.kpi_id} has grain {kpi.grain}; a {period.kind} period cannot be expressed")
    grain_col = GRAIN_COLUMNS.get(kpi.grain)
    # Filters are (expression, literal) pairs, combined as one row comparison: the validator's Postgres function
    # allowlist sees sqlglot's AND/OR nodes as functions, so the builder never needs them.
    keys: list[tuple[str, str]] = []
    if period.kind in ("month", "cohort"):
        start = _month_start(period.value)
        keys.append((f"TO_CHAR({_q(grain_col)}, 'YYYY-MM')", f"'{start.strftime('%Y-%m')}'"))
    elif period.kind == "year":
        keys.append((f"EXTRACT(YEAR FROM {_q(grain_col)})", str(_year(period.value))))
    if reply.months_since_first is not None:
        if not kpi.has_msf:
            raise Unanswerable(f"{kpi.kpi_id} has no {MSF} column")
        keys.append((_q(MSF), str(int(reply.months_since_first))))
    elif kpi.has_msf:
        raise Unanswerable(f"{kpi.kpi_id} needs {MSF} (which month after the cohort month)")
    series = wants_series(kpi, reply)
    if reply.pick == "value" and not series and not _single_row(kpi, period):
        raise Unanswerable(f"a {period.kind} period of {kpi.kpi_id} has many rows; pick max or sum")
    if reply.pick != "value" and grain_col is None:
        raise Unanswerable(f"{kpi.kpi_id} is a single total; there is nothing to {reply.pick}")
    table = f"{_q(schema)}.{_q(kpi.model)}"
    col = _q(column)
    if len(keys) == 1:
        cond = f" WHERE {keys[0][0]} = {keys[0][1]}"
    elif keys:
        cond = f" WHERE ({', '.join(k for k, _ in keys)}) = ({', '.join(v for _, v in keys)})"
    else:
        cond = ""
    if series:
        g = _q(grain_col)
        return (f"SELECT {g} AS grain_value, {col} AS kpi_value FROM {table}{cond} ORDER BY {g} LIMIT {SERIES_CAP}",
                column)
    if reply.pick == "sum":
        return f"SELECT SUM({col}) AS kpi_value, COUNT({col}) AS periods FROM {table}{cond}", column
    head = f"{_q(grain_col)} AS grain_value, " if grain_col else ""
    if reply.pick == "max":
        return f"SELECT {head}{col} AS kpi_value FROM {table}{cond} ORDER BY {col} DESC NULLS LAST LIMIT 1", column
    return f"SELECT {head}{col} AS kpi_value FROM {table}{cond} LIMIT 2", column


# --------------------------------------------------------------------------- model call


def render_prompt(question: str, registry: Registry, as_of: str | None = None) -> str:
    kpis = []
    for k in registry.kpis.values():
        extra = f"; has {MSF}" if k.has_msf else ""
        kpis.append(f"- {k.kpi_id}: {k.label}. grain: {k.grain}. value columns: {', '.join(k.value_columns)}"
                    f"{extra}. {k.definition}")
    gaps = [f"- {g.kpi_id}: missing {', '.join(g.missing) or 'data'}" for g in registry.gaps.values()]
    text = PROMPT_PATH.read_text(encoding="utf-8")
    text = text.replace("{certified}", "\n".join(kpis) or "(none)").replace("{gaps}", "\n".join(gaps) or "(none)")
    text = text.replace("{as_of}", as_of or "unknown")
    return text.replace("{question}", question)


def _parse(text: str) -> CertifiedReply | None:
    body = _FENCE.sub("", text.strip()).strip()
    start, end = body.find("{"), body.rfind("}")
    if start < 0 or end <= start:
        return None
    try:
        return CertifiedReply.model_validate(json.loads(body[start : end + 1]))
    except (json.JSONDecodeError, pydantic.ValidationError):
        return None


def _text_of(content: Any) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content or "")


def choose(llm: Any, prompt: str) -> CertifiedReply | None:
    """One structured call; None when the reply does not fit ``CertifiedReply``."""
    if hasattr(llm, "with_structured_output"):
        reply = llm.with_structured_output(CertifiedReply, include_raw=True).invoke(prompt)
        parsed = reply.get("parsed")
        if parsed is None and reply.get("raw") is not None:
            parsed = _parse(_text_of(reply["raw"].content))
        return parsed if isinstance(parsed, CertifiedReply) else None
    return _parse(_text_of(llm.invoke(prompt).content))


def make_llm(spec: str | None) -> Any:
    """``openrouter``/unset -> the real chat model (built lazily), ``fake`` or ``fake:SCRIPT.json`` -> FakeLLM."""
    from governor.ask.llm_testing import FakeLLM

    spec = (spec or "openrouter").strip()
    if spec == "openrouter":
        return None
    if spec == "fake":
        return FakeLLM()
    if spec.startswith("fake:"):
        script = json.loads(Path(spec.split(":", 1)[1]).read_text(encoding="utf-8"))
        replies = script.get("certified") if isinstance(script, dict) else None
        return FakeLLM([str(r) if isinstance(r, str) else json.dumps(r) for r in replies or []])
    raise ValueError("--llm must be openrouter, fake or fake:SCRIPT.json")


def _as_of() -> str | None:
    try:
        return paths.as_of().date().isoformat()
    except (FileNotFoundError, ValueError):
        return None


# --------------------------------------------------------------------------- answer text


def format_number(value: float) -> str:
    if value == int(value) and abs(value) < 1e15:
        return f"{int(value):,}"
    if abs(value) >= 100:
        return f"{value:,.2f}"
    return f"{value:.4f}".rstrip("0").rstrip(".")


def _period_label(value: Any) -> str:
    if isinstance(value, (dt.date, dt.datetime)):
        return value.strftime("%Y-%m")
    return str(value)


def _describe_period(kpi: CertifiedKpi, reply: CertifiedReply) -> str:
    p = reply.period or Period(kind="all")
    if p.kind == "month":
        text = f"in {p.value}"
    elif p.kind == "cohort":
        text = f"for the {p.value} cohort"
    elif p.kind == "year":
        text = f"in {p.value}"
    else:
        text = "over all data"
    if reply.months_since_first is not None:
        text += f", {reply.months_since_first} months after the first order"
    return text


def _cite_text(kpi: CertifiedKpi) -> str:
    at = kpi.certified_at
    when = at.date().isoformat() if isinstance(at, dt.datetime) else str(at)
    src = f"{kpi.source_tier} source {kpi.source_ref}" if kpi.source_ref else f"{kpi.source_tier} source"
    return (f"Source: certified KPI {kpi.kpi_id} ({kpi.label}), owner {kpi.owner}, {src}; "
            f"certified by {kpi.certified_by} on {when}.")


def _gap_text(kid: str, gap: Gap | None) -> str:
    if gap is None:
        return f"{kid} is in the KPI catalogue but is not certified in this build, so it cannot be answered yet."
    missing = ", ".join(gap.missing) or "required data"
    text = f"{kid} is not available: this build is missing {missing}."
    if gap.typical_sources:
        text += f" Typical sources: {', '.join(gap.typical_sources)}."
    if gap.next_step:
        text += f" Next step: {gap.next_step}"
    return text


def _catalogue_ids(kpis_path: Path | None) -> set[str]:
    from governor.core.catalogue import load_kpis

    try:
        return {k.id for k in load_kpis(kpis_path or DEFAULT_KPIS).kpis}
    except Exception:  # noqa: BLE001 - a broken catalogue only loses the not-certified wording
        return set()


def _unanswerable(text: str, kpi_id: str | None = None) -> CertifiedAnswer:
    return CertifiedAnswer(outcome="unanswerable", text=text, kpi_id=kpi_id)


# --------------------------------------------------------------------------- the path


def answer(
    question: str,
    role: str,
    llm: Any = None,
    adapter: Any = None,
    *,
    access_path: Path | None = None,
    kpis_path: Path | None = None,
) -> CertifiedAnswer:
    """Answer ``question`` for ``role`` from the certified KPIs only."""
    reader_role(role)
    adapter = adapter or default_adapter()
    registry = read_registry(adapter, role)
    if llm is None:
        from governor.core.llm import get_chat_model

        llm = get_chat_model(temperature=0)
    reply = choose(llm, render_prompt(question, registry, _as_of()))
    if reply is None:
        return _unanswerable("The question could not be matched to a certified KPI.")
    return answer_reply(reply, role, adapter, access_path=access_path, kpis_path=kpis_path, registry=registry)


def answer_reply(
    reply: CertifiedReply,
    role: str,
    adapter: Any = None,
    *,
    access_path: Path | None = None,
    kpis_path: Path | None = None,
    registry: Registry | None = None,
) -> CertifiedAnswer:
    """The certified path after the KPI choice: registry lookup, gap text, SQL built in code, validated, run as the
    role's reader, answer text written in Python. ``registry`` skips the registry read when the caller has it."""
    reader = reader_role(role)
    adapter = adapter or default_adapter()
    if registry is None:
        registry = read_registry(adapter, role)
    if reply.category == "person_level":
        return CertifiedAnswer(outcome="refused", text="Requests about individual people or records are refused; "
                               "certified KPIs are aggregates only.")
    if reply.category == "out_of_scope":
        return _unanswerable("No certified KPI covers this question.")
    kid = reply.kpi_id
    if not kid:
        return _unanswerable("No certified KPI covers this question.")
    kpi = registry.kpis.get(kid)
    if kpi is None:
        if kid in registry.gaps or kid in _catalogue_ids(kpis_path):
            return CertifiedAnswer(outcome="not_available", text=_gap_text(kid, registry.gaps.get(kid)), kpi_id=kid)
        return _unanswerable("No certified KPI covers this question.")
    reply, notes = drop_irrelevant_filters(kpi, reply)
    series = wants_series(kpi, reply)
    try:
        sql_text, column = build_sql(kpi, registry.schema, reply)
    except Unanswerable as why:
        return _unanswerable(f"The certified KPI {kid} cannot answer this: {why}.", kid)
    policy = certified_policy(registry, access_path)
    checked = validate(sql_text, policy)
    if not checked.ok:
        return _unanswerable(f"The query for {kid} was refused by the validator: {'; '.join(checked.reasons)}", kid)
    try:
        _, rows = adapter.run(checked.sql, timeout_s=policy.timeout_s, row_cap=policy.row_cap, native=True,
                              role=reader)
    except QueryError as error:
        raise CertifiedError(f"the certified query for {kid} failed: {error}") from None
    citation = kpi.citation()
    period = _describe_period(kpi, reply)
    value: float | None
    if series:
        points = [(_period_label(g), float(v)) for g, v in rows if isinstance(v, (int, float, Decimal))]
        if not points:
            return CertifiedAnswer(outcome="unanswerable", text=f"The certified table {kpi.model} has no values "
                                   f"{period}.", kpi_id=kid, sql=checked.sql, citation=citation)
        unit = "cohort month" if kpi.grain == "cohort_month" else "month"
        listed = "; ".join(f"{label} {format_number(v)}" for label, v in points)
        text = (f"{kpi.label} ({column}) {period}, per {unit}: {listed}. There is no single figure for the period "
                f"because {kid} is a ratio, not an amount: it cannot be summed, and an average of the {unit} values "
                f"would ignore how much each {unit} contributes.")
        value = None
    elif reply.pick == "sum":
        raw, count = (rows[0] if rows else (None, 0))
        if raw is None or not count:
            return CertifiedAnswer(outcome="unanswerable", text=f"The certified table {kpi.model} has no rows "
                                   f"{period}.", kpi_id=kid, sql=checked.sql, citation=citation)
        value = float(raw)
        text = f"{kpi.label} ({column}) summed {period} over {count} periods is {format_number(value)}."
    else:
        if not rows or rows[0][-1] is None:
            return CertifiedAnswer(outcome="unanswerable", text=f"The certified table {kpi.model} has no value "
                                   f"{period}.", kpi_id=kid, sql=checked.sql, citation=citation)
        if reply.pick == "value" and len(rows) > 1:
            return CertifiedAnswer(outcome="unanswerable", text=f"The certified table {kpi.model} has more than "
                                   f"one row {period}.", kpi_id=kid, sql=checked.sql, citation=citation)
        value = float(rows[0][-1]) if isinstance(rows[0][-1], (int, float, Decimal)) else None
        if value is None:
            return _unanswerable(f"{column} of {kid} is not a number.", kid)
        if reply.pick == "max":
            text = (f"The highest {kpi.label} ({column}) {period} was {format_number(value)}, "
                    f"in {_period_label(rows[0][0])}.")
        else:
            text = f"{kpi.label} ({column}) {period} was {format_number(value)}."
    text = " ".join([text, *notes, _cite_text(kpi)])
    return CertifiedAnswer(outcome="answer", text=text, value=value, kpi_id=kid,
                           sql=checked.sql, citation=citation)


# --------------------------------------------------------------------------- CLI


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m governor.ask.certified", description=__doc__.splitlines()[0])
    parser.add_argument("question")
    parser.add_argument("--role", required=True, choices=sorted(READER_ROLES))
    parser.add_argument("--llm", default="openrouter", help="openrouter, fake or fake:SCRIPT.json")
    args = parser.parse_args(argv)
    try:
        result = answer(args.question, args.role, make_llm(args.llm))
    except (CertifiedError, ValueError, OSError) as error:
        print(json.dumps({"outcome": "error", "text": str(error)[:500]}))
        return 1
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
