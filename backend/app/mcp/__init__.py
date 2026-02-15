"""
MCP (Model Context Protocol) — Azure MCP Server implementation.

Exposes agent capabilities as standardized MCP tools.
Supports JSON-RPC 2.0 style calls and SSE streaming responses.
"""
from .mcp_server import MCPServer, get_mcp_server
from .mcp_client import MCPClient
from .mcp_tools import TOOL_REGISTRY

__all__ = ["MCPServer", "get_mcp_server", "MCPClient", "TOOL_REGISTRY"]
