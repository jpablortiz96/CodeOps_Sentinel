"""
MCP Client — used by agents to call each other's tools via MCP.

Instead of direct Python method calls, agents communicate through
the MCPClient which:
  1. Wraps calls in A2AMessage format (Agent-to-Agent protocol)
  2. Routes through MCPServer for logging and WebSocket broadcasting
  3. Returns structured results with timing information
  4. Maintains a per-agent call history for traceability

Usage:
    client = MCPClient(caller_name="orchestrator", server=get_mcp_server())
    result = await client.call_tool(
        "diagnostic.analyze_incident",
        {"incident_id": inc.id, "service": inc.service},
        correlation_id=pipeline_corr_id,
        incident_id=inc.id,
    )
"""
import logging
import uuid
from datetime import datetime
from typing import Optional

from .mcp_server import MCPServer

logger = logging.getLogger(__name__)


class MCPClient:
    """
    Agent-side MCP client for inter-agent communication.

    Each agent creates its own MCPClient instance. All calls
    are routed through the shared MCPServer which handles
    logging and WebSocket broadcasting.
    """

    def __init__(self, caller_name: str, server: MCPServer):
        self.caller_name = caller_name
        self._server = server
        self._call_history: list[dict] = []

    async def call_tool(
        self,
        tool_name: str,
        params: dict,
        correlation_id: Optional[str] = None,
        incident_id: Optional[str] = None,
    ) -> dict:
        """
        Call an MCP tool and return the result.

        Parameters
        ----------
        tool_name:       Dotted tool name, e.g. "diagnostic.analyze_incident"
        params:          Tool input parameters matching the tool's input_schema
        correlation_id:  Shared ID for the entire incident pipeline trace
        incident_id:     Incident ID for WebSocket routing

        Returns
        -------
        dict with keys: call_id, tool_name, from_agent, to_agent,
                        result, status, elapsed_ms, ...
        """
        corr_id = correlation_id or str(uuid.uuid4())[:12]

        logger.info(
            f"MCPClient [{self.caller_name}]: calling '{tool_name}' "
            f"(corr={corr_id})"
        )

        result = await self._server.handle_call(
            tool_name=tool_name,
            params=params,
            from_agent=self.caller_name,
            correlation_id=corr_id,
            incident_id=incident_id,
        )

        # Keep local call history for this agent
        self._call_history.append({
            "timestamp": datetime.utcnow().isoformat(),
            "tool": tool_name,
            "status": result.get("status", "unknown"),
            "elapsed_ms": result.get("elapsed_ms"),
            "call_id": result.get("call_id"),
        })
        # Cap local history
        if len(self._call_history) > 100:
            self._call_history = self._call_history[-100:]

        return result

    async def call_monitor(self, action: str, params: dict, **kwargs) -> dict:
        """Convenience wrapper for monitor.* tools."""
        return await self.call_tool(f"monitor.{action}", params, **kwargs)

    async def call_diagnostic(self, action: str, params: dict, **kwargs) -> dict:
        """Convenience wrapper for diagnostic.* tools."""
        return await self.call_tool(f"diagnostic.{action}", params, **kwargs)

    async def call_fixer(self, action: str, params: dict, **kwargs) -> dict:
        """Convenience wrapper for fixer.* tools."""
        return await self.call_tool(f"fixer.{action}", params, **kwargs)

    async def call_deploy(self, action: str, params: dict, **kwargs) -> dict:
        """Convenience wrapper for deploy.* tools."""
        return await self.call_tool(f"deploy.{action}", params, **kwargs)

    @property
    def call_count(self) -> int:
        return len(self._call_history)

    def get_call_history(self) -> list[dict]:
        return list(reversed(self._call_history))
