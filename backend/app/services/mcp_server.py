"""
Azure MCP (Model Context Protocol) Server implementation.
Defines tools that agents expose to each other for agent-to-agent communication.
"""
import asyncio
import logging
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """Represents a tool exposed by an agent via MCP."""
    name: str
    description: str
    input_schema: dict
    handler: Callable
    agent_owner: str


@dataclass
class MCPToolResult:
    success: bool
    data: Any
    error: Optional[str] = None
    execution_time_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())


class MCPServer:
    """
    Azure MCP Server for agent-to-agent communication.
    Each agent registers its tools here, and other agents can call them.
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._call_history: List[dict] = []

    def register_tool(self, tool: MCPTool):
        key = f"{tool.agent_owner}.{tool.name}"
        self._tools[key] = tool
        logger.info(f"MCP: Registered tool '{key}'")

    async def call_tool(self, agent: str, tool_name: str, inputs: dict) -> MCPToolResult:
        """Call a tool registered by an agent."""
        key = f"{agent}.{tool_name}"
        if key not in self._tools:
            return MCPToolResult(success=False, error=f"Tool '{key}' not found")

        tool = self._tools[key]
        start = datetime.utcnow()
        try:
            result = await tool.handler(**inputs) if asyncio.iscoroutinefunction(tool.handler) else tool.handler(**inputs)
            elapsed = (datetime.utcnow() - start).total_seconds() * 1000

            call_record = {
                "tool": key,
                "inputs": inputs,
                "success": True,
                "timestamp": start.isoformat(),
                "duration_ms": elapsed,
            }
            self._call_history.append(call_record)

            return MCPToolResult(success=True, data=result, execution_time_ms=elapsed)
        except Exception as e:
            logger.error(f"MCP: Tool '{key}' failed: {e}")
            return MCPToolResult(success=False, error=str(e))

    def list_tools(self, agent: Optional[str] = None) -> List[dict]:
        """List all available tools, optionally filtered by agent."""
        tools = []
        for key, tool in self._tools.items():
            if agent is None or tool.agent_owner == agent:
                tools.append({
                    "name": key,
                    "description": tool.description,
                    "agent": tool.agent_owner,
                    "input_schema": tool.input_schema,
                })
        return tools

    def get_call_history(self, limit: int = 50) -> List[dict]:
        return self._call_history[-limit:]


def create_mcp_server_with_agents() -> MCPServer:
    """Factory: Create MCP server and register all agent tools."""
    server = MCPServer()

    # Monitor Agent Tools
    server.register_tool(MCPTool(
        name="check_metrics",
        description="Check current metrics for a service from Azure Monitor",
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string", "description": "Service name to check"},
                "timerange_minutes": {"type": "integer", "default": 15},
            },
            "required": ["service"],
        },
        handler=lambda service, timerange_minutes=15: {
            "service": service,
            "cpu_percent": 85.3,
            "memory_percent": 72.1,
            "error_rate": 0.12,
        },
        agent_owner="monitor",
    ))

    server.register_tool(MCPTool(
        name="get_alerts",
        description="Retrieve active Azure Monitor alerts",
        input_schema={
            "type": "object",
            "properties": {
                "severity": {"type": "string", "enum": ["critical", "high", "medium", "low"]},
            },
        },
        handler=lambda severity=None: [
            {"id": "alert-001", "severity": "critical", "service": "payment-service", "message": "CPU > 95%"}
        ],
        agent_owner="monitor",
    ))

    # Diagnostic Agent Tools
    server.register_tool(MCPTool(
        name="analyze_logs",
        description="Analyze service logs using KQL query against Log Analytics",
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "query": {"type": "string", "description": "KQL query"},
                "timerange_hours": {"type": "integer", "default": 1},
            },
            "required": ["service", "query"],
        },
        handler=lambda service, query, timerange_hours=1: {
            "results": [{"timestamp": datetime.utcnow().isoformat(), "message": "Sample log entry", "level": "ERROR"}],
            "count": 342,
        },
        agent_owner="diagnostic",
    ))

    # Fixer Agent Tools
    server.register_tool(MCPTool(
        name="search_codebase",
        description="Search the codebase for relevant code patterns",
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "file_pattern": {"type": "string", "default": "**/*.ts"},
            },
            "required": ["query"],
        },
        handler=lambda query, file_pattern="**/*.ts": {
            "matches": [
                {"file": "src/services/payment.service.ts", "line": 142, "snippet": "async processPayment(...)"},
            ],
            "total": 3,
        },
        agent_owner="fixer",
    ))

    # Deploy Agent Tools
    server.register_tool(MCPTool(
        name="check_deployment_health",
        description="Check health of a deployment in Kubernetes",
        input_schema={
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "namespace": {"type": "string", "default": "production"},
            },
            "required": ["service"],
        },
        handler=lambda service, namespace="production": {
            "pods": [{"name": f"{service}-pod-1", "status": "Running", "ready": True}],
            "replicas": {"desired": 3, "ready": 3, "available": 3},
        },
        agent_owner="deploy",
    ))

    return server


# Global MCP server instance
mcp_server = create_mcp_server_with_agents()
