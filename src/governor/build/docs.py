"""Column descriptions from lineage (batch2c.md section 16).

:func:`describe` returns ``model -> column -> description`` for every silver model and every built gold model of the
approved design, deterministic first:

1. Gold columns: the KPI's catalogue definition with the column's role (grain, the KPI value, a companion value).
2. Staging columns: a sentence from the lineage and the profile: source column and raw table, the expression applied
   (``cast from text``, ``empty text as null``, ``renamed from``), type, key, null-rate band (never values), and
   ``personal data, hashed for analysts`` when the column is PII or the policy tags its source.
3. Intermediate columns with the same name as a column of a ref inherit that ref's description.
4. Columns still empty: one write-model call per model (``prompts/describe.md``) with the model description, the
   columns' lineage, profile counts, the design assumptions and the descriptions of its refs; never data values
   (profile ``min`` / ``max`` are left out). Replies longer than :data:`MAX_CHARS` are trimmed at a word.

A description the approved design already gives is kept: the lineage sentence follows it for staging columns.
:func:`coverage` counts the described columns of the yml files written into a target (``docs_coverage``).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import sqlglot
import yaml
from sqlglot import exp
from sqlglot.errors import SqlglotError

from governor.build import gold, silver
from governor.build.llm import BuildLLM, LLMOutputError
from governor.build.models import Proposal, SilverColumn, SilverModel
from governor.core.catalogue import Kpi, KpiCatalogue

PROMPTS = Path(__file__).resolve().parent / "prompts"
MAX_CHARS = 200
PII_NOTE = "personal data, hashed for analysts"

Docs = dict[str, dict[str, str]]


def _proposal(design: Proposal | dict) -> Proposal:
    return design if isinstance(design, Proposal) else Proposal.model_validate(design)


def trim(text: str, limit: int = MAX_CHARS) -> str:
    """One line, at most ``limit`` characters, cut at a word boundary when longer."""
    text = " ".join(str(text or "").split())
    if len(text) <= limit:
        return text
    cut = text[:limit]
    if text[limit] != " " and " " in cut:
        cut = cut.rsplit(" ", 1)[0]
    return cut.rstrip(" ,;:-")


def _sentence(text: str) -> str:
    text = text.strip()
    return text[:1].upper() + text[1:] if text else text


# --------------------------------------------------------------------------- rule 1: gold


def gold_columns(kpi: Kpi, mapping: dict[str, str]) -> list[str]:
    """Output columns of the rendered KPI model (the final SELECT of the catalogue template)."""
    try:
        tree = sqlglot.parse_one(gold._plain(gold.gold_sql(kpi, mapping)), read="postgres")
    except (SqlglotError, ValueError):
        return [gold.GRAIN_COLUMN[kpi.grain]] if kpi.grain in gold.GRAIN_COLUMN else []
    return [s.alias_or_name for s in getattr(tree, "selects", []) or [] if s.alias_or_name]


def gold_docs(design: Proposal | dict, catalogue: KpiCatalogue) -> Docs:
    """Rule 1 for every built KPI model."""
    out: Docs = {}
    for k in gold.built_kpis(design):
        kpi = catalogue.get(k.id)
        definition = " ".join(kpi.definition.split())
        grain = kpi.grain.replace("_", " ")
        cols: dict[str, str] = {}
        for name in gold_columns(kpi, k.mapping):
            if gold.GRAIN_COLUMN.get(kpi.grain) == name:
                cols[name] = f"The {grain} (grain of {kpi.label})."
            elif name == kpi.id:
                cols[name] = f"{kpi.label} per {grain}: {definition}"
            else:
                cols[name] = f"{_sentence(name.replace('_', ' '))}, a companion value of {kpi.label} per {grain}: {definition}"
        out[gold.model_name(k.id)] = cols
    return out


# --------------------------------------------------------------------------- rule 2: staging


def null_band(rate: float | None) -> str | None:
    if rate is None:
        return None
    if rate <= 0:
        return "never null"
    if rate < 0.01:
        return "rarely null (under 1%)"
    if rate < 0.10:
        return "sometimes null (1 to 10%)"
    if rate < 0.50:
        return "often null (10 to 50%)"
    return "mostly null (over 50%)"


def _sources(expr: str | None) -> tuple[list[str], exp.Expression | None]:
    try:
        tree = sqlglot.parse_one(expr or "", read="postgres")
    except (SqlglotError, ValueError):
        return [], None
    if tree is None:
        return [], None
    return list(dict.fromkeys(c.name for c in tree.find_all(exp.Column))), tree


def _expression(col: SilverColumn, sources: list[str], tree: exp.Expression | None) -> str:
    if tree is None:
        return "computed in staging"
    if isinstance(tree, exp.Column):
        return "copied as is" if tree.name == col.name else f"renamed from {tree.name}"
    parts = []
    if any(True for _ in tree.find_all(exp.Cast, exp.TryCast)):
        parts.append(f"cast from text to {col.type}")
    if any(isinstance(n.expression, exp.Literal) and n.expression.this == "" for n in tree.find_all(exp.Nullif)):
        parts.append("empty text as null")
    if not parts:
        parts.append("computed from " + (", ".join(sources) if sources else "an expression"))
    return ", ".join(parts)


def _policy_tagged(policy: dict | None, table: str | None, names: list[str]) -> bool:
    policy = policy or {}
    return any(n in policy or f"{table}.{n}" in policy for n in names)


def _profile_table(profile: dict | None, table: str | None) -> dict | None:
    for t in (profile or {}).get("tables") or []:
        if t.get("name") == table:
            return t
    return None


def staging_doc(m: SilverModel, c: SilverColumn, profile: dict | None, policy: dict | None) -> str:
    """Rule 2: one sentence from lineage and profile for a staging column (no data values)."""
    sources, tree = _sources(c.expr)
    table = m.source_table or "?"
    origin = ", ".join(f"raw.{table}.{s}" for s in sources) or f"raw.{table}"
    bits = [f"{_sentence(c.type)} from {origin}, {_expression(c, sources, tree)}"]
    if m.primary_key == [c.name]:
        bits.append("primary key")
    elif c.name in m.primary_key:
        bits.append(f"part of the primary key ({', '.join(m.primary_key)})")
    prof = _profile_table(profile, m.source_table)
    if prof and len(sources) == 1:
        pc = next((x for x in prof.get("columns") or [] if x.get("name") == sources[0]), None)
        band = null_band(pc.get("null_rate")) if pc else None
        if band:
            bits.append(band)
    if c.pii or _policy_tagged(policy, m.source_table, [c.name, *sources]):
        bits.append(PII_NOTE)
    lineage = "; ".join(bits) + "."
    lead = " ".join(c.description.split()).rstrip(".")
    return f"{_sentence(lead)}. {lineage}" if lead else lineage


# --------------------------------------------------------------------------- rules 1 to 3


def deterministic(design: Proposal | dict, profile: dict | None, catalogue: KpiCatalogue | None,
                  policy: dict | None) -> Docs:
    """Rules 1 to 3; a column no rule describes is ``""``."""
    prop = _proposal(design)
    out: Docs = {}

    def silver_docs(m: SilverModel, seen: tuple[str, ...] = ()) -> dict[str, str]:
        if m.name in out:
            return out[m.name]
        cols: dict[str, str] = {}
        for c in m.columns:
            if m.folder == silver.STAGING:
                cols[c.name] = staging_doc(m, c, profile, policy)
            elif c.description.strip():
                cols[c.name] = " ".join(c.description.split())
            else:
                cols[c.name] = ""
                for r in m.refs:
                    rm = prop.model(r)
                    if rm is None or r in seen or c.name not in rm.column_names():
                        continue
                    inherited = silver_docs(rm, (*seen, m.name)).get(c.name, "")
                    if inherited:
                        cols[c.name] = inherited
                        break
        out[m.name] = cols
        return cols

    for m in prop.silver_models:
        silver_docs(m)
    if catalogue is not None:
        out.update(gold_docs(prop, catalogue))
    return out


# --------------------------------------------------------------------------- rule 4: the write model


def _render(parts: dict[str, str]) -> str:
    text = (PROMPTS / "describe.md").read_text(encoding="utf-8")
    for key, value in parts.items():
        text = text.replace("{{" + key + "}}", value)
    return text.rstrip() + "\n"


def _cell(text: str) -> str:
    return " ".join(str(text or "").split()).replace("|", "/")


def _profile_lines(m: SilverModel, prop: Proposal, profile: dict | None) -> str:
    """Rows of the raw tables behind ``m`` and, for staging, each column's null rate and distinct count."""
    tables: list[str] = []

    def walk(model: SilverModel, seen: set[str]) -> None:
        if model.name in seen:
            return
        seen.add(model.name)
        if model.source_table and model.source_table not in tables:
            tables.append(model.source_table)
        for r in model.refs:
            rm = prop.model(r)
            if rm is not None:
                walk(rm, seen)

    walk(m, set())
    lines = []
    for t in tables:
        prof = _profile_table(profile, t)
        if prof is None:
            continue
        lines.append(f"- raw.{t}: {int(prof.get('rows') or 0)} rows")
        if m.source_table == t:
            for pc in prof.get("columns") or []:
                lines.append(f"  - {pc.get('name')}: null rate {float(pc.get('null_rate') or 0):.3f}, "
                             f"{int(pc.get('distinct') or 0)} distinct")
    return "\n".join(lines) or "(none)"


