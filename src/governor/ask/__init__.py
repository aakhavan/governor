"""governor-ask: answer business questions over the billing marts.

G3 adds the one-shot baseline (``governor.ask.baseline``) and the offline
``FakeLLM`` (``governor.ask.llm_testing``). Prompts live in ``prompts/*.md``.
"""

MODEL = "openai/gpt-5-mini"
