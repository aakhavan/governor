"""The design proposal: prompt it, validate it, render the design report (batch2.md sections 6 and 7).

- :func:`propose` makes one structured call to the plan model with ``prompts/propose.md``. The prompt carries the
  profile without any data value (no min or max at all; PII columns as name and counts only), the blueprint rules,
  the catalogue (ids, definitions, relations, inputs, requires; not the templates), the approved decisions and, on a
  repair or after a rejection, the previous proposal with its findings or the reviewer's note.
- :func:`validate` is code: it returns :class:`Finding` objects with the section 6 codes. Three extra codes cover
  what the table does not: ``PROPOSAL_UNPARSEABLE`` (the reply is not a proposal; raised by the graph),
  ``EXPR_UNPARSEABLE`` (an ``expr`` or boolean mapping is not one SQL expression) and ``KPI_DUPLICATE``.
  ``KEY_NOT_UNIQUE`` (batch2c section 19): a staging model's key must contain a candidate key of its source table.
  Before validation (and on every proposal :func:`propose` returns), :func:`normalise_source_tables` turns a
  ``<profile schema>.<table>`` source table into the bare profiled table name (batch2c section 21).
- :func:`render_report` writes the section 7 markdown for the design gate.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError

from governor.build.llm import BuildLLM
from governor.build.models import Finding, Profile, Proposal, ProposalReply, proposal_as_reply
from governor.core.catalogue import ApprovedDecisions, Blueprint, CatalogueError, KpiCatalogue, render

PROMPTS = Path(__file__).resolve().parent / "prompts"
STAGING, INTERMEDIATE = "staging", "intermediate"

CODES = (
    "UNKNOWN_SOURCE_TABLE", "UNKNOWN_SOURCE_COLUMN", "BAD_FOLDER", "DUPLICATE_MODEL", "MISSING_KEY", "PII_UNTAGGED",
    "KPI_UNKNOWN", "KPI_MISSING", "MAPPING_INCOMPLETE", "MAPPING_UNKNOWN_MODEL", "MAPPING_UNKNOWN_COLUMN",
    "DECLINE_WITHOUT_GAP",
    # beyond the section 6 table
    "PROPOSAL_UNPARSEABLE", "EXPR_UNPARSEABLE", "KPI_DUPLICATE",
    # batch2c section 19
    "KEY_NOT_UNIQUE",
)


# --------------------------------------------------------------------------- prompt


def _as_profile(profile: Profile | dict) -> Profile:
    return profile if isinstance(profile, Profile) else Profile.model_validate(profile)


def profile_for_prompt(profile: Profile | dict) -> dict:
    """The profile without data values: no min or max, and PII columns as name and counts only."""
    p = _as_profile(profile)
    tables = []
    for t in p.tables:
        cols = []
        for c in t.columns:
            if c.pii:
                cols.append({"name": c.name, "pii": True, "null_rate": c.null_rate, "distinct": c.distinct})
            else:
                cols.append({"name": c.name, "type": c.inferred_type, "null_rate": c.null_rate, "distinct": c.distinct})
        tables.append({"name": t.name, "rows": t.rows, "candidate_keys": t.candidate_keys, "columns": cols})
    rels = [{"from": r.from_, "to": r.to, "coverage": r.coverage} for r in p.relationships]
    return {"schema": p.schema_, "tables": tables, "relationships": rels}


def catalogue_for_prompt(catalogue: KpiCatalogue) -> list[dict]:
    return [
        {"id": k.id, "label": k.label, "definition": k.definition, "grain": k.grain,
         "relations": {n: r.description for n, r in k.relations.items()},
         "inputs": {n: {"relation": i.relation, "type": i.type, **({"description": i.description} if i.description else {})}
                    for n, i in k.inputs.items()},
         "requires": k.requires, **({"prerequisites": k.prerequisites} if k.prerequisites else {})}
        for k in catalogue.kpis
    ]


def blueprint_for_prompt(blueprint: Blueprint) -> dict:
    return {"layers": {n: {"description": layer.description, "dbt_folders": layer.dbt}
                       for n, layer in blueprint.layers.items()},
            "rules": [{"id": r.id, "severity": r.severity, "text": r.text} for r in blueprint.rules],
            "exceptions": [e.model_dump() for e in blueprint.exceptions]}


def approved_for_prompt(approved: ApprovedDecisions | list | None) -> list[dict]:
    if approved is None:
        return []
    decisions = approved.decisions if isinstance(approved, ApprovedDecisions) else approved
    return [d.model_dump(mode="json", exclude_none=True) if hasattr(d, "model_dump") else dict(d) for d in decisions]


def _dump(value: Any) -> str:
    return "```json\n" + json.dumps(value, indent=1, ensure_ascii=False) + "\n```"


def build_prompt(profile, catalogue, blueprint, approved, findings=None, *, previous: Proposal | dict | None = None,
                 note: str | None = None) -> str:
    template = (PROMPTS / "propose.md").read_text(encoding="utf-8")
    extra: list[str] = []
    if findings:
        extra.append("## Findings on your previous proposal\n\nFix every one of these:\n\n"
                     + "\n".join(f"- {_finding(f).line()}" for f in findings))
    if note:
        extra.append("## Reviewer's note (the design was rejected)\n\n" + note.strip())
    if previous is not None:
        prev = previous.to_json_dict() if isinstance(previous, Proposal) else previous
        extra.append("## Your previous proposal\n\n" + _dump(proposal_as_reply(prev)))
    parts = {
        "{{profile}}": _dump(profile_for_prompt(profile)),
        "{{blueprint}}": _dump(blueprint_for_prompt(blueprint)),
        "{{catalogue}}": _dump(catalogue_for_prompt(catalogue)),
        "{{approved}}": _dump(approved_for_prompt(approved)),
        "{{repair}}": "\n\n".join(extra),
    }
    for key, value in parts.items():
        template = template.replace(key, value)
    return template.rstrip() + "\n"


def propose(profile, catalogue: KpiCatalogue, blueprint: Blueprint, approved, llm: BuildLLM,
            findings: list[Finding] | None = None, *, previous: Proposal | dict | None = None,
            note: str | None = None) -> Proposal:
    """One structured call to the plan model. Raises ``LLMOutputError`` when the reply is not a proposal.

    The model answers in :class:`ProposalReply` (each KPI mapping as ``mapping_pairs``, batch2b section 11); the
    pairs become the ``mapping`` dict here, before validation."""
    prompt = build_prompt(profile, catalogue, blueprint, approved, findings, previous=previous, note=note)
    return normalise_source_tables(llm.structured("propose", prompt, ProposalReply, role="plan").to_proposal(), profile)


# --------------------------------------------------------------------------- validation


def _bare_table(source_table: str | None, schema: str, tables: set[str]) -> str | None:
    """``<profile schema>.<table>`` -> ``<table>`` when ``<table>`` is profiled; anything else unchanged."""
    if not source_table or source_table in tables:
        return source_table
    prefix, sep, rest = source_table.partition(".")
    if sep and schema and prefix.strip('"').lower() == schema.lower() and rest.strip('"') in tables:
        return rest.strip('"')
    return source_table


def normalise_source_tables(proposal: Proposal | dict, profile: Profile | dict) -> Proposal:
    """Staging ``source_table`` written as ``<profile schema>.<table>`` (``raw.olist_orders_dataset``) becomes the
    bare profiled table name (batch2c section 21). Code, not a repair: any other unknown name stays and validation
    reports it as ``UNKNOWN_SOURCE_TABLE``."""
    prop = proposal if isinstance(proposal, Proposal) else Proposal.model_validate(proposal)
    prof = _as_profile(profile)
    tables = {t.name for t in prof.tables}
    models = []
    changed = False
    for m in prop.silver_models:
        bare = _bare_table(m.source_table, prof.schema_, tables)
        if bare != m.source_table:
            m, changed = m.model_copy(update={"source_table": bare}), True
        models.append(m)
    return prop.model_copy(update={"silver_models": models}) if changed else prop


def _finding(f: Finding | dict) -> Finding:
    return f if isinstance(f, Finding) else Finding.model_validate(f)


def _columns_read(sql: str) -> set[str]:
    """Column names one SQL expression reads. Raises ValueError when it is not exactly one expression."""
    try:
        trees = sqlglot.parse(sql, read="postgres")
    except SqlglotError as exc:
        raise ValueError(f"does not parse ({str(exc).splitlines()[0][:120]})") from None
    trees = [t for t in trees if t is not None]
    if len(trees) != 1:
        raise ValueError("must be one SQL expression")
    tree = trees[0]
    if isinstance(tree, (exp.Query, exp.DDL, exp.DML)) or tree.find(exp.Query) is not None:
        raise ValueError("must be an expression, not a statement or subquery")
    return {c.name for c in tree.find_all(exp.Column) if c.name}


def _has(name: str, columns: set[str]) -> bool:
    return name in columns or name.lower() in columns


def _key_source(expr: str | None, name: str) -> str | None:
    """The raw column a staging key column reads: ``expr`` null means the column of the same name; a bare column or
    a cast of one, or ``NULLIF(<col>, '')``, maps to that column. Anything else (computed, or not one expression) gives None."""
    if not (expr or "").strip():
        return name
    try:
        tree = sqlglot.parse_one(expr, read="postgres")
    except SqlglotError:
        return None
    while True:
        if isinstance(tree, (exp.Paren, exp.Cast)):
            tree = tree.this
        elif isinstance(tree, exp.Nullif) and isinstance(tree.expression, exp.Literal) \
                and tree.expression.is_string and tree.expression.this == "":
            tree = tree.this  # NULLIF(col, '') only turns '' into null, which the key's not-null test catches
        else:
            break
    return tree.name if isinstance(tree, exp.Column) and tree.name else None


def _key_findings(m, table) -> list[tuple[str, str]]:
    """Section 19: a staging key must contain a candidate key of its profiled source table (subject, problem)."""
    have = {c.name for c in table.columns}
    exprs = {c.name: c.expr for c in m.columns}
    out: list[tuple[str, str]] = []
    raw: set[str] = set()
    for k in m.primary_key:
        if k not in exprs:
            return []  # undeclared key column: MISSING_KEY
        src = _key_source(exprs[k], k)
        if src is None:
            out.append((f"{m.name}.{k}", f"key column '{k}' is computed; key a staging model on raw columns"))
            continue
        if not _has(src, have):
            return out  # UNKNOWN_SOURCE_COLUMN reports it
        raw.add(src if src in have else src.lower())
    if out or not m.primary_key:
        return out
    if any(set(ck) <= raw for ck in table.candidate_keys):
        return []
    key = ", ".join(m.primary_key)
    if not table.candidate_keys:
        return [(m.name, f"primary_key [{key}] is not known to be unique: {table.name} has no unique column or "
                         "column pair in the profile; leave it unstaged unless a KPI needs it, or dedupe it in an "
                         "intermediate model")]
    cands = "; ".join("[" + ", ".join(ck) + "]" for ck in table.candidate_keys)
    return [(m.name, f"primary_key [{key}] (raw columns [{', '.join(sorted(raw))}]) contains no candidate key of "
                     f"{table.name} ({table.rows} rows); its candidate keys are {cands}: key on one of them")]


def _is_pii(table: str, column: str, policy: dict[str, str], profiled: set[tuple[str, str]]) -> bool:
    return column in policy or f"{table}.{column}" in policy or (table, column) in profiled


def validate(proposal: Proposal | dict, profile: Profile | dict, catalogue: KpiCatalogue,
             policy: dict[str, str] | None) -> list[Finding]:
    """Every section 6 code that applies, in model then KPI order. Empty means the proposal is valid."""
    prof = _as_profile(profile)
    prop = normalise_source_tables(proposal, prof)
    policy = policy or {}
    out: list[Finding] = []

    def add(code: str, subject: str, problem: str) -> None:
        out.append(Finding(code=code, subject=subject, problem=problem))

    raw_cols = {t.name: {c.name for c in t.columns} for t in prof.tables}
    pii_profiled = {(t.name, c.name) for t in prof.tables for c in t.columns if c.pii}
    names = [m.name for m in prop.silver_models]
    models = {m.name: m for m in prop.silver_models}

    for name in sorted({n for n in names if names.count(n) > 1}):
        add("DUPLICATE_MODEL", name, f"{names.count(name)} silver models are named '{name}'")

    for m in prop.silver_models:
        declared = m.column_names()
        # folders and refs (L1, L3)
        if m.folder == STAGING:
            if not m.source_table:
                add("BAD_FOLDER", m.name, "a staging model needs a source_table")
            if m.refs:
                add("BAD_FOLDER", m.name, f"a staging model reads one raw table and has no refs (has {m.refs})")
        elif m.folder == INTERMEDIATE:
            if m.source_table:
                add("BAD_FOLDER", m.name, f"an intermediate model has no source_table (has '{m.source_table}')")
            if not m.refs:
                add("BAD_FOLDER", m.name, "an intermediate model needs refs to silver models")
        else:
            add("BAD_FOLDER", m.name, f"folder '{m.folder}' is not a silver folder (staging or intermediate)")
        for ref in m.refs:
            if ref == m.name or ref not in models:
                add("BAD_FOLDER", m.name, f"ref '{ref}' is not another silver model")
        # keys (L4)
        if not m.primary_key:
            add("MISSING_KEY", m.name, "no primary_key")
        for k in m.primary_key:
            if k not in declared:
                add("MISSING_KEY", m.name, f"key column '{k}' is not a declared column")
        # staging columns over the raw table
        if m.folder == STAGING and m.source_table:
            if m.source_table not in raw_cols:
                add("UNKNOWN_SOURCE_TABLE", m.name, f"source_table '{m.source_table}' is not in the profile")
            else:
                have = raw_cols[m.source_table]
                for c in m.columns:
                    if not (c.expr or "").strip():
                        add("EXPR_UNPARSEABLE", f"{m.name}.{c.name}", "a staging column needs an expr over the raw table")
                        continue
                    try:
                        read = _columns_read(c.expr)
                    except ValueError as exc:
                        add("EXPR_UNPARSEABLE", f"{m.name}.{c.name}", f"expr {c.expr!r} {exc}")
                        continue
                    for col in sorted(read):
                        if not _has(col, have):
                            add("UNKNOWN_SOURCE_COLUMN", f"{m.name}.{c.name}",
                                f"expr reads '{col}', which {m.source_table} does not have")
                    pii_read = sorted(col for col in read if _has(col, have)
                                      and _is_pii(m.source_table, col if col in have else col.lower(), policy, pii_profiled))
                    if pii_read and not c.pii:
                        add("PII_UNTAGGED", f"{m.name}.{c.name}", f"reads PII column(s) {pii_read} but has pii: false (L6)")
                # keys against the profile's candidate keys (batch2c section 19)
                for subject, problem in _key_findings(m, prof.table(m.source_table)):
                    add("KEY_NOT_UNIQUE", subject, problem)

    # PII passed on by name through intermediate models (L6)
    for m in prop.silver_models:
        if m.folder != INTERMEDIATE:
            continue
        pii_upstream = {c.name for r in m.refs if r in models for c in models[r].columns if c.pii}
        for c in m.columns:
            if c.name in pii_upstream and not c.pii:
                add("PII_UNTAGGED", f"{m.name}.{c.name}", "carries a PII column from its refs but has pii: false (L6)")

    # KPI decisions
    known = {k.id for k in catalogue.kpis}
    ids = [k.id for k in prop.kpis]
    for kid in sorted({i for i in ids if ids.count(i) > 1}):
        add("KPI_DUPLICATE", f"kpi.{kid}", f"{ids.count(kid)} decisions for one KPI")
    for kid in ids:
        if kid not in known:
            add("KPI_UNKNOWN", f"kpi.{kid}", "not in the KPI catalogue")
    for kid in [k.id for k in catalogue.kpis if k.id not in ids]:
        add("KPI_MISSING", f"kpi.{kid}", "the catalogue KPI has no decision")

    for d in prop.kpis:
        subject = f"kpi.{d.id}"
        if d.decision == "decline":
            gap = d.gap
            missing = [f for f in ("missing", "typical_sources", "next_step") if gap is None or not _filled(getattr(gap, f))]
            if not (d.reason or "").strip():
                add("DECLINE_WITHOUT_GAP", subject, "a declined KPI needs a reason")
            if missing:
                add("DECLINE_WITHOUT_GAP", subject, f"the gap needs {', '.join(missing)}")
            continue
        if d.id not in known:
            continue
        kpi = catalogue.get(d.id)
        if not (d.domain or "").strip():
            add("MAPPING_INCOMPLETE", subject, "a built KPI needs a domain (its gold folder)")
        try:
            render(kpi, d.mapping)
        except CatalogueError as exc:
            add("MAPPING_INCOMPLETE", subject, str(exc).removeprefix(f"kpi '{d.id}': "))
        for rel in kpi.relations:
            target = d.mapping.get(rel)
            if target and target not in models:
                add("MAPPING_UNKNOWN_MODEL", subject, f"relation '{rel}' maps to '{target}', which is not a silver model")
        for name, inp in kpi.inputs.items():
            value = (d.mapping.get(name) or "").strip()
            model = models.get(d.mapping.get(inp.relation) or "")
            if not value or model is None:
                continue  # unfilled or unknown relation: reported above
            declared = set(model.column_names())
            if inp.type == "boolean":
                try:
                    read = _columns_read(value)
                except ValueError as exc:
                    add("EXPR_UNPARSEABLE", subject, f"input '{name}' expression {value!r} {exc}")
                    continue
                for col in sorted(c for c in read if c not in declared):
                    add("MAPPING_UNKNOWN_COLUMN", subject,
                        f"input '{name}' reads '{col}', which {model.name} does not declare")
            elif value not in declared:
                add("MAPPING_UNKNOWN_COLUMN", subject, f"input '{name}' maps to '{value}', which {model.name} does not declare")
    return out


def _filled(value: Any) -> bool:
    if isinstance(value, list):
        return any(str(v).strip() for v in value)
    return bool(str(value or "").strip())


# --------------------------------------------------------------------------- report


def _cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_report(proposal: Proposal | dict | None, findings: list[Finding] | list[dict], thread_id: str) -> str:
    """The section 7 design report."""
    prop = proposal if isinstance(proposal, Proposal) or proposal is None else Proposal.model_validate(proposal)
    found = [_finding(f) for f in findings]
    models = prop.silver_models if prop else []
    kpis = prop.kpis if prop else []
    build = [k for k in kpis if k.decision == "build"]
    declined = [k for k in kpis if k.decision == "decline"]
    lines = ["# Design report", ""]
    lines.append(f"{len(models)} silver model(s), {len(build)} KPI(s) to build, {len(declined)} KPI(s) declined"
                 + (f"; {len(found)} validation finding(s), not approvable." if found else "."))
    lines += ["", f"Thread: `{thread_id}`", ""]

    lines += ["## Silver models", ""]
    if models:
        lines += ["| name | folder | from | key | PII columns |", "|---|---|---|---|---|"]
        for m in models:
            src = f"raw.{m.source_table}" if m.source_table else ", ".join(m.refs)
            pii = ", ".join(c.name for c in m.columns if c.pii) or "none"
            lines.append(f"| {_cell(m.name)} | {_cell(m.folder)} | {_cell(src)} | {_cell(', '.join(m.primary_key))} | {_cell(pii)} |")
    else:
        lines.append("No silver models proposed.")
    lines.append("")

    lines += ["## KPIs", ""]
    if kpis:
        lines += ["| id | decision | domain | mapping or reason |", "|---|---|---|---|"]
        for k in kpis:
            detail = ("; ".join(f"{n} → {v}" for n, v in k.mapping.items()) if k.decision == "build"
                      else (k.reason or ""))
            lines.append(f"| {_cell(k.id)} | {k.decision} | {_cell(k.domain or '')} | {_cell(detail)} |")
    else:
        lines.append("No KPI decisions.")
    lines.append("")

    lines += ["## Gap report", ""]
    if declined:
        for k in declined:
            gap = k.gap
            lines += [f"### {k.id}", "",
                      f"- Missing data: {', '.join(gap.missing) if gap and gap.missing else '(not given)'}",
                      f"- Typical sources: {', '.join(gap.typical_sources) if gap and gap.typical_sources else '(not given)'}",
                      f"- Next step: {gap.next_step if gap and gap.next_step else '(not given)'}", ""]
    else:
        lines += ["No KPI declined: no gaps.", ""]

    lines += ["## Assumptions", ""]
    lines += [f"- {a}" for a in (prop.assumptions if prop else [])] or ["None."]
    lines.append("")

    lines += ["## Validation findings", ""]
    if found:
        lines += ["| code | model or KPI | problem |", "|---|---|---|"]
        lines += [f"| {f.code} | {_cell(f.subject)} | {_cell(f.problem)} |" for f in found]
    else:
        lines.append("None: the proposal passed every check.")
    lines.append("")

    lines += ["## Commands", ""]
    if found:
        lines += ["The design is invalid and cannot be approved. Fix the inputs (profile, catalogue, approved decisions) "
                  "and run the build again:", "", "```", "python -m governor.build run --target <dir> --project-name <name>",
                  "```", ""]
    else:
        lines += ["Approve:", "", "```", f"python -m governor.build approve {thread_id} --by <name>", "```", "",
                  "Reject with a note (the plan model proposes once more):", "", "```",
                  f'python -m governor.build reject {thread_id} --note "<what to change>"', "```", ""]
    return "\n".join(lines)
