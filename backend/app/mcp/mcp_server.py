"""
Azure MCP Server — Model Context Protocol server implementation.

Follows the MCP specification (JSON-RPC 2.0 style) for tool discovery
and invocation. Supports:
  - Tool registration and discovery (GET /mcp/tools)
  - Tool invocation (POST /mcp/call)
  - SSE streaming responses for long-running tools
  - Full call logging for dashboard traceability

Architecture:
  MCPServer
    ├── TOOL_REGISTRY     — schema definitions (from mcp_tools.py)
    ├── call_handlers     — registered callables for each tool
    ├── call_log          — ordered history of all MCP calls
    └── handle_call()     — routes calls, logs, emits WebSocket events
"""
import asyncio
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Callable, Optional

from .mcp_tools import TOOL_REGISTRY, MCPTool

logger = logging.getLogger(__name__)


class MCPCallRecord:
    """Immutable record of a single MCP tool invocation."""

    __slots__ = (
        "call_id", "tool_name", "from_agent", "to_agent",
        "params", "result", "status", "error",
        "started_at", "completed_at", "elapsed_ms",
        "correlation_id",
    )

    def __init__(
        self,
        call_id: str,
        tool_name: str,
        from_agent: str,
        correlation_id: str,
        params: dict,
    ):
        self.call_id = call_id
        self.tool_name = tool_name
        self.from_agent = from_agent
        self.to_agent = tool_name.split(".")[0]  # "diagnostic" from "diagnostic.analyze_incident"
        self.params = params
        self.correlation_id = correlation_id
        self.result: Optional[dict] = None
        self.status = "in_progress"
        self.error: Optional[str] = None
        self.started_at = datetime.utcnow()
        self.completed_at: Optional[datetime] = None
        self.elapsed_ms: Optional[int] = None

    def complete(self, result: dict, elapsed_ms: int):
        self.result = result
        self.status = "success"
        self.completed_at = datetime.utcnow()
        self.elapsed_ms = elapsed_ms

    def fail(self, error: str, elapsed_ms: int):
        self.error = error
        self.status = "error"
        self.completed_at = datetime.utcnow()
        self.elapsed_ms = elapsed_ms

    def to_dict(self) -> dict:
        return {
            "call_id": self.call_id,
            "tool_name": self.tool_name,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "params": self.params,
            "result": self.result,
            "status": self.status,
            "error": self.error,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "elapsed_ms": self.elapsed_ms,
            "correlation_id": self.correlation_id,
        }


