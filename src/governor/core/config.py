"""Model and endpoint settings for the LLM clients.

Stands in for the Sprint 4 ``triage.config``, which was not imported. Only
the names ``llm.py`` and ``retrieval.py`` use are kept. Paths come from
``governor.core.paths``. Model ids can be overridden through the
environment; the API key is read by name and never logged.
"""

from __future__ import annotations

import os

from governor.core import paths

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
API_KEY_ENV = "OPENROUTER_API_KEY"

# Verified OpenRouter ids. The first is the default chat model.
ALLOWED_MODELS = [
    "openai/gpt-5-mini",
    "anthropic/claude-haiku-4.5",
]
CHAT_MODEL = os.environ.get("GOVERNOR_CHAT_MODEL", ALLOWED_MODELS[0])
FAST_MODEL = os.environ.get("GOVERNOR_FAST_MODEL", "openai/gpt-5-nano")
# Reasoning models spend output tokens before the answer; see llm.get_chat_model.
MAX_TOKENS = 4096

EMBED_BACKEND = os.environ.get("GOVERNOR_EMBED_BACKEND", "openrouter")
EMBED_MODEL = os.environ.get("GOVERNOR_EMBED_MODEL", "openai/text-embedding-3-small")

CHROMA_DIR = paths.STATE / "chroma"
CHUNKS_PATH = paths.STATE / "chunks.jsonl"


class ConfigError(RuntimeError):
    """A required setting is missing or invalid."""


def get_api_key() -> str:
    key = os.environ.get(API_KEY_ENV, "").strip()
    if not key:
        raise ConfigError(f"{API_KEY_ENV} is not set.")
    return key
