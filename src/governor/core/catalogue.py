"""KPI catalogue, layer blueprint and approved decisions (docs/capstone/design.md sections 6 to 8).

Three human-owned files under ``knowledge/``:

- ``kpis.yaml``: the KPI catalogue, loaded with :func:`load_kpis`;
- ``blueprint.md``: the layer blueprint, YAML front matter then prose, loaded with
  :func:`load_blueprint`;
- ``approved.yaml``: approved decisions (column mappings, blueprint exceptions,
  corrections), loaded with :func:`load_approved`.

The models mirror the YAML keys, so ``model_dump()`` returns the documented
structure. Unknown keys are refused so a typo in a human-owned file fails loudly.
Every loader raises :class:`CatalogueError` (a ``ValueError``) naming the file and,
for KPI problems, the KPI id.

Definition provenance (agreed 4 Nov 2026, extends design section 6): a KPI names an
``owner`` and a ``source: {tier, ref, note}``. When definitions conflict the tiers
win in the order of :data:`SOURCE_PRECEDENCE`: company glossary, accounting or
regulatory standard, the shop's platform docs, vendor glossaries. A ``vendor``
source needs a ``note``. A ``proposed`` KPI may still be missing its owner and
source (a draft under discussion); an ``approved`` KPI must have both.

:func:`render` fills a KPI's ``template_sql`` from a mapping of relation and input
names to SQL identifiers or expressions.
"""

from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

SOURCE_PRECEDENCE: tuple[str, ...] = ("company", "accounting", "platform", "vendor")
"""Source tiers, strongest first: the earlier tier wins when definitions conflict."""

PLACEHOLDER = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

SourceTier = Literal["company", "accounting", "platform", "vendor"]
Severity = Literal["high", "medium", "low"]
DecisionKind = Literal["column_mapping", "blueprint_exception", "correction"]


class CatalogueError(ValueError):
    """A knowledge file is missing, unreadable or fails validation."""


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _nonblank(value: str, what: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{what} must not be empty")
    return value


# --------------------------------------------------------------------------- KPI catalogue


class Relation(_Strict):
    description: str = ""


class KpiInput(_Strict):
    relation: str
    type: str
    description: str = ""


class KpiSource(_Strict):
    tier: SourceTier
    ref: str
    note: str | None = None

    @field_validator("ref")
    @classmethod
    def _ref(cls, v: str) -> str:
        return _nonblank(v, "source.ref (a URL or document name)")

    @model_validator(mode="after")
    def _vendor_note(self) -> KpiSource:
        if self.tier == "vendor" and not (self.note or "").strip():
            raise ValueError("a vendor source needs a note (vendor glossaries rank last; say why it is used)")
        return self


class Kpi(_Strict):
    id: str
    label: str
    status: Literal["proposed", "approved"]
    definition: str
    grain: Literal["month", "customer", "cohort_month", "total"]
    owner: str | None = None
    source: KpiSource | None = None
    relations: dict[str, Relation]
    inputs: dict[str, KpiInput] = Field(default_factory=dict)
    template_sql: str
    requires: list[str] = Field(default_factory=list)
    prerequisites: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)

    def placeholders(self) -> list[str]:
        """Placeholder names in ``template_sql``, in first-seen order."""
        return list(dict.fromkeys(PLACEHOLDER.findall(self.template_sql)))

    def names(self) -> set[str]:
        """Every name a mapping may fill: declared relations and inputs."""
        return set(self.relations) | set(self.inputs)

    @model_validator(mode="after")
    def _consistent(self) -> Kpi:
        problems: list[str] = []
        if self.owner is not None and not self.owner.strip():
            problems.append("owner must not be empty")
        if self.status == "approved":
            if self.owner is None:
                problems.append("an approved KPI needs an owner")
            if self.source is None:
                problems.append("an approved KPI needs a source {tier, ref, note}")
        clash = sorted(set(self.relations) & set(self.inputs))
        if clash:
            problems.append(f"names used as both relation and input: {clash}")
        for name, inp in self.inputs.items():
            if inp.relation not in self.relations:
                problems.append(f"input '{name}' names undeclared relation '{inp.relation}'")
        undeclared = [p for p in self.placeholders() if p not in self.names()]
        if undeclared:
            problems.append(f"template_sql uses undeclared placeholders {undeclared}")
        missing = [r for r in self.requires if r not in self.relations]
        if missing:
            problems.append(f"requires lists undeclared relations {missing}")
        if problems:
            raise ValueError(f"kpi '{self.id}': " + "; ".join(problems))
        return self