def describe_prompt(m: SilverModel | str, design: Proposal | dict, profile: dict | None, docs: Docs,
                    catalogue: KpiCatalogue | None = None) -> str:
    """The rule 4 prompt for one model: evidence only, never data values."""
    prop = _proposal(design)
    name = m if isinstance(m, str) else m.name
    model = prop.model(name)
    have = docs.get(name, {})
    if model is not None:
        rows = [f"| {c.name} | {c.type} | {'yes' if c.pii else 'no'} | "
                f"{_cell(c.expr) if c.expr else '(written from the refs)'} | {_cell(have.get(c.name, ''))} |"
                for c in model.columns]
        description, folder, key = model.description or "(none)", model.folder, ", ".join(model.primary_key)
        refs = []
        for r in model.refs:
            rd = docs.get(r, {})
            rm = prop.model(r)
            refs.append(f"### {r}\n\n{(rm.description if rm else '') or '(none)'}\n\n| column | description |\n|---|---|\n"
                        + "\n".join(f"| {c} | {_cell(d)} |" for c, d in rd.items()))
        prof = _profile_lines(model, prop, profile)
    else:  # a gold model
        kpi_id = name[4:] if name.startswith("kpi_") else name
        kpi = catalogue.get(kpi_id) if catalogue is not None else None
        rows = [f"| {c} | | no | (catalogue template) | {_cell(d)} |" for c, d in have.items()]
        description = " ".join(kpi.definition.split()) if kpi else "(none)"
        folder, key, refs, prof = "marts", "(none)", [], "(none)"
    empty = [c for c, d in have.items() if not d.strip()]
    return _render({
        "model": name, "folder": folder, "description": description, "primary_key": key or "(none)",
        "columns": "| column | type | personal data | lineage | description |\n|---|---|---|---|---|\n" + "\n".join(rows),
        "empty": "\n".join(f"- {c}" for c in empty) or "(none)",
        "refs": "\n\n".join(refs) or "(none)",
        "profile": prof,
        "assumptions": "\n".join(f"- {a}" for a in prop.assumptions) or "(none)",
    })


