"""A tiny fake MCP server used by test_mcp.py.

Speaks newline-delimited JSON-RPC over stdio, just enough of the MCP
protocol for the AgentForge bridge: initialize, tools/list, tools/call.
It has three fake Google-flavoured tools and needs no network or account.

Run it the way the tests do::

    python tests/fake_mcp_server.py
"""
from __future__ import annotations

import json
import sys

TOOLS = [
    {
        "name": "calendar_list_events",
        "description": "List calendar events for a date.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "date": {"type": "string"},
                "calendar": {"type": "string", "default": "primary"},
            },
            "required": ["date"],
        },
    },
    {
        "name": "drive_search",
        "description": "Search Drive files by name.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "docs_get",
        "description": "Fetch the text of a Google Doc.",
        "inputSchema": {
            "type": "object",
            "properties": {"document_id": {"type": "string"}},
            "required": ["document_id"],
        },
    },
]


def call_tool(name: str, args: dict) -> str:
    if name == "calendar_list_events":
        return f"Events on {args.get('date')}: 10:00 Standup, 13:00 Dentist"
    if name == "drive_search":
        return f"Found 2 files matching '{args.get('query')}': report-2026.pdf, report-notes"
    if name == "docs_get":
        return f"Document {args.get('document_id')}: Quarterly plan. Revenue grew 12%."
    raise ValueError(f"unknown tool {name}")


def main() -> None:
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        method = message.get("method")
        if "id" not in message:
            continue  # a notification, nothing to reply to
        if method == "initialize":
            result = {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "serverInfo": {"name": "fake-workspace", "version": "0.0.1"},
            }
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = message.get("params") or {}
            try:
                text = call_tool(params.get("name", ""), params.get("arguments") or {})
                result = {"content": [{"type": "text", "text": text}], "isError": False}
            except Exception as exc:  # noqa: BLE001 - report it the MCP way
                result = {
                    "content": [{"type": "text", "text": str(exc)}],
                    "isError": True,
                }
        else:
            reply = {
                "jsonrpc": "2.0",
                "id": message["id"],
                "error": {"code": -32601, "message": f"method not found: {method}"},
            }
            print(json.dumps(reply), flush=True)
            continue
        print(json.dumps({"jsonrpc": "2.0", "id": message["id"], "result": result}), flush=True)


if __name__ == "__main__":
    main()
