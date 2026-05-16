"""
MCP server exposing mock CRM / ticketing tools.

Run: python mcp_servers/enterprise_mock/server.py

Wire into agents via ADK MCP integration or LangGraph tool wrappers.
Demonstrates the "connective tissue" pattern from the FDE job description.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Allow importing fieldops without editable install during dev
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))

from mcp.server import Server  # noqa: E402
from mcp.server.stdio import stdio_server  # noqa: E402
from mcp.types import TextContent, Tool  # noqa: E402

from fieldops.tools.enterprise import create_ticket, list_open_tickets, lookup_customer  # noqa: E402

server = Server("enterprise-mock")


@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="lookup_customer",
            description="Fetch customer tier and ARR from mock CRM",
            inputSchema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
                "required": ["customer_id"],
            },
        ),
        Tool(
            name="create_ticket",
            description="Create a ServiceNow-style incident",
            inputSchema={
                "type": "object",
                "properties": {
                    "customer_id": {"type": "string"},
                    "title": {"type": "string"},
                    "priority": {"type": "string"},
                    "category": {"type": "string"},
                    "body": {"type": "string"},
                },
                "required": ["customer_id", "title", "priority", "category", "body"],
            },
        ),
        Tool(
            name="list_open_tickets",
            description="List open incidents, optionally filtered by customer",
            inputSchema={
                "type": "object",
                "properties": {"customer_id": {"type": "string"}},
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    if name == "lookup_customer":
        result = lookup_customer(arguments["customer_id"])
    elif name == "create_ticket":
        result = create_ticket(**arguments)
    elif name == "list_open_tickets":
        result = list_open_tickets(arguments.get("customer_id"))
    else:
        raise ValueError(f"Unknown tool: {name}")

    import json

    payload = {"ok": result.ok, "data": result.data, "audit": result.audit_note}
    return [TextContent(type="text", text=json.dumps(payload))]


async def main() -> None:
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
