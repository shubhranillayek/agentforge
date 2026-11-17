"""A research agent that searches the web and summarises findings.

Runs as-is with a deterministic stub LLM, so no API keys are needed::

    python examples/research_agent.py
"""
from __future__ import annotations

import textwrap
from typing import Any

from agentforge import Agent, AgentConfig, ToolRegistry, tool


# --- Demo tools (swap for real implementations) ----------------------------
@tool(description="Search the web for a query and return the top results.")
def web_search(query: str, max_results: int = 3) -> list[dict[str, str]]:
    return [
        {"title": f"Result {i + 1} for '{query}'", "url": f"https://example.com/{i + 1}"}
        for i in range(max_results)
    ]


@tool(description="Fetch and return the text content of a URL.")
def fetch_page(url: str) -> str:
    return f"Placeholder body text fetched from {url}."


# --- A deterministic stub LLM so the example runs without API keys ----------
def stub_llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    """Stand-in for a real model - illustrates the (messages, tools) -> str contract."""
    tool_turns = sum(1 for m in messages if m["role"] == "tool")
    if tool_turns == 0:
        return (
            "I'll search the web first.\n"
            '```json\n{"tool": "web_search", "args": {"query": "AI agents 2026", "max_results": 3}}\n```'
        )
    return (
        "Based on the research, here is a concise summary:\n"
        "- AI agents are autonomous systems that plan, use tools, and remember.\n"
        "- The think -> act -> observe loop is the dominant pattern in 2026."
    )


def main() -> None:
    agent = Agent(
        name="researcher",
        llm=stub_llm,
        tools=ToolRegistry(web_search, fetch_page),
        config=AgentConfig(
            system_prompt=(
                "You are a research agent. Use the web_search and fetch_page "
                "tools to gather information, then summarise your findings."
            ),
        ),
    )
    answer = agent.run("Research the current state of AI agents and summarise it.")
    print(textwrap.fill(answer, width=80))


if __name__ == "__main__":
    main()
