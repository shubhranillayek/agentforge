"""The AgentForge core: a minimal, opinionated agent loop.

An agent is just a loop: think -> act -> observe -> repeat, until it decides
the task is done or it runs out of steps. This module keeps that loop tiny and
explicit so you can read it, hack it, and ship it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, Callable

from .memory import ConversationBufferMemory
from .tools import ToolRegistry

# A callable that takes a list of messages + tool schemas and returns the
# model's text response. Swap this for the Anthropic SDK, OpenAI, Ollama...
LLMClient = Callable[[list[dict[str, Any]], list[dict[str, Any]]], str]

_ACTION_BLOCK = re.compile(
    r"```(?:json)?\s*(\{.*?\})\s*```",
    re.DOTALL,
)


@dataclass
class AgentConfig:
    """Tune an agent's behaviour."""

    max_steps: int = 10
    system_prompt: str = (
        "You are a helpful, autonomous agent. To act, emit a JSON code block "
        "with keys 'tool' and 'args'. When the task is complete, respond with "
        "the final answer in plain text (no JSON block)."
    )


@dataclass
class Agent:
    """A provider-agnostic agent that runs a think -> act -> observe loop."""

    name: str
    llm: LLMClient
    tools: ToolRegistry = field(default_factory=ToolRegistry)
    memory: ConversationBufferMemory = field(default_factory=ConversationBufferMemory)
    config: AgentConfig = field(default_factory=AgentConfig)

    def _build_messages(self) -> list[dict[str, Any]]:
        messages: list[dict[str, Any]] = [
            {"role": "system", "content": self.config.system_prompt}
        ]
        messages.extend(self.memory.as_messages())
        return messages

    def _parse_action(self, text: str) -> dict[str, Any] | None:
        match = _ACTION_BLOCK.search(text)
        if match is None:
            return None
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None

    def run(self, task: str) -> str:
        """Run the agent loop on *task* and return the final answer."""
        self.memory.add_user(task)
        for step in range(1, self.config.max_steps + 1):
            response = self.llm(self._build_messages(), self.tools.schemas())
            self.memory.add_assistant(response)
            action = self._parse_action(response)
            if action is None:
                # No tool call -> the model produced a final answer.
                return response.strip()
            tool_name = action.get("tool", "")
            args = action.get("args", {}) or {}
            tool = self.tools.get(tool_name)
            if tool is None:
                observation = f"Error: unknown tool '{tool_name}'."
            else:
                try:
                    observation = tool.run(**args)
                except Exception as exc:  # noqa: BLE001 - surface errors to the model
                    observation = f"Error calling {tool_name}: {exc}"
            self.memory.add_tool(tool_name, observation)
        return "Reached max steps without producing a final answer."

    def reset(self) -> None:
        """Clear the agent's conversation memory."""
        self.memory.clear()