def _error_text(exc: ValidationError) -> str:
    parts = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        parts.append(f"{loc}: {msg}" if loc else msg)
    return "; ".join(parts)


class KpiCatalogue(_Strict):
    version: Literal[1]
    kpis: list[Kpi] = Field(default_factory=list)

    @field_validator("kpis", mode="before")
    @classmethod
    def _each(cls, raw: Any) -> Any:
        if raw is None:
            return []
        if not isinstance(raw, list):
            raise ValueError("kpis must be a list")
        out = []
        for i, item in enumerate(raw):
            if isinstance(item, Kpi):
                out.append(item)
                continue
            kid = item.get("id", f"#{i}") if isinstance(item, dict) else f"#{i}"
            try:
                out.append(Kpi.model_validate(item))
            except ValidationError as exc:
                text = _error_text(exc)
                prefix = f"kpi '{kid}': "
                raise ValueError(text if text.startswith(prefix) else prefix + text) from None
        return out

    @model_validator(mode="after")
    def _unique(self) -> KpiCatalogue:
        seen: set[str] = set()
        dups = sorted({k.id for k in self.kpis if k.id in seen or seen.add(k.id)})
        if dups:
            raise ValueError(f"duplicate kpi id(s): {', '.join(repr(d) for d in dups)}")
        return self

    def get(self, kpi_id: str) -> Kpi:
        for k in self.kpis:
            if k.id == kpi_id:
                return k
        raise KeyError(kpi_id)


def render(kpi: Kpi, mapping: dict[str, str]) -> str:
    """Fill ``kpi.template_sql`` from relation/input names to SQL identifiers or expressions.

    Refuses (``CatalogueError``) a mapping that names something the KPI does not
    declare, that leaves a placeholder unfilled, or whose values themselves
    contain a ``{placeholder}`` (so rendering can neither leave nor add one).
    Otherwise values are inserted as given; validating the rendered SQL is the
    caller's job.
    """
    unknown = sorted(set(mapping) - kpi.names())
    if unknown:
        raise CatalogueError(f"kpi '{kpi.id}': mapping names unknown relations or inputs {unknown}")
    injected = sorted(
        f"{name} -> {{{found}}}"
        for name, value in mapping.items()
        for found in PLACEHOLDER.findall(str(value))
    )
    if injected:
        raise CatalogueError(f"kpi '{kpi.id}': mapping values contain placeholders {injected}")
    unfilled = [p for p in kpi.placeholders() if not str(mapping.get(p) or "").strip()]
    if unfilled:
        raise CatalogueError(f"kpi '{kpi.id}': mapping leaves placeholders unfilled {unfilled}")
    rendered = PLACEHOLDER.sub(lambda m: str(mapping[m.group(1)]), kpi.template_sql)
    # a value fragment can combine with a stray brace in the template to form a new one
    formed = list(dict.fromkeys(PLACEHOLDER.findall(rendered)))
    if formed:
        raise CatalogueError(f"kpi '{kpi.id}': rendered SQL still contains placeholders {formed}")
    return rendered


# --------------------------------------------------------------------------- layer blueprint


class Layer(_Strict):
    description: str = ""
    dbt: list[str]


class Rule(_Strict):
    id: str
    severity: Severity
    text: str


