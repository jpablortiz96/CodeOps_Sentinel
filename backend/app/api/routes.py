from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime
import random

from models.incident import Incident, IncidentSeverity, IncidentStatus
from models.agent_messages import AgentStatus
from api.websocket import manager

router = APIRouter()

# In-memory store for demo
incidents_db: dict[str, Incident] = {}
agent_statuses: dict[str, AgentStatus] = {
    "monitor": AgentStatus(agent_name="monitor", status="idle", incidents_handled=12, success_rate=1.0),
    "diagnostic": AgentStatus(agent_name="diagnostic", status="idle", incidents_handled=10, success_rate=0.95),
    "fixer": AgentStatus(agent_name="fixer", status="idle", incidents_handled=8, success_rate=0.875),
    "deploy": AgentStatus(agent_name="deploy", status="idle", incidents_handled=7, success_rate=0.857),
}


# ── Incident endpoints ─────────────────────────────────────────────────────────

@router.get("/incidents", response_model=List[Incident])
async def list_incidents():
    return list(incidents_db.values())


@router.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incidents_db[incident_id]


@router.post("/incidents/simulate", response_model=Incident)
async def simulate_incident(
    background_tasks: BackgroundTasks,
    scenario_index: Optional[int] = None,
):
    from agents.orchestrator import OrchestratorAgent
    from agents.monitor_agent import ANOMALY_SCENARIOS

    idx = scenario_index if scenario_index is not None else random.randint(0, len(ANOMALY_SCENARIOS) - 1)
    idx = idx % len(ANOMALY_SCENARIOS)
    scenario = ANOMALY_SCENARIOS[idx]

    metrics = dict(scenario["metrics"])
    if scenario.get("mock_logs"):
        metrics["mock_logs"] = scenario["mock_logs"]

    incident = Incident(
        title=scenario.get("title", f"[{scenario['severity'].upper()}] {scenario['service']}"),
        description=scenario["description"],
        severity=scenario["severity"],
        service=scenario.get("service", "unknown-service"),
        error_count=scenario.get("error_count", random.randint(50, 500)),
        affected_users=scenario.get("affected_users", random.randint(100, 2000)),
        metrics_snapshot=metrics,
    )

    incidents_db[incident.id] = incident
    orchestrator = OrchestratorAgent(incidents_db=incidents_db, agent_statuses=agent_statuses)
    background_tasks.add_task(orchestrator.handle_incident, incident)
    return incident


@router.get("/incidents/{incident_id}/plan")
async def get_incident_plan(incident_id: str):
    """Return the execution plan for a specific incident (from WebSocket broadcast history)."""
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    incident = incidents_db[incident_id]
    return {
        "incident_id": incident_id,
        "incident_status": incident.status,
        "note": "Plans are broadcast in real-time via WebSocket (event: plan_created, plan_step_update). "
                "Connect to /ws to receive live plan updates.",
    }


@router.get("/incidents/{incident_id}/trace")
async def get_incident_trace(incident_id: str):
    """Return the full MCP call trace for an incident."""
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    from mcp.mcp_server import get_mcp_server
    server = get_mcp_server()
    calls = server.get_call_log(incident_id=incident_id, limit=100)
    return {
        "incident_id": incident_id,
        "mcp_call_count": len(calls),
        "calls": calls,
    }


@router.delete("/incidents")
async def clear_incidents():
    incidents_db.clear()
    for status in agent_statuses.values():
        status.status = "idle"
        status.current_task = None
        status.last_action = None
    return {"status": "cleared"}


# ── Agent endpoints ────────────────────────────────────────────────────────────

@router.get("/agents/status", response_model=List[AgentStatus])
async def get_agents_status():
    return list(agent_statuses.values())


@router.post("/agents/trigger")
async def trigger_agent(agent_name: str, action: str = "check"):
    if agent_name not in agent_statuses:
        raise HTTPException(status_code=404, detail=f"Agent '{agent_name}' not found")
    await manager.broadcast_event(
        "agent_triggered",
        {"agent": agent_name, "action": action},
        agent=agent_name,
    )
    return {"status": "triggered", "agent": agent_name, "action": action}


@router.get("/agents/registry")
async def get_agent_registry():
    """Return all registered agents with their capabilities and current status."""
    from framework.agent_registry import get_agent_registry as _get_registry
    registry = _get_registry()
    agents = registry.list_agent_dicts()
    # Merge live status from agent_statuses
    for agent in agents:
        name = agent["name"]
        if name in agent_statuses:
            live = agent_statuses[name]
            agent["status"] = live.status
            agent["current_task"] = live.current_task
            agent["incidents_handled"] = live.incidents_handled
    return {"agents": agents, "total": len(agents)}


@router.get("/agents/{name}/tools")
async def get_agent_tools(name: str):
    """Return the MCP tools exposed by a specific agent."""
    from framework.agent_registry import get_agent_registry as _get_registry
    from mcp.mcp_server import get_mcp_server
    registry = _get_registry()
    agent = registry.get_agent(name)
    if not agent:
        raise HTTPException(status_code=404, detail=f"Agent '{name}' not found")
    server = get_mcp_server()
    tools = []
    for tool_name in agent.tools:
        schema = server.get_tool_schema(tool_name)
        if schema:
            tools.append(schema)
    return {
        "agent": name,
        "description": agent.description,
        "capabilities": agent.capabilities,
        "tools": tools,
        "tool_count": len(tools),
    }


# ── MCP endpoints ──────────────────────────────────────────────────────────────

@router.get("/mcp/tools")
async def list_mcp_tools():
    """List all registered MCP tools with their schemas."""
    from mcp.mcp_server import get_mcp_server
    server = get_mcp_server()
    tools = server.list_tools()
    # Group by agent namespace
    grouped: dict[str, list] = {}
    for tool in tools:
        namespace = tool["name"].split(".")[0]
        grouped.setdefault(namespace, []).append(tool)
    return {
        "tools": tools,
        "total": len(tools),
        "grouped_by_agent": grouped,
    }


@router.post("/mcp/call")
async def call_mcp_tool(
    tool_name: str,
    params: dict,
    from_agent: str = "external",
    incident_id: Optional[str] = None,
):
    """
    Manually invoke an MCP tool.
    Useful for testing individual tools from the dashboard.
    """
    from mcp.mcp_server import get_mcp_server
    server = get_mcp_server()
    result = await server.handle_call(
        tool_name=tool_name,
        params=params,
        from_agent=from_agent,
        incident_id=incident_id,
    )
    return result


@router.get("/mcp/call-log")
async def get_mcp_call_log(limit: int = 50):
    """Return recent MCP tool calls for dashboard visualization."""
    from mcp.mcp_server import get_mcp_server
    server = get_mcp_server()
    return {
        "calls": server.get_call_log(limit=limit),
        "count": limit,
    }


@router.get("/mcp/stream/{tool_name}")
async def stream_mcp_tool(
    tool_name: str,
    service: str = "unknown",
    incident_id: Optional[str] = None,
):
    """
    SSE endpoint for streaming MCP tool execution.
    Returns a Server-Sent Events stream with call progress.
    """
    from mcp.mcp_server import get_mcp_server
    server = get_mcp_server()
    params = {"service": service}
    if incident_id:
        params["incident_id"] = incident_id

    return StreamingResponse(
        server.stream_call(tool_name, params, from_agent="external", incident_id=incident_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
