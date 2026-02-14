from fastapi import APIRouter, HTTPException, BackgroundTasks
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

MOCK_INCIDENTS = [
    {
        "title": "High CPU Usage - Payment Service",
        "description": "Payment service CPU exceeded 95% threshold for 5 consecutive minutes",
        "severity": IncidentSeverity.CRITICAL,
        "service": "payment-service",
        "error_count": 342,
        "affected_users": 1250,
    },
    {
        "title": "Memory Leak Detected - Auth Service",
        "description": "Auth service memory growing unbounded, approaching OOM",
        "severity": IncidentSeverity.HIGH,
        "service": "auth-service",
        "error_count": 87,
        "affected_users": 430,
    },
    {
        "title": "Database Connection Pool Exhausted",
        "description": "PostgreSQL connection pool at 100% capacity, queries queuing",
        "severity": IncidentSeverity.HIGH,
        "service": "user-service",
        "error_count": 156,
        "affected_users": 890,
    },
    {
        "title": "Slow API Response - Recommendations Engine",
        "description": "P99 latency spiked to 12s (threshold: 2s) in recommendations service",
        "severity": IncidentSeverity.MEDIUM,
        "service": "recommendation-service",
        "error_count": 45,
        "affected_users": 320,
    },
    {
        "title": "CI/CD Pipeline Failure - Deploy Stage",
        "description": "Kubernetes deployment failing with ImagePullBackOff on 3 pods",
        "severity": IncidentSeverity.HIGH,
        "service": "k8s-cluster",
        "error_count": 12,
        "affected_users": 0,
    },
]


@router.get("/incidents", response_model=List[Incident])
async def list_incidents():
    return list(incidents_db.values())


@router.get("/incidents/{incident_id}", response_model=Incident)
async def get_incident(incident_id: str):
    if incident_id not in incidents_db:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found")
    return incidents_db[incident_id]


@router.post("/incidents/simulate", response_model=Incident)
async def simulate_incident(background_tasks: BackgroundTasks, scenario_index: Optional[int] = None):
    from agents.orchestrator import OrchestratorAgent
    from agents.monitor_agent import ANOMALY_SCENARIOS

    idx = scenario_index if scenario_index is not None else random.randint(0, len(ANOMALY_SCENARIOS) - 1)
    idx = idx % len(ANOMALY_SCENARIOS)
    scenario = ANOMALY_SCENARIOS[idx]

    # Build incident directly from the rich scenario data (includes mock_logs)
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


@router.delete("/incidents")
async def clear_incidents():
    incidents_db.clear()
    for status in agent_statuses.values():
        status.status = "idle"
        status.current_task = None
        status.last_action = None
    return {"status": "cleared"}
