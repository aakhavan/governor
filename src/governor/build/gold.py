"""Gold (batch2.md section 10): KPI models from catalogue templates, the static blueprint check, the gap report.

- :func:`write_gold`: one ``models/marts/<domain>/kpi_<id>.sql`` per ``build`` KPI of the approved design. The file
  is exactly ``catalogue.render(kpi, mapping)`` with each relation mapped to ``{{ ref('<model>') }}``; nothing is
  added, so L8 can compare it with a fresh render. ``_<domain>.yml`` carries the KPI definition as description,
  ``meta`` (``kpi_id``, ``owner``, ``source_tier``, ``source_ref``, ``template_sha256``, ``rendered_sha256``) and
  ``not_null`` on the grain column (``month`` or ``cohort_month``; none for grain ``total``).
- :func:`check_project`: blueprint rules L1 to L9 over the files of the generated project (no database). Each
  finding has ``rule``, ``severity`` (from ``knowledge/blueprint.md``), ``target`` (the model) and ``problem``;
  the blueprint's named exceptions are honoured. High findings stop the build (``blueprint_failed``).
- :func:`write_gaps`: ``governor/gaps.md`` from the declined KPIs.
- :func:`dbt_build_gold`, :func:`summarise`: ``dbt build --select marts`` and ``governor/build.json``.

Hashes are SHA-256 of UTF-8 text with line endings normalised to ``\\n`` (a checkout with autocrlf keeps them).
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Callable

import sqlglot
import yaml
from pydantic import BaseModel, ConfigDict
from sqlglot import exp
from sqlglot.errors import SqlglotError

from governor.build import silver
from governor.build.dbt import DbtResult, run_dbt
from governor.build.models import KpiDecision, Proposal
from governor.core import paths
from governor.core.catalogue import Blueprint, Kpi, KpiCatalogue, load_blueprint, render

DEFAULT_BLUEPRINT = paths.KNOWLEDGE / "blueprint.md"
MARTS = "marts"
SCHEMA = silver.SCHEMA
GRAIN_COLUMN = {"month": "month", "cohort_month": "cohort_month"}

BUILT, ESCALATED, BLUEPRINT_FAILED = "built", "escalated", "blueprint_failed"

L9_PATTERNS = [("CAST", re.compile(r"\b(?:TRY_)?CAST\s*\(", re.I)), ("::", re.compile(r"::")),
               ("TRIM", re.compile(r"\b(?:B|L|R)?TRIM\s*\(", re.I)), ("LOWER", re.compile(r"\bLOWER\s*\(", re.I)),
               ("UPPER", re.compile(r"\bUPPER\s*\(", re.I)), ("REPLACE", re.compile(r"\bREPLACE\s*\(", re.I))]

_REF = re.compile(r"""\{\{\s*ref\(\s*(?:['"][^'"]+['"]\s*,\s*)?['"]([^'"]+)['"]\s*\)\s*\}\}""")
_SOURCE = re.compile(r"""\{\{\s*source\(\s*['"]([^'"]+)['"]\s*,\s*['"]([^'"]+)['"]\s*\)\s*\}\}""")
_JINJA = re.compile(r"\{\{.*?\}\}|\{%.*?%\}|\{#.*?#\}", re.S)


class BlueprintFinding(BaseModel):
    """One broken blueprint rule: ``rule`` (``L1``..``L9``), ``severity``, ``target`` (model) and ``problem``."""

    model_config = ConfigDict(extra="forbid")

    rule: str
    severity: str
    target: str
    problem: str

    def line(self) -> str:
        return f"{self.rule} ({self.severity}) {self.target}: {self.problem}"


Finding = BlueprintFinding


def _proposal(design: Proposal | dict) -> Proposal:
    return design if isinstance(design, Proposal) else Proposal.model_validate(design)


def _lf(text: str) -> str:
    return text.replace("\r\n", "\n")


def sha256(text: str) -> str:
    return hashlib.sha256(_lf(text).encode("utf-8")).hexdigest()


def _write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_lf(text).encode("utf-8"))  # bytes: no CRLF translation on Windows, so the hash is the file
    return path


# --------------------------------------------------------------------------- gold models


def gold_sql(kpi: Kpi, mapping: dict[str, str]) -> str:
    """``catalogue.render`` with each relation mapped to ``{{ ref('<model>') }}`` (inputs as given)."""
    filled = {name: (f"{{{{ ref('{value}') }}}}" if name in kpi.relations else value) for name, value in mapping.items()}
    return render(kpi, filled)


def model_name(kpi_id: str) -> str:
    return f"kpi_{kpi_id}"


def built_kpis(design: Proposal | dict) -> list[KpiDecision]:
    return [k for k in _proposal(design).kpis if k.decision == "build"]


def declined_kpis(design: Proposal | dict) -> list[KpiDecision]:
    return [k for k in _proposal(design).kpis if k.decision == "decline"]


def gold_path(target: str | Path, k: KpiDecision) -> Path:
    return Path(target) / "models" / MARTS / silver.mart_folder(k.domain) / f"{model_name(k.id)}.sql"


def _model_yml(kpi: Kpi, sql: str) -> dict:
    meta = {"kpi_id": kpi.id, "owner": kpi.owner or "", "source_tier": kpi.source.tier if kpi.source else "",
            "source_ref": kpi.source.ref if kpi.source else "", "template_sha256": sha256(kpi.template_sql),
            "rendered_sha256": sha256(sql)}
    out: dict[str, Any] = {"name": model_name(kpi.id), "description": " ".join(kpi.definition.split()),
                           "config": {"meta": meta}}
    grain = GRAIN_COLUMN.get(kpi.grain)
    if grain:
        out["columns"] = [{"name": grain, "description": f"the {kpi.grain.replace('_', ' ')} (grain)",
                           "data_tests": ["not_null"]}]
    return out


def write_gold(target: str | Path, design: Proposal | dict, catalogue: KpiCatalogue) -> list[Path]:
    """Write the KPI models and their ``_<domain>.yml`` files; stale files of an earlier design are removed first."""
    target, prop = Path(target), _proposal(design)
    silver.prune_stale(target, prop)
    written: list[Path] = []
    by_domain: dict[str, list[dict]] = {}
    for k in built_kpis(prop):
        kpi = catalogue.get(k.id)
        sql = gold_sql(kpi, k.mapping)
        written.append(_write(gold_path(target, k), sql))
        by_domain.setdefault(silver.mart_folder(k.domain), []).append(_model_yml(kpi, sql))
    for domain, models in by_domain.items():
        doc = {"version": 2, "models": models}
        path = target / "models" / MARTS / domain / f"_{domain}.yml"
        written.append(_write(path, yaml.safe_dump(doc, sort_keys=False, allow_unicode=True, width=1000)))
    return written


# --------------------------------------------------------------------------- gap report


def gaps(design: Proposal | dict) -> list[dict]:
    out = []
    for k in declined_kpis(design):
        g = k.gap
        out.append({"id": k.id, "reason": k.reason or "", "missing": list(g.missing) if g else [],
                    "typical_sources": list(g.typical_sources) if g else [], "next_step": g.next_step if g else ""})
    return out


def write_gaps(target: str | Path, design: Proposal | dict) -> Path:
    """``governor/gaps.md``: per declined KPI, why, the missing data, where it usually comes from and the next step."""
    items = gaps(design)
    lines = ["# Gap report", "",
             "KPIs from the catalogue that the approved design declines, and the data that would make them buildable.",
             ""]
    if not items:
        lines += ["No KPI was declined.", ""]
    for g in items:
        lines += [f"## {g['id']}", "", f"Reason: {g['reason'] or '(none given)'}", "",
                  f"- Missing data: {', '.join(g['missing']) or '(not stated)'}",
                  f"- Typical sources: {', '.join(g['typical_sources']) or '(not stated)'}",
                  f"- Next step: {g['next_step'] or '(not stated)'}", ""]
    return _write(Path(target) / "governor" / "gaps.md", "\n".join(lines))


# --------------------------------------------------------------------------- blueprint check


def _strip_sql(text: str) -> str:
    """SQL without comments and string literals (so a cast word inside a literal does not count)."""
    text = re.sub(r"--[^\n]*", " ", text)
    text = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
    return re.sub(r"'(?:[^']|'')*'", "''", text)


def _plain(sql: str) -> str:
    """Jinja calls replaced by identifiers so sqlglot can parse the model."""
    def swap(m: re.Match) -> str:
        ref = _REF.fullmatch(m.group(0))
        if ref:
            return f" __ref_{ref.group(1)} "
        src = _SOURCE.fullmatch(m.group(0))
        if src:
            return f" __source_{src.group(1)}_{src.group(2)} "
        return " __jinja "
    return _JINJA.sub(swap, sql)


def _parse(sql: str) -> exp.Expression | None:
    try:
        trees = [t for t in sqlglot.parse(_plain(sql), read="postgres") if t is not None]
    except SqlglotError:
        return None
    return trees[0] if len(trees) == 1 else None


def _pii_names(policy: dict | str | Path | None) -> set[str]:
    if policy is None:
        return set()
    if not isinstance(policy, dict):
        policy = yaml.safe_load(Path(policy).read_text(encoding="utf-8")) or {}
    return {str(k).split(".")[-1].lower() for k in policy}


def _meta(entry: dict) -> dict:
    cfg = entry.get("config") or {}
    return {**(entry.get("meta") or {}), **(cfg.get("meta") or {})}


def _tests(col: dict) -> set[str]:
    out = set()
    for t in list(col.get("data_tests") or []) + list(col.get("tests") or []):
        if isinstance(t, str):
            out.add(t)
        elif isinstance(t, dict) and t:
            out.add(str(t.get("test_name") or next(iter(t))))
    return out


def _passthrough_names(tree: exp.Expression) -> list[tuple[str, list[str], bool]]:
    """For each output column of the final SELECT: its name, the column names it passes through unchanged (through
    CTEs; empty when it is computed) and whether it is a ``*``."""
    ctes: dict[str, exp.Expression] = {}
    for cte in tree.find_all(exp.CTE):
        ctes[cte.alias_or_name.lower()] = cte.this

    def chain(name: str, depth: int) -> list[str]:
        # over-approximate: any CTE column of that name that is a renamed bare column is followed
        names = [name]
        if depth > 10:
            return names
        for body in ctes.values():
            for proj in getattr(body, "selects", []) or []:
                inner = proj.this if isinstance(proj, exp.Alias) else proj
                if (proj.alias_or_name.lower() == name and isinstance(inner, exp.Column)
                        and inner.name.lower() != name):
                    names += chain(inner.name.lower(), depth + 1)
        return names

    out = []
    for proj in getattr(tree, "selects", []) or []:
        inner = proj.this if isinstance(proj, exp.Alias) else proj
        name = proj.alias_or_name.lower()
        if isinstance(inner, exp.Star) or (isinstance(inner, exp.Column) and isinstance(inner.this, exp.Star)):
            out.append(("*", [], True))
        elif isinstance(inner, exp.Column):
            out.append((name, [name, *chain(inner.name.lower(), 0)], False))
        else:
            out.append((name, [name], False))
    return out


class _Project:
    """The model files and yml entries of a dbt project, keyed by model name."""

    def __init__(self, target: Path, blueprint: Blueprint):
        self.target = target
        self.folder_layer = {f: layer for layer, spec in blueprint.layers.items() for f in spec.dbt}
        self.models: dict[str, list[Path]] = {}
        root = target / "models"
        for p in sorted(root.rglob("*.sql")) if root.is_dir() else []:
            self.models.setdefault(p.stem, []).append(p)
        self.yml: dict[str, dict] = {}
        for p in sorted(root.rglob("*.y*ml")) if root.is_dir() else []:
            try:
                doc = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
            except yaml.YAMLError:
                continue
            for entry in doc.get("models") or [] if isinstance(doc, dict) else []:
                if isinstance(entry, dict) and entry.get("name"):
                    self.yml[str(entry["name"])] = entry

    def folder(self, path: Path) -> str:
        rel = path.relative_to(self.target / "models").parts
        return rel[0] if len(rel) > 1 else ""

    def layer(self, name: str) -> str | None:
        files = self.models.get(name) or []
        return self.folder_layer.get(self.folder(files[0])) if files else None

    def in_layer(self, layer: str) -> list[tuple[str, Path]]:
        return [(n, ps[0]) for n, ps in self.models.items() if self.layer(n) == layer]


def check_project(target: str | Path, catalogue: KpiCatalogue, policy: dict | str | Path | None = None, *,
                  blueprint: Blueprint | str | Path | None = None) -> list[BlueprintFinding]:
    """Blueprint rules L1 to L9 over the files of ``target`` (section 10); empty means the project conforms."""
    target = Path(target)
    bp = blueprint if isinstance(blueprint, Blueprint) else load_blueprint(blueprint or DEFAULT_BLUEPRINT)
    severity = {r.id: r.severity for r in bp.rules}
    excepted = {(e.rule, e.target) for e in bp.exceptions}
    proj = _Project(target, bp)
    pii = _pii_names(policy)
    found: list[BlueprintFinding] = []

    def add(rule: str, model: str, problem: str) -> None:
        if (rule, model) not in excepted:
            found.append(BlueprintFinding(rule=rule, severity=severity.get(rule, "high"), target=model, problem=problem))

    silver_models = proj.in_layer("silver")
    gold_models = proj.in_layer("gold")
    sql_of = {n: _lf(ps[0].read_text(encoding="utf-8")) for n, ps in proj.models.items()}

    # L1: one layer per model
    for name, files in proj.models.items():
        folders = {proj.folder(p) for p in files}
        bad = sorted(f or "models/" for f in folders if f not in proj.folder_layer)
        if bad:
            add("L1", name, f"model file in {bad}, which belongs to no layer (layer folders: {sorted(proj.folder_layer)})")
        layers = {proj.folder_layer[f] for f in folders if f in proj.folder_layer}
        if len(files) > 1:
            add("L1", name, f"model is defined {len(files)} times ({', '.join(p.relative_to(target).as_posix() for p in files)})"
                + (f" across layers {sorted(layers)}" if len(layers) > 1 else ""))

    # L2 / L3: reads
    for layer, rule, allowed in (("gold", "L2", {"silver", "gold"}), ("silver", "L3", {"bronze", "silver"})):
        for name, _ in proj.in_layer(layer):
            sql = sql_of[name]
            if layer == "gold" and _SOURCE.search(sql):
                add(rule, name, "gold reads a raw source() directly; read the silver model instead")
            for ref in _REF.findall(sql):
                ref_layer = proj.layer(ref)
                if ref_layer is None:
                    add(rule, name, f"ref('{ref}') is not a model of the project")
                elif ref_layer not in allowed:
                    add(rule, name, f"ref('{ref}') reads {ref_layer}; {layer} reads only {' or '.join(sorted(allowed))}")

    # L4 / L6: silver keys and PII tags
    tests_dir = target / "tests"
    for name, path in silver_models:
        entry = proj.yml.get(name)
        if entry is None:
            add("L4", name, "no yml entry, so no primary key or key tests")
            continue
        key = [str(k) for k in (_meta(entry).get("primary_key") or [])]
        cols = {str(c.get("name")): c for c in entry.get("columns") or [] if isinstance(c, dict)}
        if not key:
            add("L4", name, "no primary key declared (config.meta.primary_key)")
        elif len(key) == 1:
            missing = {"unique", "not_null"} - _tests(cols.get(key[0], {}))
            if missing:
                add("L4", name, f"primary key {key[0]} lacks {sorted(missing)} tests")
        elif not (tests_dir / f"{name}__primary_key.sql").is_file():
            add("L4", name, f"composite primary key {key} has no singular test tests/{name}__primary_key.sql")
        tagged = {n.lower() for n, c in cols.items() if _meta(c).get("pii") is True}
        untagged = sorted(n for n in cols if n.lower() in pii and n.lower() not in tagged)
        tree = _parse(sql_of[name]) if proj.folder(path) == "staging" else None
        for p in getattr(tree, "selects", []) or []:
            out = p.alias_or_name
            if out.lower() not in tagged and any(c.name.lower() in pii for c in p.find_all(exp.Column)):
                untagged.append(out)
        for col in sorted(set(untagged)):
            add("L6", name, f"column {col} carries policy PII but is not tagged (config.meta.pii: true)")

    silver_pii = set(pii)
    for name, _ in silver_models:
        for c in (proj.yml.get(name) or {}).get("columns") or []:
            if isinstance(c, dict) and _meta(c).get("pii") is True:
                silver_pii.add(str(c.get("name")).lower())

    # design for L8
    design: Proposal | None = None
    design_file = target / "governor" / "design.json"
    design_error = ""
    if design_file.is_file():
        try:
            design = Proposal.model_validate(json.loads(design_file.read_text(encoding="utf-8")))
        except (ValueError, OSError) as exc:
            design_error = f"governor/design.json does not load ({type(exc).__name__})"
    else:
        design_error = "governor/design.json is missing"
    decisions = {k.id: k for k in design.kpis} if design else {}

    for name, path in gold_models:
        sql, entry = sql_of[name], proj.yml.get(name) or {}
        meta = _meta(entry)
        # L5
        if not str(entry.get("description") or "").strip():
            add("L5", name, "no description")
        if not str(meta.get("owner") or "").strip():
            add("L5", name, "no owner (config.meta.owner)")
        # L7
        tree = _parse(sql)
        if tree is None:
            add("L7", name, "the model does not parse, so its output cannot be checked for PII")
        else:
            for out, chain, star in _passthrough_names(tree):
                if star:
                    add("L7", name, "selects * in its output, which can pass PII columns through")
                else:
                    hit = [c for c in chain if c in silver_pii]
                    if hit:
                        add("L7", name, f"output column {out} passes PII column {hit[-1]} through unmasked")
        # L8
        kpi_id = str(meta.get("kpi_id") or (name[4:] if name.startswith("kpi_") else ""))
        if kpi_id:
            _check_l8(add, name, kpi_id, sql, meta, catalogue, decisions, design_error)
        # L9
        clean = _strip_sql(_JINJA.sub(" ", sql))
        hits = [word for word, pattern in L9_PATTERNS if pattern.search(clean)]
        if hits:
            add("L9", name, f"type cast or string cleaning in gold ({', '.join(hits)}); do it in silver")

    if design is not None:
        built = {model_name(k.id) for k in design.kpis if k.decision == "build"}
        for missing in sorted(built - {n for n, _ in gold_models}):
            add("L8", missing, "the approved design builds this KPI but the project has no gold model for it")
    return found


def _check_l8(add, name: str, kpi_id: str, sql: str, meta: dict, catalogue: KpiCatalogue,
              decisions: dict[str, KpiDecision], design_error: str) -> None:
    try:
        kpi = catalogue.get(kpi_id)
    except KeyError:
        add("L8", name, f"KPI '{kpi_id}' is not in the catalogue")
        return
    if str(meta.get("template_sha256") or "") != sha256(kpi.template_sql):
        add("L8", name, "template_sha256 does not match the catalogue template")
    if str(meta.get("rendered_sha256") or "") != sha256(sql):
        add("L8", name, "rendered_sha256 does not match the model file")
    if design_error:
        add("L8", name, f"cannot re-render: {design_error}")
        return
    k = decisions.get(kpi_id)
    if k is None or k.decision != "build":
        add("L8", name, f"the approved design does not build KPI '{kpi_id}'")
        return
    try:
        fresh = gold_sql(kpi, k.mapping)
    except ValueError as exc:
        add("L8", name, f"the approved mapping does not render: {exc}")
        return
    if _lf(sql) != _lf(fresh):
        add("L8", name, "the model file differs from a fresh render of the catalogue template with the approved mapping")


def high(findings: list[BlueprintFinding]) -> list[BlueprintFinding]:
    return [f for f in findings if f.severity == "high"]


# --------------------------------------------------------------------------- dbt and summary

Runner = Callable[[Path, list[str]], DbtResult]
RowCounter = Callable[[list[str]], dict[str, int]]


def dbt_build_gold(target: str | Path, design: Proposal | dict, *, runner: Runner = run_dbt) -> dict:
    """``dbt build --select marts``: ``{"status": built|escalated, "tests_passed", "models", "escalated"?}``.

    Gold SQL is the catalogue template, so a failure is not repaired by a model; the run escalates with the error."""
    names = [model_name(k.id) for k in built_kpis(design)]
    res = runner(Path(target), ["build", "--select", MARTS])
    passed, errors = 0, []
    for r in res.results:
        status = (r.get("status") or "").lower()
        uid = str(r.get("unique_id") or "")
        if status == "pass" and uid.startswith("test."):
            passed += 1
        if status in ("error", "fail", "runtime error"):
            errors.append((uid, f"dbt {uid} {status}: {(r.get('message') or '').strip()}"))
    out: dict[str, Any] = {"status": BUILT, "tests_passed": passed, "models": names}
    if not res.results or errors or not res.ok:
        owner = next((n for uid, _ in errors for n in sorted(names, key=len, reverse=True) if n in uid), None)
        text = "\n".join(m for _, m in errors) or ("dbt build produced no results:\n" if not res.results else "") + res.log_tail[-2000:]
        out |= {"status": ESCALATED, "escalated": {"model": owner, "folder": MARTS, "error": text[-3000:]}}
    return out


def kpi_rows(names: list[str], dsn: str | None = None) -> dict[str, int]:
    """Row count of each gold table in ``dev_governor``, read as the build login."""
    import psycopg
    from psycopg import sql

    from governor.build.workspace import build_dsn

    out: dict[str, int] = {}
    with psycopg.connect(dsn or build_dsn()) as conn:
        for n in names:
            q = sql.SQL("select count(*) from {}.{}").format(sql.Identifier(SCHEMA), sql.Identifier(n))
            out[n] = int(conn.execute(q).fetchone()[0])
    return out


def model_cost(calls: list[dict]) -> dict:
    by_model: dict[str, dict] = {}
    for c in calls:
        m = by_model.setdefault(str(c.get("model")), {"calls": 0, "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0})
        m["calls"] += 1
        m["input_tokens"] += int(c.get("input_tokens") or 0)
        m["output_tokens"] += int(c.get("output_tokens") or 0)
        m["cost_usd"] = None if m["cost_usd"] is None or c.get("cost_usd") is None else round(m["cost_usd"] + c["cost_usd"], 6)
    costs = [c.get("cost_usd") for c in calls]
    return {"llm_calls": len(calls), "cost_usd": round(sum(costs), 6) if calls and None not in costs else (0.0 if not calls else None),
            "by_model": by_model}


def summarise(target: str | Path, design: Proposal | dict, *, status: str, silver_state: dict, gold_state: dict | None,
              findings: list[dict], calls: list[dict], sql_repairs: int, rows: dict[str, int] | None = None,
              thread_id: str | None = None) -> dict:
    """Write ``governor/build.json`` and return it."""
    prop = _proposal(design)
    gold_state = gold_state or {}
    built = status == BUILT
    kpis = [{"id": k.id, "model": model_name(k.id), "domain": silver.mart_folder(k.domain),
             "rows": (rows or {}).get(model_name(k.id))} for k in built_kpis(prop)] if built else []
    summary = {
        "status": status,
        "thread_id": thread_id,
        "models": {"silver": list(silver_state.get("models") or []), "gold": list(gold_state.get("models") or [])},
        "tests_passed": {"silver": int(silver_state.get("tests_passed") or 0),
                         "gold": int(gold_state.get("tests_passed") or 0)},
        "kpis_built": kpis,
        "gaps": gaps(prop),
        "repairs": sql_repairs,
        "blueprint": findings,
        "cost": model_cost(calls),
    }
    summary["tests_passed"]["total"] = summary["tests_passed"]["silver"] + summary["tests_passed"]["gold"]
    if gold_state.get("escalated"):
        summary["escalated"] = gold_state["escalated"]
    _write(Path(target) / "governor" / "build.json", json.dumps(summary, indent=2, ensure_ascii=False) + "\n")
    return summary


__all__ = ["BLUEPRINT_FAILED", "BUILT", "ESCALATED", "BlueprintFinding", "Finding", "check_project", "dbt_build_gold",
           "gaps", "gold_sql", "high", "kpi_rows", "model_cost", "sha256", "summarise", "write_gaps", "write_gold"]
