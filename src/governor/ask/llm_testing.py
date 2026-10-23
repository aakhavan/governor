"""Offline chat model for tests and ``--llm fake``.

``FakeLLM`` answers ``invoke`` with scripted replies (a list, consumed in
order, then the default) or with a function of the prompt. It records every
prompt it was given and reports zero tokens and zero cost, in the same
message shape ``governor.core.llm.usage_from_message`` reads.
"""

from __future__ import annotations

from typing import Any, Callable, Sequence

from langchain_core.messages import AIMessage, BaseMessage

DEFAULT_REPLY = "SELECT 1"


def prompt_text(prompt: Any) -> str:
    """The text of a prompt given as a string, a message, or a list of messages."""
    if isinstance(prompt, str):
        return prompt
    if isinstance(prompt, BaseMessage):
        return str(prompt.content)
    if isinstance(prompt, Sequence):
        return "\n\n".join(prompt_text(p) for p in prompt)
    return str(prompt)


class FakeLLM:
    def __init__(
        self,
        responses: Sequence[str] | Callable[[str], str] | None = None,
        default: str = DEFAULT_REPLY,
    ) -> None:
        self._script = None if callable(responses) else list(responses or [])
        self._fn = responses if callable(responses) else None
        self.default = default
        self.calls: list[str] = []

    def invoke(self, prompt: Any, **_: Any) -> AIMessage:
        text = prompt_text(prompt)
        self.calls.append(text)
        if self._fn is not None:
            reply = self._fn(text)
        elif self._script:
            reply = self._script.pop(0)
        else:
            reply = self.default
        return AIMessage(
            content=reply,
            usage_metadata={"input_tokens": 0, "output_tokens": 0, "total_tokens": 0},
            response_metadata={"token_usage": {"prompt_tokens": 0, "completion_tokens": 0, "cost": 0.0}},
        )
