"""Pydantic models for build mode (batch2.md): the raw-schema profile (section 5), the design proposal and its
validation findings (section 6)."""

from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

InferredType = Literal["integer", "numeric", "timestamp", "date", "boolean", "text"]


class _Model(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ColumnProfile(_Model):
    name: str
    inferred_type: InferredType
    null_rate: float = Field(ge=0.0, le=1.0)
    distinct: int = Field(ge=0)
    pii: bool
    # Only for non-PII integer, numeric, timestamp and date columns; timestamps and dates as ISO text.
    min: int | float | str | None = None
    max: int | float | str | None = None


class TableProfile(_Model):
    name: str
    rows: int = Field(ge=0)
    columns: list[ColumnProfile]
    candidate_keys: list[list[str]]


class Relationship(_Model):
    from_: str = Field(alias="from")
    to: str
    coverage: float = Field(ge=0.0, le=1.0)


class Profile(_Model):
    schema_: str = Field(alias="schema")
    profiled_at_rows: bool = True
    tables: list[TableProfile]
    relationships: list[Relationship]

    def to_json_dict(self) -> dict:
        return self.model_dump(by_alias=True, mode="json")

    def table(self, name: str) -> TableProfile | None:
        return next((t for t in self.tables if t.name == name), None)


# --------------------------------------------------------------------------- design proposal (section 6)
# Shape is enforced here; meaning (folders, keys, PII tags, mappings) is checked by design.validate, which returns
# finding codes the plan model can repair. So the fields the validator judges are permissive (folder is a str, gap
# fields may be empty) and only the structure is strict.


class SilverColumn(_Model):
    name: str
    expr: str | None = None  # SQL over the raw table's columns (staging); null for intermediate
    type: str
    pii: bool = False
    description: str = ""


class SilverModel(_Model):
    name: str
    folder: str  # staging | intermediate
    source_table: str | None = None
    refs: list[str] = Field(default_factory=list)
    description: str = ""
    primary_key: list[str] = Field(default_factory=list)
    columns: list[SilverColumn] = Field(default_factory=list)

    def column_names(self) -> list[str]:
        return [c.name for c in self.columns]


class Gap(_Model):
    missing: list[str] = Field(default_factory=list)
    typical_sources: list[str] = Field(default_factory=list)
    next_step: str = ""


class KpiDecision(_Model):
    id: str
    decision: Literal["build", "decline"]
    domain: str | None = None
    mapping: dict[str, str] = Field(default_factory=dict)  # relation -> silver model; input -> column or boolean SQL
    reason: str | None = None
    gap: Gap | None = None


class Proposal(_Model):
    silver_models: list[SilverModel] = Field(default_factory=list)
    kpis: list[KpiDecision] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    def model(self, name: str) -> SilverModel | None:
        return next((m for m in self.silver_models if m.name == name), None)

    def to_json_dict(self) -> dict:
        """The section 6 shape: silver nulls kept (``source_table``, ``expr``); a KPI shows only what its decision uses."""
        doc = self.model_dump(mode="json")
        for k in doc["kpis"]:
            for key in [key for key, v in k.items() if v is None or (key == "mapping" and k["decision"] == "decline" and not v)]:
                del k[key]
        return doc


# --------------------------------------------------------------------------- the schema the model sees (batch2b section 11)
# Free-form objects come back empty under json_schema structured output, so the model answers each KPI mapping as a
# list of {name, value} pairs. ``ProposalReply.to_proposal`` turns the pairs into the ``mapping`` dict before
# validation; design.json and everything downstream keep the dict.


class MappingPair(_Model):
    name: str
    value: str


class KpiDecisionReply(_Model):
    id: str
    decision: Literal["build", "decline"]
    domain: str | None = None
    mapping_pairs: list[MappingPair] = Field(default_factory=list)
    reason: str | None = None
    gap: Gap | None = None

    @model_validator(mode="before")
    @classmethod
    def _accept_mapping_dict(cls, data: Any) -> Any:
        # A scripted (fake) reply or a model that ignores the schema may still send the dict; take it as pairs.
        if isinstance(data, dict) and isinstance(data.get("mapping"), dict):
            data = dict(data)
            pairs = [{"name": str(k), "value": str(v)} for k, v in data.pop("mapping").items()]
            data["mapping_pairs"] = list(data.get("mapping_pairs") or []) + pairs
        return data

    def to_decision(self) -> KpiDecision:
        return KpiDecision(id=self.id, decision=self.decision, domain=self.domain,
                           mapping={p.name: p.value for p in self.mapping_pairs}, reason=self.reason, gap=self.gap)


class ProposalReply(_Model):
    silver_models: list[SilverModel] = Field(default_factory=list)
    kpis: list[KpiDecisionReply] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)

    def to_proposal(self) -> Proposal:
        return Proposal(silver_models=self.silver_models, kpis=[k.to_decision() for k in self.kpis],
                        assumptions=self.assumptions)


def proposal_as_reply(proposal: dict) -> dict:
    """A proposal in the shape the model answers in (mapping as pairs), for showing a previous proposal back."""
    doc = json.loads(json.dumps(proposal))
    for k in doc.get("kpis") or []:
        if isinstance(k.get("mapping"), dict):
            k["mapping_pairs"] = [{"name": n, "value": v} for n, v in k.pop("mapping").items()]
    return doc


class Finding(_Model):
    """One validation problem: the code (section 6 table), the model or KPI it is about, and what is wrong."""

    code: str
    subject: str
    problem: str

    def line(self) -> str:
        return f"{self.code} {self.subject}: {self.problem}"
