"""
Agent Registry — central catalog of all agents in the system.

Each agent registers itself at startup with:
  - name:         unique agent identifier
  - description:  what the agent does
  - capabilities: list of high-level capabilities
  - tools:        MCP tool names this agent exposes

The registry provides real-time status tracking and is exposed via
the GET /agents/registry API endpoint for the dashboard.
"""
import logging
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class AgentInfo(BaseModel):
    """Metadata and current status for a registered agent."""

    name: str
    description: str
    capabilities: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)  # MCP tool names
    status: str = "idle"  # idle | working | error | offline
    current_task: Optional[str] = None
    incidents_handled: int = 0
    registered_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    last_active_at: Optional[str] = None
    avg_response_ms: Optional[float] = None


# ─── Pre-defined agent metadata ───────────────────────────────────────────────

_AGENT_DEFINITIONS: list[dict] = [
    {
        "name": "monitor",
        "description": (
            "Continuously polls Azure Monitor and Log Analytics for anomalies. "
            "Detects CPU spikes, memory leaks, high error rates, and SLA breaches."
        ),
        "capabilities": [
            "anomaly_detection",
            "metrics_collection",
            "azure_monitor_integration",
            "incident_creation",
            "sla_monitoring",
        ],
        "tools": ["monitor.check_health", "monitor.get_metrics"],
    },
    {
        "name": "diagnostic",
        "description": (
            "Performs root cause analysis using Azure OpenAI GPT-4o. "
            "Analyzes logs, metrics, and error patterns to identify the root cause "
            "with a confidence score."
        ),
        "capabilities": [
            "root_cause_analysis",
            "log_correlation",
            "gpt4o_inference",
            "confidence_scoring",
            "kql_queries",
        ],
        "tools": ["diagnostic.analyze_incident", "diagnostic.get_root_cause"],
    },
    {
        "name": "fixer",
        "description": (
            "Generates production-safe code fixes using Azure OpenAI GPT-4o and "
            "GitHub Copilot. Creates pull requests with automated test suggestions."
        ),
        "capabilities": [
            "code_generation",
            "gpt4o_inference",
            "github_pr_creation",
            "risk_assessment",
            "test_suggestion",
        ],
        "tools": ["fixer.generate_patch", "fixer.validate_fix"],
    },
    {
        "name": "deploy",
        "description": (
            "Manages the full deployment lifecycle: test suite execution, "
            "pre-deploy validation, rolling deployment, and automatic rollback "
            "on failure."
        ),
        "capabilities": [
            "test_execution",
            "rolling_deployment",
            "health_check_validation",
            "automatic_rollback",
            "kubernetes_integration",
        ],
        "tools": ["deploy.execute_deployment", "deploy.rollback"],
    },
    {
        "name": "orchestrator",
        "description": (
            "Coordinates the full auto-remediation pipeline using TaskPlanner. "
            "Routes decisions through MCP, applies confidence-based gating, "
            "and escalates to human review when needed."
        ),
        "capabilities": [
            "pipeline_orchestration",
            "task_planning",
            "confidence_routing",
            "human_escalation",
            "mcp_coordination",
        ],
        "tools": [],  # Orchestrator calls tools but doesn't expose its own
    },
]


class AgentRegistry:
    """
    Central registry for all CodeOps Sentinel agents.

    Thread-safe for asyncio (single-threaded event loop).
    """

    def __init__(self):
        self._agents: dict[str, AgentInfo] = {}
        # Auto-register all predefined agents
        for defn in _AGENT_DEFINITIONS:
            self._agents[defn["name"]] = AgentInfo(**defn)
        logger.info(
            f"AgentRegistry: registered {len(self._agents)} agents: "
            + ", ".join(self._agents.keys())
        )

    def register(
        self,
        name: str,
        description: str,
        capabilities: list[str],
        tools: list[str],
    ) -> AgentInfo:
        """Register or update an agent's metadata."""
        info = AgentInfo(
            name=name,
            description=description,
            capabilities=capabilities,
            tools=tools,
        )
        self._agents[name] = info
        logger.debug(f"AgentRegistry: registered '{name}'")
        return info

    def get_agent(self, name: str) -> Optional[AgentInfo]:
        return self._agents.get(name)

    def list_agents(self) -> list[AgentInfo]:
        return list(self._agents.values())

    def list_agent_dicts(self) -> list[dict]:
        return [a.model_dump() for a in self._agents.values()]

    def update_status(
        self,
        name: str,
        status: str,
        current_task: Optional[str] = None,
        incidents_handled: Optional[int] = None,
    ) -> None:
        """Update the real-time status of an agent."""
        agent = self._agents.get(name)
        if not agent:
            return
        agent.status = status
        agent.current_task = current_task
        agent.last_active_at = datetime.utcnow().isoformat()
        if incidents_handled is not None:
            agent.incidents_handled = incidents_handled

    def get_agent_tools(self, name: str) -> list[str]:
        agent = self._agents.get(name)
        return agent.tools if agent else []

    def get_agent_capabilities(self, name: str) -> list[str]:
        agent = self._agents.get(name)
        return agent.capabilities if agent else []


# ─── Singleton ────────────────────────────────────────────────────────────────

_registry_instance: Optional[AgentRegistry] = None


def get_agent_registry() -> AgentRegistry:
    """Return the shared AgentRegistry instance."""
    global _registry_instance
    if _registry_instance is None:
        _registry_instance = AgentRegistry()
    return _registry_instance
