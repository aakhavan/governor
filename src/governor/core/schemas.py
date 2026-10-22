"""Tool result models shared by retrieval and its callers.

Stands in for the part of the Sprint 4 ``triage.schemas`` that
``retrieval.py`` uses (the agent-specific models were not imported).
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

UNTRUSTED_OPEN = "<untrusted>"
UNTRUSTED_CLOSE = "</untrusted>"


def as_untrusted(text: str | None) -> str | None:
    """Wrap retrieved text so a prompt can tell data from instructions."""
    if text is None:
        return None
    # A passage must not be able to close the wrapper early.
    body = str(text).replace(UNTRUSTED_OPEN, "").replace(UNTRUSTED_CLOSE, "")
    return f"{UNTRUSTED_OPEN}{body}{UNTRUSTED_CLOSE}"


class Hit(BaseModel):
    chunk_id: str
    source: str
    text: str
    score: float


class SearchKnowledgeResult(BaseModel):
    status: Literal["ok", "error"] = "ok"
    hits: list[Hit] = Field(default_factory=list)
    summary: str = ""
