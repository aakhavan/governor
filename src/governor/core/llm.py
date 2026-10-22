"""Chat and embedding clients.

OpenRouter is OpenAI-compatible: same LangChain classes, a custom base_url.
Model ids keep the provider prefix (openai/gpt-5-mini).
"""

from __future__ import annotations

from langchain_core.embeddings import Embeddings
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

from governor.core.config import (
    CHAT_MODEL,
    EMBED_BACKEND,
    EMBED_MODEL,
    FAST_MODEL,
    MAX_TOKENS,
    OPENROUTER_BASE_URL,
    ConfigError,
    get_api_key,
)


def _chat_extra_body(model: str, reasoning_effort: str | None) -> dict:
    """Usage accounting, plus reasoning effort for OpenAI models only.

    Forced tool calls (structured output, ToolStrategy) and a provider's
    own thinking mode can conflict. OpenRouter's `reasoning` block is the
    OpenAI control. Anthropic and Gemini use different thinking parameters,
    and sending this one next to a required tool call can fail the request
    or drop the tool. Those models get usage accounting and nothing else.
    """
    body: dict = {"usage": {"include": True}}
    if reasoning_effort and model.startswith("openai/"):
        body["reasoning"] = {"effort": reasoning_effort}
    return body


def get_chat_model(
    model: str | None = None,
    fast: bool = False,
    temperature: float = 0.2,
    timeout: float | None = None,
    max_retries: int | None = None,
    reasoning_effort: str | None = None,
) -> ChatOpenAI:
    """Return a chat model pointed at OpenRouter.

    fast=True selects FAST_MODEL (slot extraction and query translation).
    An explicit model overrides that choice.

    timeout and max_retries are applied when the client is built. Setting
    them on the model afterwards does not change the client already created.

    Reasoning models (gpt-5-mini, gpt-5-nano) spend output tokens on hidden
    reasoning before they write the answer. In Sprint 1 a budget of 800 came
    back empty and 1024 was only just enough; structured output needs 2048
    or more. The call still succeeds when the budget runs out during
    reasoning, and the message text is empty. MAX_TOKENS stays at 4096 so
    there is room for the answer.

    reasoning_effort is sent only when the model id starts with "openai/".
    See _chat_extra_body for why other providers do not get it.
    """
    chosen = model or (FAST_MODEL if fast else CHAT_MODEL)
    kwargs: dict = {}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if max_retries is not None:
        kwargs["max_retries"] = max_retries
    return ChatOpenAI(
        model=chosen,
        temperature=temperature,
        max_tokens=MAX_TOKENS,
        api_key=get_api_key(),
        base_url=OPENROUTER_BASE_URL,
        extra_body=_chat_extra_body(chosen, reasoning_effort),
        **kwargs,
    )


def usage_from_message(message) -> dict:
    """Tokens and billed cost for one model response.

    Tokens come from LangChain's usage_metadata. Cost comes from OpenRouter's
    usage accounting (enabled above), which reports what was actually charged,
    in OpenRouter credits (priced in US dollars). Nothing is estimated: if the
    cost is missing, cost_usd is None and the UI must say "unavailable".

    Works on any AIMessage, including the raw message from
    with_structured_output(..., include_raw=True).
    """
    usage = getattr(message, "usage_metadata", None) or {}
    raw = (getattr(message, "response_metadata", None) or {}).get("token_usage") or {}
    output_details = usage.get("output_token_details") or {}
    cost = raw.get("cost")
    return {
        "input_tokens": int(usage.get("input_tokens") or raw.get("prompt_tokens") or 0),
        "output_tokens": int(usage.get("output_tokens") or raw.get("completion_tokens") or 0),
        "reasoning_tokens": int(output_details.get("reasoning") or 0),
        "cost_usd": float(cost) if cost is not None else None,
    }


def get_embeddings() -> Embeddings:
    """Return the embedding function selected by EMBED_BACKEND.

    "local" imports FastEmbedEmbeddings only on that branch, so the
    OpenRouter path does not load the on-disk model stack.
    """
    if EMBED_BACKEND == "openrouter":
        # OpenAI-compatible endpoints may reject the token-array format that
        # the OpenAI SDK sends when it tokenises the input itself.
        return OpenAIEmbeddings(
            model=EMBED_MODEL,
            api_key=get_api_key(),
            base_url=OPENROUTER_BASE_URL,
            check_embedding_ctx_length=False,
        )
    if EMBED_BACKEND == "local":
        from langchain_community.embeddings.fastembed import FastEmbedEmbeddings

        return FastEmbedEmbeddings(model_name="BAAI/bge-small-en-v1.5")
    raise ConfigError(
        "EMBED_BACKEND must be 'openrouter' or 'local'; "
        f"got {EMBED_BACKEND!r}."
    )
