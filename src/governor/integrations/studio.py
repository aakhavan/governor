"""LangGraph Studio entry points (batch4.md section 36).

Each function returns a compiled graph with no checkpointer (Studio adds its own).
The real OpenRouter model is used when ``OPENROUTER_API_KEY`` is set; otherwise the
fake. Importing this module does not open a network connection.
"""

from __future__ import annotations

import os


def build():
    from governor.build.graph import build_graph
    from governor.build.llm import FakeBuildLLM, OpenRouterLLM

    llm = OpenRouterLLM() if os.environ.get("OPENROUTER_API_KEY") else FakeBuildLLM({})
    return build_graph(llm, None)


def ask():
    from governor.ask.graph import build_graph

    llm = None
    if not os.environ.get("OPENROUTER_API_KEY"):
        from governor.ask.llm_testing import FakeLLM

        llm = FakeLLM()
    return build_graph(llm=llm, checkpointer=None)
