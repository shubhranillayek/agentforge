"""An autonomous coding agent scaffold with filesystem tools.

Runs with a stub LLM, so no API keys are needed::

    python examples/autonomous_coder.py
"""
from __future__ import annotations

import os
from typing import Any

from agentforge import Agent, AgentConfig, tool, ToolRegistry


@tool(description="Read a file from disk and return its contents.")
def read_file(path: str) -> str:
    with open(path, "r", encoding="utf-8") as handle:
        return handle.read()


@tool(description="Write content to a file on disk.")
def write_file(path: str, content: str) -> str:
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return f"Wrote {len(content)} characters to {path}."


@tool(description="List the files in a directory.")
def list_dir(path: str = ".") -> list[str]:
    return sorted(os.listdir(path))


def stub_llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    """Deterministic stand-in for a real model."""
    tool_turns = sum(1 for m in messages if m["role"] == "tool")
    if tool_turns == 0:
        return (
            "I'll start by listing the project files.\n"
            '```json\n{"tool": "list_dir", "args": {"path": "."}}\n```'
        )
    return "I reviewed the files and added docstrings to every public function."


def main() -> None:
    agent = Agent(
        name="coder",
        llm=stub_llm,
        tools=ToolRegistry(read_file, write_file, list_dir),
        config=AgentConfig(
            system_prompt=(
                "You are an autonomous coding agent. Use the filesystem tools "
                "to read, understand, and modify code. Make one change at a time."
            ),
            max_steps=8,
        ),
    )
    print(agent.run("Add a docstring to every public function in this project."))


if __name__ == "__main__":
    main()
