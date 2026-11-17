"""The AgentForge core: a minimal, opinionated agent loop.

An agent is just a loop: think -> act -> observe -> repeat, until it decides
the task is done or it runs out of steps. This module keeps that loop tiny and
explicit so you can read it, hack it, and ship it.
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

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
        """Return the action dict in *text*, or None if there is none.

        Kept for backwards compatibility; new code should use
        :meth:`_parse_response`, which also reports invalid JSON.
        """
        action, _error = self._parse_response(text)
        return action

    def _parse_response(self, text: str) -> tuple[dict[str, Any] | None, str | None]:
        """Parse an LLM response.

        Returns ``(action, error)``:

        - ``(dict, None)`` - a tool action was found.
        - ``(None, str)`` - the response tried to be an action but the JSON
          was invalid; the error should be fed back to the model.
        - ``(None, None)`` - no action; the text is the final answer.

        Only the first action block in a response is used. If a model emits
        several blocks in one turn, the rest are ignored for that step and
        the model can issue them again on the next step.
        """
        match = _ACTION_BLOCK.search(text)
        if match is not None:
            try:
                parsed = json.loads(match.group(1))
            except json.JSONDecodeError as exc:
                return None, f"Error: invalid JSON in action block: {exc}"
            if isinstance(parsed, dict) and "tool" in parsed:
                return parsed, None
            return None, "Error: action block must be a JSON object with a 'tool' key."

        # Bare JSON action, without a code fence - some models reply like
        # this, especially with native tool-calling style output.
        stripped = text.strip()
        if stripped.startswith("{"):
            try:
                parsed = json.loads(stripped)
            except json.JSONDecodeError:
                return None, None
            if isinstance(parsed, dict) and "tool" in parsed:
                return parsed, None
        return None, None

    def run(self, task: str) -> str:
        """Run the agent loop on *task* and return the final answer.

        If the LLM callable itself raises (network error, rate limit, ...),
        the loop does not crash: it returns a string starting with
        ``"Error: LLM call failed:"`` so the caller can log or retry.
        Memory is kept between ``run()`` calls; use :meth:`reset` to clear it.
        """
        self.memory.add_user(task)
        for _step in range(1, self.config.max_steps + 1):
            try:
                response = self.llm(self._build_messages(), self.tools.schemas())
            except Exception as exc:  # noqa: BLE001 - do not crash on provider errors
                return f"Error: LLM call failed: {exc}"
            self.memory.add_assistant(response)
            action, parse_error = self._parse_response(response)
            if parse_error is not None:
                # Feed the problem back so the model can try again on the
                # next step instead of showing raw broken JSON to the user.
                self.memory.add_tool("parse_error", parse_error)
                continue
            if action is None:
                # No tool call -> the model produced a final answer.
                return response.strip()
            tool_name = action.get("tool", "")
            args = action.get("args", {}) or {}
            if not isinstance(args, dict):
                observation = "Error: 'args' must be a JSON object."
                self.memory.add_tool(tool_name, observation)
                continue
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
