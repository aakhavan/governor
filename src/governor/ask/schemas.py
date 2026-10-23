"""Model outputs and graph state for the governor-ask graph.

Every model reply is parsed into one of the pydantic models below. The graph
state is a plain ``TypedDict`` of JSON-friendly values (pydantic objects are
stored as dicts) so any LangGraph checkpointer can save it.
"""

from __future__ import annotations

import operator
from typing import Annotated, Any, Literal, TypedDict

import pydantic

Intent = Literal["answer", "clarify", "unanswerable"]

# Columns of one decision-trace row (built by ``record_trace``; G6b stores it).
TRACE_COLUMNS = (
    "trace_id",
    "ts",
    "role",
    "question_hash",
    "question_len",
    "retrieved_ids",
    "plan_json",
    "sql_attempts",
    "policy_decisions",
    "executed_sql",
    "row_count",
    "result_hash",
    "answer",
    "outcome",
    "models",
    "tokens_in",
    "tokens_out",
    "cost_usd",
    "latency_s",
    "human_feedback",
)

Outcome = Literal[
    "answer",  # executed and answered
    "refused_guard",  # input screen or model flag
    "refused_policy",  # PII_FORBIDDEN / TABLE_NOT_ALLOWED
    "refused_repair",  # no valid query within the repair budget
    "refused_error",  # timeout or another execution failure that is not repairable
    "unanswerable",  # the plan says the marts cannot answer it
    "clarify_failed",  # still missing a slot after one clarification
]


class TimeRange(pydantic.BaseModel):
    """Absolute dates (ISO ``YYYY-MM-DD``), already resolved against as_of. ``end`` is exclusive."""

    start: str | None = None
    end: str | None = None


class QueryPlan(pydantic.BaseModel):
    intent: Intent
    models: list[str] = pydantic.Field(default_factory=list)
    metrics: list[str] = pydantic.Field(default_factory=list)
    grain: str | None = None
    filters: list[str] = pydantic.Field(default_factory=list)
    time_range: TimeRange | None = None
    missing_slot: str | None = None
    # The model's half of the guard: the question tries to change the
    # assistant's instructions or role instead of asking about the data.
    injection: bool = False

    @pydantic.model_validator(mode="after")
    def _slot_when_clarifying(self) -> QueryPlan:
        if self.intent == "clarify" and not (self.missing_slot or "").strip():
            raise ValueError("intent clarify needs missing_slot")
        return self


class SqlDraft(pydantic.BaseModel):
    sql: str
    rationale: str = ""

    @pydantic.field_validator("sql")
    @classmethod
    def _not_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("sql is empty")
        return value.strip().rstrip(";").strip()


class AnswerDraft(pydantic.BaseModel):
    text_with_placeholders: str


class AskState(TypedDict, total=False):
    # input
    question: str
    role: str
    # guard and timing
    started_at: str
    refusal: str | None
    outcome: str | None
    # retrieval and plan
    retrieved_ids: list[str]
    context: str
    plan: dict | None
    plan_error: str | None
    clarification: dict | None  # {"slot", "answer"} once the user has answered
    # SQL loop
    sql: str | None  # current draft (model SQL, before the validator rewrite)
    rationale: str
    validated_sql: str | None
    tables: list[str]
    codes: list[str]
    reasons: list[str]
    dry_run_error: str | None
    repairs: int
    sql_attempts: Annotated[list[dict], operator.add]
    policy_decisions: Annotated[list[dict], operator.add]
    # result
    executed_sql: str | None
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
    answer: dict | None
    # metering
    usage: Annotated[list[dict], operator.add]
    trace: dict | None
