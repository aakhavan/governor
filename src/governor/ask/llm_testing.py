"""Offline chat model for tests and ``--llm fake``.

``FakeLLM`` answers ``invoke`` with scripted replies (a list, consumed in
order, then the default) or with a function of the prompt. It records every
prompt it was given and reports zero tokens and zero cost, in the same
message shape ``governor.core.llm.usage_from_message`` reads. ``load_script``
builds one from a JSON script for ``python -m governor.ask.run --llm fake:...``.
"""

from __future__ import annotations

import json
from pathlib import Path
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


# Prompt kinds for scripted runs, keyed by graph prompt file.
SCRIPT_KINDS = {"plan": "plan", "draft_sql": "sql", "repair": "sql", "answer": "answer"}


def scripted(script: Sequence[str] | dict[str, Sequence[str]], prompts_dir: Path | None = None) -> FakeLLM:
    """A FakeLLM from a script (``--llm fake:SCRIPT.json``).

    A list is replied in order. A dict maps a prompt kind (``plan``, ``sql``,
    ``answer``) to its own list of replies; each list is consumed in order and
    its last reply repeats. The kind is found from the prompt's first line.
    """
    if not isinstance(script, dict):
        return FakeLLM(list(script))
    folder = Path(prompts_dir or Path(__file__).resolve().parent / "prompts")
    heads = {
        (folder / f"{name}.md").read_text(encoding="utf-8").splitlines()[0].strip(): kind
        for name, kind in SCRIPT_KINDS.items()
    }
    queues = {kind: list(replies) for kind, replies in script.items()}

    def reply(prompt: str) -> str:
        lines = prompt.strip().splitlines()
        queue = queues.get(heads.get(lines[0].strip() if lines else "", "sql")) or []
        if not queue:
            return DEFAULT_REPLY
        return queue.pop(0) if len(queue) > 1 else queue[0]

    return FakeLLM(reply)


def load_script(path: str | Path) -> FakeLLM:
    """``scripted`` from a JSON file."""
    return scripted(json.loads(Path(path).read_text(encoding="utf-8")))
