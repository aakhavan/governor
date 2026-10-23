"""One-shot baseline: schema + question in one prompt, SQL out, run it.

The prompt (``prompts/baseline.md``) carries the full mart schema from
``artifacts/meta.duckdb`` (columns, types, descriptions) and the question.
The model replies with SQL or a refusal; SQL runs read-only with the
access.yaml row cap. Nothing else: no retrieval, no validation, no role
policy, no repair. This is the floor the governed pipeline must beat.
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import duckdb
import pydantic
import yaml

from governor.ask import MODEL
from governor.core import paths
from governor.core.config import MAX_TOKENS
from governor.core.llm import get_chat_model, usage_from_message
from governor.eval.golden import Question
from governor.eval.systems import SystemOutput, execute_into, register

PROMPT_FILE = Path(__file__).resolve().parent / "prompts" / "baseline.md"
_FENCE = re.compile(r"^```[a-zA-Z]*\s*|\s*```$")
_SQL_START = re.compile(r"^\s*(select|with)\b", re.IGNORECASE)

assert MAX_TOKENS >= 2048, "reasoning models need room before the answer"


class BaselineReply(pydantic.BaseModel):
    action: Literal["sql", "refuse"]
    sql: str | None = None
    reason: str | None = None

    @pydantic.model_validator(mode="after")
    def _sql_when_answering(self) -> BaselineReply:
        if self.action == "sql" and not (self.sql or "").strip():
            raise ValueError("action sql needs sql")
        return self


def default_llm():
    """gpt-5-mini through OpenRouter (governor.core.llm)."""
    return get_chat_model(model=MODEL)


@lru_cache(maxsize=2)
def mart_schema(meta: Path | None = None) -> str:
    """Every allowlisted mart with its description and columns (name, type, description)."""
    access = yaml.safe_load((paths.KNOWLEDGE / "access.yaml").read_text(encoding="utf-8"))
    marts = list(access["allowlist"]["models"])
    connection = duckdb.connect(str(meta or paths.META), read_only=True)
    try:
        blocks = []
        for mart in marts:
            node = connection.execute(
                "SELECT unique_id, description FROM nodes WHERE resource_type = 'model' AND name = ?", [mart]
            ).fetchone()
            if node is None:
                continue
            columns = connection.execute(
                'SELECT "column", data_type, description FROM columns WHERE unique_id = ? ORDER BY rowid',
                [node[0]],
            ).fetchall()
            lines = [f"### {mart}", (node[1] or "").strip(), ""]
            lines += [f"- {name} ({data_type}): {(desc or '').strip()}" for name, data_type, desc in columns]
            blocks.append("\n".join(lines).strip())
    finally:
        connection.close()
    return "\n\n".join(blocks)


def build_prompt(question: str, schema: str | None = None, as_of: str | None = None) -> str:
    template = PROMPT_FILE.read_text(encoding="utf-8")
    return (
        template.replace("{schema}", schema if schema is not None else mart_schema())
        .replace("{as_of}", as_of or paths.as_of().isoformat())
        .replace("{question}", question.strip())
    )


def _text(content: Any) -> str:
    if isinstance(content, list):
        return "".join(p.get("text", "") if isinstance(p, dict) else str(p) for p in content)
    return str(content or "")


def parse_reply(text: str) -> BaselineReply | None:
    """JSON reply per the prompt; bare (or fenced) SQL is accepted as an answer. None if neither."""
    body = _FENCE.sub("", text.strip()).strip()
    start, end = body.find("{"), body.rfind("}")
    if start != -1 and end > start:
        try:
            return BaselineReply.model_validate(json.loads(body[start : end + 1]))
        except (json.JSONDecodeError, pydantic.ValidationError):
            pass
    if _SQL_START.match(body):
        return BaselineReply(action="sql", sql=body.rstrip(";").strip())
    return None


@register("baseline")
class BaselineSystem:
    name = "baseline"

    def __init__(self, llm: Any = None) -> None:
        self.llm = llm if llm is not None else default_llm()

    def answer(self, q: Question | str, role: str) -> SystemOutput:
        question = q.question if isinstance(q, Question) else str(q)
        message = self.llm.invoke(build_prompt(question))
        usage = usage_from_message(message)
        meter = {
            "cost_usd": usage["cost_usd"],
            "tokens_in": usage["input_tokens"],
            "tokens_out": usage["output_tokens"],
        }
        reply = parse_reply(_text(message.content))
        if reply is None:
            return SystemOutput(behaviour="answer", error="unparseable model reply", **meter)
        if reply.action == "refuse":
            return SystemOutput(behaviour="refuse", **meter)
        return execute_into(SystemOutput(behaviour="answer", sql=reply.sql, **meter))
