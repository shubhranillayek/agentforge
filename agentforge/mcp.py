"""Bridge between AgentForge and MCP (Model Context Protocol) servers.

This module is a small MCP client that talks to a server over stdio using
nothing but the standard library. It lists the server's tools and wraps
each one as a normal AgentForge :class:`~agentforge.tools.Tool`, so an
agent can call MCP tools exactly like tools defined with ``@tool``.

The core package does not import this module, and it has no third-party
dependencies. You only pay for it when you use it::

    from agentforge.mcp import MCPClient, mcp_registry

    with MCPClient(["uvx", "workspace-mcp"]) as client:
        registry = mcp_registry(client)
        agent = Agent(name="google", llm=my_llm, tools=registry)

See ``docs/google-workspace.md`` for a worked Google Workspace setup
(Calendar, Drive, Docs) built on this bridge.
"""
from __future__ import annotations

import json
import shlex
import subprocess
from typing import Any

from .tools import Tool, ToolRegistry

_PROTOCOL_VERSION = "2024-11-05"


class MCPError(RuntimeError):
    """Raised when the MCP server returns an error or stops responding."""


class MCPClient:
    """A minimal MCP client that runs a server as a subprocess over stdio.

    ``command`` is the server command, either as a list
    (``["uvx", "workspace-mcp"]``) or as a single string
    (``"uvx workspace-mcp"``), which is split with :func:`shlex.split`.
    Extra environment variables for the server can be passed with ``env``;
    they are merged on top of the current environment.

    Use it as a context manager so the server process is shut down
    cleanly, or call :meth:`close` yourself.
    """

    def __init__(
        self,
        command: list[str] | str,
        env: dict[str, str] | None = None,
        cwd: str | None = None,
    ) -> None:
        if isinstance(command, str):
            command = shlex.split(command)
        if not command:
            raise ValueError("MCP server command is empty.")
        self.command = command
        self._env = env
        self._cwd = cwd
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 0
        self.server_info: dict[str, Any] = {}

    # -- lifecycle ---------------------------------------------------------

    def start(self) -> MCPClient:
        """Start the server process and run the MCP initialize handshake."""
        if self._proc is not None:
            return self
        import os

        env = None
        if self._env:
            env = {**os.environ, **self._env}
        self._proc = subprocess.Popen(
            self.command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=None,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=env,
            cwd=self._cwd,
        )
        result = self._request(
            "initialize",
            {
                "protocolVersion": _PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "agentforge", "version": "0.1.0"},
            },
        )
        self.server_info = result.get("serverInfo", {}) if isinstance(result, dict) else {}
        self._notify("notifications/initialized")
        return self

    def close(self) -> None:
        """Shut the server process down. Safe to call more than once."""
        proc, self._proc = self._proc, None
        if proc is None:
            return
        try:
            if proc.stdin is not None:
                proc.stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()

    def __enter__(self) -> MCPClient:  # noqa: PYI034 - typing.Self needs 3.11+, we support 3.10
        return self.start()

    def __exit__(self, *exc: object) -> None:
        self.close()

    # -- MCP operations ------------------------------------------------------

    def list_tools(self) -> list[dict[str, Any]]:
        """Return the server's tool descriptions (name, description, inputSchema)."""
        result = self._request("tools/list")
        if isinstance(result, dict):
            tools = result.get("tools", [])
            if isinstance(tools, list):
                return tools
        return []

    def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> str:
        """Call one server tool and return its text result.

        Raises :class:`MCPError` if the server marks the result as an
        error, so the agent loop surfaces it to the model like any other
        tool failure.
        """
        result = self._request(
            "tools/call", {"name": name, "arguments": arguments or {}}
        )
        if not isinstance(result, dict):
            return str(result)
        parts: list[str] = []
        for item in result.get("content", []):
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            elif isinstance(item, dict):
                parts.append(json.dumps(item))
            else:
                parts.append(str(item))
        text = "\n".join(parts)
        if result.get("isError"):
            raise MCPError(text or f"MCP tool '{name}' failed.")
        return text

    # -- JSON-RPC plumbing ---------------------------------------------------

    def _notify(self, method: str) -> None:
        self._send({"jsonrpc": "2.0", "method": method})

    def _request(self, method: str, params: dict[str, Any] | None = None) -> Any:
        if self._proc is None:
            self.start()
        assert self._proc is not None  # for type checkers; start() sets it
        self._next_id += 1
        request_id = self._next_id
        self._send(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "method": method,
                "params": params or {},
            }
        )
        while True:
            message = self._read_message()
            if message.get("id") != request_id:
                # A notification or a server-initiated message; this simple
                # client does not act on them, it just keeps waiting for
                # the response it asked for.
                continue
            if "error" in message:
                error = message["error"]
                detail = error.get("message", error) if isinstance(error, dict) else error
                raise MCPError(f"MCP {method} failed: {detail}")
            return message.get("result")

    def _send(self, payload: dict[str, Any]) -> None:
        assert self._proc is not None and self._proc.stdin is not None
        self._proc.stdin.write(json.dumps(payload) + "\n")
        self._proc.stdin.flush()

    def _read_message(self) -> dict[str, Any]:
        assert self._proc is not None and self._proc.stdout is not None
        while True:
            line = self._proc.stdout.readline()
            if line == "":
                raise MCPError(
                    "MCP server closed the connection "
                    f"({' '.join(self.command)})."
                )
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                # Not every server keeps stdout perfectly clean; ignore
                # lines that are not JSON instead of dying on them.
                continue
            if isinstance(message, dict):
                return message


def mcp_tools(client: MCPClient) -> list[Tool]:
    """Wrap every tool of a connected MCP server as an AgentForge tool.

    The server's ``inputSchema`` is used as-is for the tool parameters -
    unlike ``@tool``, nothing is inferred from type hints here.
    """
    wrapped: list[Tool] = []
    for spec in client.list_tools():
        name = spec.get("name")
        if not name:
            continue
        schema = spec.get("inputSchema") or {}
        properties = schema.get("properties") or {}
        required = schema.get("required")
        wrapped.append(
            Tool(
                name=name,
                description=spec.get("description", "") or "",
                func=_make_caller(client, name),
                parameters=dict(properties),
                required=list(required) if isinstance(required, list) else None,
            )
        )
    return wrapped


def mcp_registry(client: MCPClient) -> ToolRegistry:
    """Return a :class:`ToolRegistry` holding all of the server's tools."""
    return ToolRegistry(*mcp_tools(client))


def _make_caller(client: MCPClient, name: str):
    def call_tool(**kwargs: Any) -> str:
        # MCP tools take one arguments object, so the keyword arguments
        # the agent loop passes in are forwarded as that object.
        return client.call_tool(name, kwargs)

    return call_tool