class BlueprintException(_Strict):
    rule: str
    target: str
    reason: str
    owner: str

    @field_validator("target", "reason", "owner")
    @classmethod
    def _filled(cls, v: str, info: Any) -> str:
        return _nonblank(v, info.field_name)


class Blueprint(_Strict):
    version: Literal[1] = 1
    layers: dict[str, Layer]
    rules: list[Rule]
    exceptions: list[BlueprintException] = Field(default_factory=list)

    @field_validator("exceptions", mode="before")
    @classmethod
    def _none_is_empty(cls, v: Any) -> Any:
        return [] if v is None else v

    @model_validator(mode="after")
    def _consistent(self) -> Blueprint:
        if not self.layers:
            raise ValueError("blueprint declares no layers")
        seen: set[str] = set()
        dups = sorted({r.id for r in self.rules if r.id in seen or seen.add(r.id)})
        if dups:
            raise ValueError(f"duplicate rule id(s): {dups}")
        folders: dict[str, str] = {}
        for name, layer in self.layers.items():
            for folder in layer.dbt:
                if folder in folders:
                    raise ValueError(f"dbt folder '{folder}' is in layers '{folders[folder]}' and '{name}'")
                folders[folder] = name
        bad = sorted({e.rule for e in self.exceptions} - seen)
        if bad:
            raise ValueError(f"exceptions name unknown rules {bad}")
        return self


def _front_matter(text: str, path: Path) -> Any:
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise CatalogueError(f"{path}: blueprint must start with YAML front matter ('---')")
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return yaml.safe_load("\n".join(lines[1:i]))
    raise CatalogueError(f"{path}: front matter is not closed with '---'")


# --------------------------------------------------------------------------- approved decisions


class Decision(_Strict):
    id: str
    kind: DecisionKind
    subject: str
    value: Any = None
    reason: str
    approved_by: str
    approved_on: dt.date
    source: str | None = None

    @field_validator("id", "subject", "reason", "approved_by")
    @classmethod
    def _filled(cls, v: str, info: Any) -> str:
        return _nonblank(v, info.field_name)


class ApprovedDecisions(_Strict):
    version: Literal[1]
    decisions: list[Decision] = Field(default_factory=list)

    @field_validator("decisions", mode="before")
    @classmethod
    def _none_is_empty(cls, v: Any) -> Any:
        return [] if v is None else v

    @model_validator(mode="after")
    def _unique(self) -> ApprovedDecisions:
        seen: set[str] = set()
        dups = sorted({d.id for d in self.decisions if d.id in seen or seen.add(d.id)})
        if dups:
            raise ValueError(f"duplicate decision id(s): {dups}")
        return self


# --------------------------------------------------------------------------- loaders


def _read(path: Path) -> str:
    try:
        return Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise CatalogueError(f"{path}: cannot read ({exc.__class__.__name__})") from None


def _parse(model: type[BaseModel], data: Any, path: Path) -> Any:
    if not isinstance(data, dict):
        raise CatalogueError(f"{path}: expected a mapping at the top level")
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise CatalogueError(f"{path}: {_error_text(exc)}") from None


def _yaml(path: Path) -> Any:
    try:
        return yaml.safe_load(_read(path))
    except yaml.YAMLError as exc:
        raise CatalogueError(f"{path}: invalid YAML ({exc})") from None


def load_kpis(path: str | Path) -> KpiCatalogue:
    return _parse(KpiCatalogue, _yaml(Path(path)), Path(path))


def load_blueprint(path: str | Path) -> Blueprint:
    p = Path(path)
    try:
        data = _front_matter(_read(p), p)
    except yaml.YAMLError as exc:
        raise CatalogueError(f"{p}: invalid YAML front matter ({exc})") from None
    return _parse(Blueprint, data, p)


def load_approved(path: str | Path) -> ApprovedDecisions:
    return _parse(ApprovedDecisions, _yaml(Path(path)), Path(path))
