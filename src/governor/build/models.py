"""Pydantic models for build mode (batch2.md): the raw-schema profile (section 5), the design proposal and its
validation findings (section 6)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

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


class Finding(_Model):
    """One validation problem: the code (section 6 table), the model or KPI it is about, and what is wrong."""

    code: str
    subject: str
    problem: str

    def line(self) -> str:
        return f"{self.code} {self.subject}: {self.problem}"
