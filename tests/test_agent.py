"""Tests for the agent loop in agentforge.core."""
from __future__ import annotations

from typing import Any

from agentforge import Agent, AgentConfig, ToolRegistry, tool


@tool(description="Add two numbers together.")
def add(a: int, b: int) -> int:
    return a + b


@tool(description="Always fails.")
def boom(x: int) -> int:
    raise ValueError("kaboom")


def scripted_llm(replies: list[str]):
    """Return an LLM stub that replays *replies*, then gives a final answer."""
    calls = {"n": 0}

    def llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        idx = min(calls["n"], len(replies) - 1)
        calls["n"] += 1
        return replies[idx]

    return llm


def tool_messages(agent: Agent) -> list[dict[str, Any]]:
    return [m for m in agent.memory.as_messages() if m["role"] == "tool"]


def test_happy_path_tool_call_then_final_answer():
    llm = scripted_llm(
        [
            '```json\n{"tool": "add", "args": {"a": 7, "b": 5}}\n```',
            "7 plus 5 is 12.",
        ]
    )
    agent = Agent(name="mathie", llm=llm, tools=ToolRegistry(add))
    assert agent.run("What is 7 plus 5?") == "7 plus 5 is 12."
    observations = tool_messages(agent)
    assert len(observations) == 1
    assert observations[0]["content"] == "12"
    assert observations[0]["name"] == "add"


def test_plain_text_is_final_answer():
    llm = scripted_llm(["Just an answer, no tools needed."])
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    assert agent.run("hi") == "Just an answer, no tools needed."


def test_unknown_tool_is_fed_back_not_a_crash():
    llm = scripted_llm(
        [
            '```json\n{"tool": "nope", "args": {}}\n```',
            "Sorry, that tool does not exist.",
        ]
    )
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    assert agent.run("go") == "Sorry, that tool does not exist."
    assert "unknown tool 'nope'" in tool_messages(agent)[0]["content"]


def test_tool_exception_is_fed_back():
    llm = scripted_llm(
        [
            '```json\n{"tool": "boom", "args": {"x": 1}}\n```',
            "The tool failed, here is a fallback answer.",
        ]
    )
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(boom))
    assert agent.run("go") == "The tool failed, here is a fallback answer."
    assert "kaboom" in tool_messages(agent)[0]["content"]


def test_missing_args_is_fed_back():
    llm = scripted_llm(
        [
            '```json\n{"tool": "add", "args": {"a": 1}}\n```',
            "I missed an argument.",
        ]
    )
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    assert agent.run("go") == "I missed an argument."
    assert "Error calling add" in tool_messages(agent)[0]["content"]


def test_max_steps_terminates_endless_tool_loop():
    def llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        return '```json\n{"tool": "add", "args": {"a": 1, "b": 2}}\n```'

    agent = Agent(
        name="t",
        llm=llm,
        tools=ToolRegistry(add),
        config=AgentConfig(max_steps=3),
    )
    assert agent.run("loop") == "Reached max steps without producing a final answer."
    assert len(tool_messages(agent)) == 3


def test_nested_dict_args_are_parsed():
    @tool(description="Take a nested config.")
    def configure(config: dict) -> str:
        return f"a={config['a']} c={config['b']['c']}"

    llm = scripted_llm(
        [
            '```json\n{"tool": "configure", "args": {"config": {"a": 1, "b": {"c": 2}}}}\n```',
            "done",
        ]
    )
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(configure))
    assert agent.run("go") == "done"
    assert tool_messages(agent)[0]["content"] == "a=1 c=2"


def test_bare_json_without_code_fence_is_an_action():
    llm = scripted_llm(
        [
            '{"tool": "add", "args": {"a": 2, "b": 3}}',
            "2 plus 3 is 5.",
        ]
    )
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    assert agent.run("go") == "2 plus 3 is 5."
    assert tool_messages(agent)[0]["content"] == "5"


def test_plain_json_without_tool_key_is_a_final_answer():
    llm = scripted_llm(['{"answer": 42}'])
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    assert agent.run("go") == '{"answer": 42}'


def test_invalid_json_in_fence_is_fed_back_not_returned():
    llm = scripted_llm(
        [
            "```json\n{tool: add, args: broken}\n```",
            "My first reply was not valid JSON, here is the answer.",
        ]
    )
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    result = agent.run("go")
    assert result == "My first reply was not valid JSON, here is the answer."
    assert "invalid JSON" in tool_messages(agent)[0]["content"]


def test_invalid_json_every_time_ends_at_max_steps_not_as_answer():
    def llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        return "```json\n{nope}\n```"

    agent = Agent(
        name="t",
        llm=llm,
        tools=ToolRegistry(add),
        config=AgentConfig(max_steps=2),
    )
    assert agent.run("go") == "Reached max steps without producing a final answer."


def test_llm_exception_returns_error_string_instead_of_crashing():
    def llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        raise RuntimeError("API down")

    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    result = agent.run("go")
    assert result.startswith("Error: LLM call failed:")
    assert "API down" in result


def test_memory_persists_between_runs_until_reset():
    llm = scripted_llm(["one", "two"])
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    agent.run("first")
    assert len(agent.memory) == 2
    agent.run("second")
    assert len(agent.memory) == 4
    agent.reset()
    assert len(agent.memory) == 0


def test_first_action_block_wins_when_two_are_sent():
    llm = scripted_llm(
        [
            (
                '```json\n{"tool": "add", "args": {"a": 1, "b": 1}}\n```\n'
                '```json\n{"tool": "add", "args": {"a": 9, "b": 9}}\n```'
            ),
            "done",
        ]
    )
    agent = Agent(name="t", llm=llm, tools=ToolRegistry(add))
    assert agent.run("go") == "done"
    observations = tool_messages(agent)
    assert len(observations) == 1
    assert observations[0]["content"] == "2"
