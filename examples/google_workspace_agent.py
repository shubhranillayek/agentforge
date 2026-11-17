"""A Google Workspace agent: Calendar, Drive and Docs through MCP.

This connects AgentForge to a Google Workspace MCP server using the
bridge in ``agentforge/mcp.py``. The server the example expects by
default is ``workspace-mcp`` (PyPI package ``workspace-mcp``, project
name ``google_workspace_mcp``), started with::

    uvx workspace-mcp

Your Google account is connected by that server, on your own machine -
AgentForge never sees your Google credentials or tokens. Full setup
(Google Cloud project, APIs, OAuth client) is in
``docs/google-workspace.md``. Read that first; this file assumes it is
done.

Configuration is through environment variables:

- ``GOOGLE_WORKSPACE_MCP_COMMAND`` - how to start the server.
  Default: ``uvx workspace-mcp``. Set this if you run a different
  Google Workspace MCP server, or the same one with extra flags, for
  example ``uvx workspace-mcp --tools calendar drive docs``.
- ``GOOGLE_OAUTH_CLIENT_ID`` / ``GOOGLE_OAUTH_CLIENT_SECRET`` - your
  Google OAuth client, which the server uses to sign you in.

If either piece is missing, the example prints what is missing and
exits - it does not crash and does not try to start anything.

The LLM below is a stub, the same pattern as the other examples: it
shows which tools the server gave the agent and answers without calling
one. Replace ``stub_llm`` with a real adapter (see the "Wiring Up an
LLM" section of the README) and the agent can call the Calendar, Drive
and Docs tools for real.
"""
from __future__ import annotations

import os
import shlex
import shutil
from typing import Any

from agentforge import Agent, AgentConfig
from agentforge.mcp import MCPClient, mcp_registry

SETUP_DOC = "docs/google-workspace.md"


def stub_llm(messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> str:
    """Stand-in for a real model - illustrates the (messages, tools) -> str contract.

    A real adapter would look at the task, emit a JSON action block for
    one of the Google tools below, and summarise the result. This stub
    just reports how many tools the server connected, so the example
    runs the same way for everyone.
    """
    names = ", ".join(t["name"] for t in tools[:5])
    return (
        f"Connected to the Google Workspace MCP server with {len(tools)} tools "
        f"available (first few: {names}). Swap stub_llm for a real LLM adapter "
        "and I can use them - for example to list today's calendar events, "
        "search Drive, or read a Doc."
    )


# --- Real LLM adapter goes here -------------------------------------------
# def my_llm_client(messages: list[dict], tools: list[dict]) -> str:
#     ... call your model, return a JSON action block or plain text ...
# Then pass llm=my_llm_client instead of llm=stub_llm below.


def main() -> None:
    command_text = os.environ.get("GOOGLE_WORKSPACE_MCP_COMMAND", "uvx workspace-mcp")
    command = shlex.split(command_text)

    if not command or shutil.which(command[0]) is None:
        print(f"Google Workspace MCP server not found: '{command_text}' cannot be run.")
        print("Install uv (which provides uvx) or set GOOGLE_WORKSPACE_MCP_COMMAND")
        print(f"to the command that starts your server. Setup steps: {SETUP_DOC}")
        return

    missing = [
        name
        for name in ("GOOGLE_OAUTH_CLIENT_ID", "GOOGLE_OAUTH_CLIENT_SECRET")
        if not os.environ.get(name)
    ]
    if missing:
        print(f"Missing environment variable(s): {', '.join(missing)}")
        print("The MCP server needs your Google OAuth client to sign you in.")
        print(f"Setup steps: {SETUP_DOC}")
        return

    with MCPClient(command) as client:
        registry = mcp_registry(client)
        print(f"Connected: {len(registry)} Google Workspace tools available.")
        agent = Agent(
            name="google-workspace",
            llm=stub_llm,
            tools=registry,
            config=AgentConfig(
                system_prompt=(
                    "You are an assistant with access to the user's Google "
                    "Calendar, Drive and Docs through tools. Use them to "
                    "answer, and say plainly when a tool result is empty."
                ),
                max_steps=8,
            ),
        )
        print(agent.run("What can you do with my Google account?"))


if __name__ == "__main__":
    main()
