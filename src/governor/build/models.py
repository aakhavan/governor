"""Pydantic models for build mode (batch2.md). D2: the raw-schema profile (section 5); D3 adds the design proposal."""

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