def parse_reply(text: str) -> dict[str, str]:
    body = (text or "").strip()
    fence = re.search(r"```[A-Za-z]*\s*\n(.*?)```", body, re.S)
    if fence:
        body = fence.group(1).strip()
    try:
        data = json.loads(body)
    except ValueError as exc:
        raise LLMOutputError(f"describe reply is not JSON: {exc}") from None
    if not isinstance(data, dict):
        raise LLMOutputError("describe reply is not a JSON object of column to description")
    return {str(k): str(v) for k, v in data.items() if isinstance(v, (str, int, float))}


def describe(design: Proposal | dict, profile: dict | None, catalogue: KpiCatalogue | None, policy: dict | None,
             llm: BuildLLM | None) -> Docs:
    """``model -> column -> description``: rules 1 to 3, then one write-model call per model with empty columns."""
    prop = _proposal(design)
    docs = deterministic(prop, profile, catalogue, policy)
    if llm is None:
        return docs
    for name, cols in docs.items():
        empty = [c for c, d in cols.items() if not d.strip()]
        if not empty:
            continue
        try:
            reply = parse_reply(llm.text("describe", describe_prompt(name, prop, profile, docs, catalogue),
                                         key=name, role="write"))
        except LLMOutputError:
            continue  # stays empty; docs_coverage shows it
        for c in empty:
            if str(reply.get(c) or "").strip():
                cols[c] = trim(reply[c])
    return docs


# --------------------------------------------------------------------------- coverage


def yml_files(target: str | Path) -> list[Path]:
    models = Path(target) / "models"
    files = [models / silver.STAGING / "_staging.yml", models / silver.INTERMEDIATE / "_intermediate.yml"]
    files += sorted((models / gold.MARTS).glob("*/_*.yml")) if (models / gold.MARTS).is_dir() else []
    return [f for f in files if f.is_file()]


def coverage(target: str | Path) -> dict[str, Any]:
    """Share of the columns in the generated yml files that have a description."""
    total = described = 0
    for f in yml_files(target):
        doc = yaml.safe_load(f.read_text(encoding="utf-8")) or {}
        for m in doc.get("models") or [] if isinstance(doc, dict) else []:
            for c in (m or {}).get("columns") or []:
                if isinstance(c, dict):
                    total += 1
                    described += bool(str(c.get("description") or "").strip())
    return {"columns": total, "described": described, "share": round(described / total, 4) if total else 1.0}


__all__ = ["MAX_CHARS", "PII_NOTE", "coverage", "describe", "describe_prompt", "deterministic", "gold_columns",
           "gold_docs", "null_band", "parse_reply", "staging_doc", "trim"]