class MCPServer:
    """
    Azure MCP Server — central hub for agent tool invocation.

    Agents register callable handlers for their tools.
    Other agents (via MCPClient) call tools by name.
    All calls are logged and broadcast via WebSocket.
    """

    MAX_CALL_LOG = 500  # keep last N calls in memory

    def __init__(self):
        # Tool schemas (from TOOL_REGISTRY) — static definitions
        self._schemas: dict[str, MCPTool] = dict(TOOL_REGISTRY)
        # Dynamic handlers — registered by agent instances at runtime
        self._handlers: dict[str, Callable] = {}
        # Ordered call log (most recent last)
        self._call_log: list[MCPCallRecord] = []
        logger.info(
            f"MCPServer initialized with {len(self._schemas)} tools: "
            + ", ".join(self._schemas.keys())
        )

    # ── Tool registration ──────────────────────────────────────────────────────

    def register_handler(self, tool_name: str, handler: Callable) -> None:
        """
        Register an async callable for a tool.
        Called by agent instances so the server can route requests to them.
        """
        self._handlers[tool_name] = handler
        logger.debug(f"MCPServer: registered handler for '{tool_name}'")

    def register_handlers(self, handlers: dict[str, Callable]) -> None:
        """Batch register multiple handlers at once."""
        for name, fn in handlers.items():
            self.register_handler(name, fn)

    # ── Tool discovery ─────────────────────────────────────────────────────────

    def list_tools(self) -> list[dict]:
        """Return all registered tool schemas (for GET /mcp/tools)."""
        tools = []
        for name, tool in self._schemas.items():
            entry = tool.to_dict()
            entry["has_handler"] = name in self._handlers
            tools.append(entry)
        return tools

    def get_tool_schema(self, tool_name: str) -> Optional[dict]:
        tool = self._schemas.get(tool_name)
        return tool.to_dict() if tool else None

    # ── Call dispatch ──────────────────────────────────────────────────────────

    async def handle_call(
        self,
        tool_name: str,
        params: dict,
        from_agent: str = "external",
        correlation_id: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> dict:
        """
        Dispatch a tool call, log it, and broadcast WebSocket events.

        Resolution order:
          1. Use registered agent handler if available
          2. Fall back to tool's built-in execute() method
          3. Return error if tool not found
        """
        if tool_name not in self._schemas:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(self._schemas.keys()),
            }

        call_id = f"mcp-{str(uuid.uuid4())[:8]}"
        corr_id = correlation_id or str(uuid.uuid4())[:12]

        record = MCPCallRecord(
            call_id=call_id,
            tool_name=tool_name,
            from_agent=from_agent,
            correlation_id=corr_id,
            params=params,
        )

        # Emit call started event via WebSocket
        await self._broadcast_call(record, incident_id, "mcp_call")

        start = time.monotonic()
        try:
            # Prefer registered handler (routes to live agent instance)
            handler = self._handlers.get(tool_name)
            if handler:
                result = await handler(params)
            else:
                # Fall back to the tool's own execute() (standalone mode)
                result = await self._schemas[tool_name].execute(params)

            elapsed_ms = int((time.monotonic() - start) * 1000)
            record.complete(result, elapsed_ms)
            logger.info(
                f"MCPServer: [{call_id}] {from_agent} → {tool_name} "
                f"completed in {elapsed_ms}ms"
            )

        except Exception as e:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            record.fail(str(e), elapsed_ms)
            logger.error(
                f"MCPServer: [{call_id}] {from_agent} → {tool_name} "
                f"failed in {elapsed_ms}ms: {e}"
            )

        # Store record
        self._call_log.append(record)
        if len(self._call_log) > self.MAX_CALL_LOG:
            self._call_log = self._call_log[-self.MAX_CALL_LOG :]

        # Emit response event
        await self._broadcast_call(record, incident_id, "mcp_response")

        return record.to_dict()

    # ── SSE streaming ──────────────────────────────────────────────────────────

    async def stream_call(
        self,
        tool_name: str,
        params: dict,
        from_agent: str = "external",
        incident_id: Optional[str] = None,
    ):
        """
        Generator that yields SSE-formatted events for a tool call.
        Usage: StreamingResponse(server.stream_call(...), media_type="text/event-stream")
        """
        import json

        call_id = f"mcp-{str(uuid.uuid4())[:8]}"

        # Event: call started
        yield f"data: {json.dumps({'event': 'started', 'call_id': call_id, 'tool': tool_name})}\n\n"
        await asyncio.sleep(0)

        result = await self.handle_call(
            tool_name=tool_name,
            params=params,
            from_agent=from_agent,
            incident_id=incident_id,
        )

        # Event: result
        yield f"data: {json.dumps({'event': 'completed', 'call_id': call_id, 'result': result})}\n\n"
        yield "data: [DONE]\n\n"

    # ── Call log ───────────────────────────────────────────────────────────────

    def get_call_log(
        self, incident_id: Optional[str] = None, limit: int = 50
    ) -> list[dict]:
        """Return recent MCP calls, optionally filtered by incident correlation."""
        records = list(reversed(self._call_log))
        if incident_id:
            records = [r for r in records if incident_id in r.correlation_id]
        return [r.to_dict() for r in records[:limit]]

    def get_calls_for_correlation(self, correlation_id: str) -> list[dict]:
        """Return all MCP calls belonging to a single incident pipeline trace."""
        return [
            r.to_dict()
            for r in self._call_log
            if r.correlation_id == correlation_id
        ]

    # ── Internals ──────────────────────────────────────────────────────────────

    async def _broadcast_call(
        self,
        record: MCPCallRecord,
        incident_id: Optional[str],
        event_type: str,
    ) -> None:
        """Broadcast MCP event to WebSocket clients."""
        try:
            from api.websocket import manager

            await manager.broadcast_event(
                event_type=event_type,
                incident_id=incident_id,
                agent=record.from_agent,
                data=record.to_dict(),
            )
        except Exception as e:
            logger.warning(f"MCPServer: WebSocket broadcast failed: {e}")


# ─── Singleton ────────────────────────────────────────────────────────────────

_mcp_server_instance: Optional[MCPServer] = None


def get_mcp_server() -> MCPServer:
    """Return the shared MCPServer instance."""
    global _mcp_server_instance
    if _mcp_server_instance is None:
        _mcp_server_instance = MCPServer()
    return _mcp_server_instance
