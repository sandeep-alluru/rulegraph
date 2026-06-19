"""MCP server for rulegraph.

Start:  python -m rulegraph.mcp_server
Or:     rulegraph-mcp

Add to Claude Desktop (~/.config/claude/claude_desktop_config.json):
    {
        "mcpServers": {
            "rulegraph": {
                "command": "rulegraph-mcp"
            }
        }
    }
"""

from __future__ import annotations

import json
import sys
from typing import Any

try:
    import mcp.server.stdio as _mcp_stdio
    import mcp.types as _mcp_types
    from mcp.server import Server as _Server
    _HAS_MCP = True
except ImportError:
    _HAS_MCP = False


def run_server() -> None:
    """Start the MCP server on stdio."""
    if not _HAS_MCP:
        print(
            "MCP server requires: pip install 'rulegraph[mcp]'",
            file=sys.stderr,
        )
        sys.exit(1)

    server = _Server("rulegraph")

    @server.list_tools()
    async def list_tools() -> list[_mcp_types.Tool]:
        """Expose rulegraph tools to MCP clients."""
        return [
            _mcp_types.Tool(
                name="add_rule",
                description="Add a rule node to the rulegraph rule graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "rule_id": {"type": "string", "description": "Unique rule identifier."},
                        "text": {"type": "string", "description": "Full rule text."},
                        "node_type": {
                            "type": "string",
                            "description": "Node type.",
                            "default": "mechanic",
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "default": [],
                        },
                        "source": {"type": "string", "default": ""},
                        "db": {"type": "string", "default": ".rulegraph/rules.db"},
                    },
                    "required": ["rule_id", "text"],
                },
            ),
            _mcp_types.Tool(
                name="query_rules",
                description="Arbitrate a natural-language question against the rule graph.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string", "description": "Natural-language question."},
                        "db": {"type": "string", "default": ".rulegraph/rules.db"},
                    },
                    "required": ["question"],
                },
            ),
            _mcp_types.Tool(
                name="arbitrate",
                description="Return a structured ArbitrationResult for a game-rules question.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "db": {"type": "string", "default": ".rulegraph/rules.db"},
                    },
                    "required": ["question"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool(name: str, arguments: dict[str, Any]) -> list[_mcp_types.TextContent]:
        """Dispatch an MCP tool call."""
        from rulegraph.rule import RuleArbiter, RuleNode, RuleStore

        db = arguments.get("db", ".rulegraph/rules.db")

        if name == "add_rule":
            store = RuleStore(db)
            try:
                node = RuleNode(
                    rule_id=arguments["rule_id"],
                    text=arguments["text"],
                    node_type=arguments.get("node_type", "mechanic"),
                    tags=arguments.get("tags", []),
                    source=arguments.get("source", ""),
                )
                store.save_node(node)
                return [_mcp_types.TextContent(type="text", text=json.dumps(node.to_dict()))]
            finally:
                store.close()

        elif name in ("query_rules", "arbitrate"):
            store = RuleStore(db)
            try:
                graph = store.load_graph()
                arbiter = RuleArbiter(graph)
                result = arbiter.query(arguments["question"])
                store.save_result(result)
                return [_mcp_types.TextContent(type="text", text=json.dumps(result.to_dict()))]
            finally:
                store.close()

        raise ValueError(f"Unknown tool: {name}")

    import asyncio

    async def _main() -> None:
        async with _mcp_stdio.stdio_server() as (read_stream, write_stream):
            await server.run(read_stream, write_stream, server.create_initialization_options())

    asyncio.run(_main())


if __name__ == "__main__":
    run_server()
