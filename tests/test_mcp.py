"""Tests for the MCP bridge in agentforge.mcp.

These run a tiny fake MCP server (tests/fake_mcp_server.py) over stdio.
No network, no Google account, no real MCP server involved.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

from agentforge import Agent, ToolRegistry
from agentforge.mcp import MCPClient, MCPError, mcp_registry, mcp_tools

FAKE_SERVER = [sys.executable, str(Path(__file__).with_name("fake_mcp_server.py"))]


@pytest.fixture()
def client():
    with MCPClient(FAKE_SERVER) as connected:
        yield connected


def test_initialize_handshake_records_server_info(client):
    assert client.server_info == {"name": "fake-workspace", "version": "0.0.1"}


def test_tools_list_is_wrapped_with_mcp_schemas(client):
    tools = mcp_tools(client)
    assert [t.name for t in tools] == ["calendar_list_events", "drive_search", "docs_get"]

    calendar = tools[0]
    schema = calendar.schema["input_schema"]
    # The MCP inputSchema is used as-is: properties pass through and the
    # server's own required list wins (calendar has a default, but date
    # is the only required field either way).
    assert schema["properties"]["date"] == {"type": "string"}
    assert schema["properties"]["calendar"] == {"type": "string", "default": "primary"}
    assert schema["required"] == ["date"]
    assert calendar.description == "List calendar events for a date."

    drive = tools[1]
    drive_schema = drive.schema["input_schema"]
    # max_results is in properties but not in the server's required list,
    # and it has no default - the explicit MCP required list must win
    # over AgentForge's usual "no default means required" rule.
    assert drive_schema["required"] == ["query"]


def test_registry_holds_all_mcp_tools(client):
    registry = mcp_registry(client)
    assert isinstance(registry, ToolRegistry)
    assert len(registry) == 3
    assert registry.get("docs_get") is not None
    assert [s["name"] for s in registry.schemas()] == [
        "calendar_list_events",
        "drive_search",
        "docs_get",
    ]


def test_call_tool_passes_arguments_and_returns_text(client):
    drive = mcp_registry(client).get("drive_search")
    assert drive is not None
    result = drive.run(query="report")
    assert "report-2026.pdf" in result


def test_call_tool_error_surfaces_as_exception(client):
    docs = mcp_registry(client).get("docs_get")
    assert docs is not None
    # Call the client with a tool the server does not know, through the
    # same path a wrapped tool uses.
    with pytest.raises(MCPError):
        client.call_tool("no_such_tool", {})


def test_full_agent_run_uses_mcp_tool(client):
    replies = [
        '```json\n{"tool": "calendar_list_events", "args": {"date": "2026-11-17"}}\n```',
        "Aaj do events hain: 10 baje standup aur 1 baje dentist.",
    ]
    calls = {"n": 0}

    def stub_llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
        idx = min(calls["n"], len(replies) - 1)
        calls["n"] += 1
        return replies[idx]

    agent = Agent(name="google", llm=stub_llm, tools=mcp_registry(client))
    answer = agent.run("aaj ke calendar events batao")
    assert answer == "Aaj do events hain: 10 baje standup aur 1 baje dentist."
    observations = [m for m in agent.memory.as_messages() if m["role"] == "tool"]
    assert len(observations) == 1
    assert observations[0]["name"] == "calendar_list_events"
    assert "10:00 Standup" in observations[0]["content"]


def test_missing_server_command_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        MCPClient(["definitely-not-a-real-command-xyz"]).start()


def test_close_is_idempotent():
    client = MCPClient(FAKE_SERVER).start()
    client.close()
    client.close()  # second close must not raise
