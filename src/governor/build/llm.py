"""Model access for build mode (batch2.md section 1 and 8).

Two roles: ``plan`` (``GOVERNOR_BUILD_PLAN_MODEL``: the design proposal, the gap report, the escalation try) and
``write`` (``GOVERNOR_BUILD_WRITE_MODEL``: intermediate SQL and repairs). Both go through
``governor.core.llm`` and every call reports its tokens and billed cost.

``make_llm("fake:<script.json>")`` returns a scripted model for tests and acceptance. Script format (section 8)::

    {"propose": ["<proposal json>", ...],
     "intermediate": {"<model>": ["<sql>", ...]},
     "repair": {"<model>": ["<sql>", ...]}}

Each list is consumed in order and its last reply repeats (the same pattern as ask's ``llm_testing`` module; build
does not import ask).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from governor.core.config import CHAT_MODEL

PLAN_MODEL_ENV = "GOVERNOR_BUILD_PLAN_MODEL"
WRITE_MODEL_ENV = "GOVERNOR_BUILD_WRITE_MODEL"

T = TypeVar("T", bound=BaseModel)


class LLMOutputError(ValueError):
    """The model's reply is not what was asked for (not JSON, wrong shape, empty)."""


def _usage(message: Any, model: str, kind: str) -> dict:
    from governor.core.llm import usage_from_message

    return {"kind": kind, "model": model, **usage_from_message(message)}


def _parse(schema: type[T], text: str) -> T:
    body = (text or "").strip()
    if body.startswith("```"):  # tolerate a fenced reply
        body = body.strip("`")
        body = body[body.find("\n") + 1:] if "\n" in body else body
    try:
        return schema.model_validate_json(body)
    except ValidationError as exc:
        raise LLMOutputError(f"reply does not match {schema.__name__}: {exc.error_count()} error(s): "
                             + "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()[:8])) from None


class BuildLLM:
    """The interface the build graph uses. ``calls`` collects one usage dict per call."""

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def structured(self, kind: str, prompt: str, schema: type[T], role: str = "plan") -> T:
        raise NotImplementedError

    def text(self, kind: str, prompt: str, key: str | None = None, role: str = "write") -> str:
        raise NotImplementedError


class OpenRouterLLM(BuildLLM):
    """Real models; the chat clients are created on first use, so commands that make no call need no key."""

    def __init__(self, plan_model: str | None = None, write_model: str | None = None) -> None:
        super().__init__()
        self.models = {"plan": plan_model or os.environ.get(PLAN_MODEL_ENV) or CHAT_MODEL,
                       "write": write_model or os.environ.get(WRITE_MODEL_ENV) or CHAT_MODEL}
        self._clients: dict[str, Any] = {}

    def _client(self, role: str):
        if role not in self._clients:
            from governor.core.llm import get_chat_model

            self._clients[role] = get_chat_model(model=self.models[role], temperature=0.0, timeout=300, max_retries=2)
        return self._clients[role]

    def structured(self, kind: str, prompt: str, schema: type[T], role: str = "plan") -> T:
        runnable = self._client(role).with_structured_output(schema, method="function_calling", include_raw=True)
        out = runnable.invoke(prompt)
        self.calls.append(_usage(out.get("raw"), self.models[role], kind))
        if out.get("parsed") is None:
            raise LLMOutputError(f"reply does not match {schema.__name__}: {out.get('parsing_error')}")
        return out["parsed"]

    def text(self, kind: str, prompt: str, key: str | None = None, role: str = "write") -> str:
        message = self._client(role).invoke(prompt)
        self.calls.append(_usage(message, self.models[role], kind))
        return str(message.content or "")


class FakeBuildLLM(BuildLLM):
    """Scripted replies by kind (and by model name for ``intermediate`` and ``repair``); zero tokens, zero cost."""

    def __init__(self, script: dict[str, Any]) -> None:
        super().__init__()
        if not isinstance(script, dict):
            raise ValueError("a build fake script is an object: {\"propose\": [...], \"intermediate\": {...}, \"repair\": {...}}")
        self._queues: dict[str, list[str]] = {}
        for kind, replies in script.items():
            if isinstance(replies, dict):
                for key, items in replies.items():
                    self._queues[f"{kind}:{key}"] = list(items)
            else:
                self._queues[kind] = list(replies)
        self.prompts: list[tuple[str, str]] = []

    def _next(self, kind: str, key: str | None, prompt: str) -> str:
        self.prompts.append((kind, prompt))
        self.calls.append({"kind": kind, "model": "fake", "input_tokens": 0, "output_tokens": 0,
                           "reasoning_tokens": 0, "cost_usd": 0.0})
        queue = self._queues.get(f"{kind}:{key}" if key else kind) or []
        if not queue:
            raise LLMOutputError(f"the fake script has no '{kind}' reply" + (f" for '{key}'" if key else ""))
        return queue.pop(0) if len(queue) > 1 else queue[0]

    def structured(self, kind: str, prompt: str, schema: type[T], role: str = "plan") -> T:
        return _parse(schema, self._next(kind, None, prompt))

    def text(self, kind: str, prompt: str, key: str | None = None, role: str = "write") -> str:
        return self._next(kind, key, prompt)


def make_llm(spec: str | None) -> BuildLLM:
    """``openrouter`` (default) or ``fake:<script.json>``."""
    spec = (spec or "openrouter").strip()
    if spec == "openrouter":
        return OpenRouterLLM()
    if spec.startswith("fake:"):
        path = Path(spec.removeprefix("fake:"))
        return FakeBuildLLM(json.loads(path.read_text(encoding="utf-8")))
    raise ValueError(f"unknown --llm {spec!r}: use openrouter or fake:<script.json>")


__all__ = ["BuildLLM", "FakeBuildLLM", "LLMOutputError", "OpenRouterLLM", "make_llm"]
