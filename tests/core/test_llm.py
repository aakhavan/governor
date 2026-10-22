"""Model list and the reasoning-parameter rule. No network calls."""

from triage.config import ALLOWED_MODELS
from triage.llm import _chat_extra_body


def test_allowed_models_are_the_verified_dropdown_ids():
    assert ALLOWED_MODELS == [
        "openai/gpt-5-mini",
        "anthropic/claude-haiku-4.5",
    ]


def test_reasoning_effort_is_sent_only_for_openai_models():
    openai = _chat_extra_body("openai/gpt-5-mini", "low")
    assert openai["usage"] == {"include": True}
    assert openai["reasoning"] == {"effort": "low"}

    # Forced tool calls and a provider's own thinking mode can conflict,
    # so these two get usage accounting and no reasoning block.
    assert "reasoning" not in _chat_extra_body("anthropic/claude-haiku-4.5", "low")
    assert "reasoning" not in _chat_extra_body("google/gemini-3.8-flash", "low")
    assert "reasoning" not in _chat_extra_body("openai/gpt-5-nano", None)
