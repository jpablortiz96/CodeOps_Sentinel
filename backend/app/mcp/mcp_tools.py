"""
MCP Tool definitions — schema + description for each agent capability.

Each tool follows the Azure MCP specification:
  - name:         dotted namespace (agent.action)
  - description:  human-readable purpose
  - input_schema: JSON Schema for parameters
  - execute():    actual implementation (used by POST /mcp/call)

Tools are grouped by the agent that owns them:
  monitor.*     — MonitorAgent
  diagnostic.*  — DiagnosticAgent
  fixer.*       — FixerAgent
  deploy.*      — DeployAgent
"""
import asyncio
import logging
import random
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class MCPTool(ABC):
    """Base class for all MCP tools."""

    name: str
    description: str
    input_schema: dict

    @abstractmethod
    async def execute(self, params: dict) -> dict:
        """Execute the tool with the given parameters."""

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }


# ── Monitor Tools ─────────────────────────────────────────────────────────────

class MonitorCheckHealthTool(MCPTool):
    name = "monitor.check_health"
    description = (
        "Check the health status of a specific service or all services. "
        "Returns real-time metrics including CPU, memory, error rate, and P99 latency."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "service": {
                "type": "string",
                "description": "Service name to check. Omit for all services.",
            },
            "include_metrics": {
                "type": "boolean",
                "description": "Whether to include detailed metrics snapshot.",
                "default": True,
            },
        },
        "required": [],
    }

    async def execute(self, params: dict) -> dict:
        service = params.get("service", "all-services")
        await asyncio.sleep(0.2)  # simulate I/O
        return {
            "service": service,
            "status": random.choice(["healthy", "degraded", "degraded"]),
            "checked_at": datetime.utcnow().isoformat(),
            "metrics": {
                "cpu_percent": round(random.uniform(20, 95), 1),
                "memory_percent": round(random.uniform(30, 90), 1),
                "error_rate": round(random.uniform(0, 0.4), 3),
                "latency_p99_ms": random.randint(100, 8000),
            },
        }


class MonitorGetMetricsTool(MCPTool):
    name = "monitor.get_metrics"
    description = (
        "Retrieve detailed metrics for a service over a time window. "
        "Queries Azure Monitor / Log Analytics and returns a metrics snapshot."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "service": {"type": "string", "description": "Target service name."},
            "window_minutes": {
                "type": "integer",
                "description": "Look-back window in minutes.",
                "default": 15,
            },
            "metrics": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Specific metrics to retrieve (cpu, memory, error_rate, latency).",
            },
        },
        "required": ["service"],
    }

    async def execute(self, params: dict) -> dict:
        service = params.get("service", "unknown")
        window = params.get("window_minutes", 15)
        await asyncio.sleep(0.3)
        return {
            "service": service,
            "window_minutes": window,
            "snapshot": {
                "cpu_percent": round(random.uniform(20, 99), 1),
                "memory_percent": round(random.uniform(30, 98), 1),
                "error_rate": round(random.uniform(0, 0.5), 3),
                "latency_p99_ms": random.randint(100, 15000),
                "request_rate": random.randint(100, 5000),
                "active_connections": random.randint(5, 120),
            },
            "queried_at": datetime.utcnow().isoformat(),
        }


# ── Diagnostic Tools ──────────────────────────────────────────────────────────

class DiagnosticAnalyzeIncidentTool(MCPTool):
    name = "diagnostic.analyze_incident"
    description = (
        "Analyze a production incident using Azure OpenAI GPT-4o. "
        "Returns structured root cause analysis with confidence score, "
        "affected services, and recommended remediation action."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "Incident identifier."},
            "service": {"type": "string", "description": "Affected service name."},
            "description": {"type": "string", "description": "Incident description."},
            "metrics_snapshot": {
                "type": "object",
                "description": "Current metrics snapshot dict.",
            },
        },
        "required": ["incident_id", "service", "description"],
    }

    async def execute(self, params: dict) -> dict:
        await asyncio.sleep(0.8)
        return {
            "incident_id": params.get("incident_id"),
            "root_cause": "Simulated root cause analysis from MCP tool",
            "confidence": 0.87,
            "severity": "high",
            "affected_services": [params.get("service", "unknown")],
            "recommended_action": "Apply the suggested fix and monitor for 10 minutes.",
            "analyzed_at": datetime.utcnow().isoformat(),
        }


class DiagnosticGetRootCauseTool(MCPTool):
    name = "diagnostic.get_root_cause"
    description = (
        "Get the previously determined root cause for an incident. "
        "Returns the stored Diagnosis object including confidence and evidence."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "Incident identifier."},
        },
        "required": ["incident_id"],
    }

    async def execute(self, params: dict) -> dict:
        await asyncio.sleep(0.1)
        return {
            "incident_id": params.get("incident_id"),
            "root_cause": "Retrieved from diagnosis store",
            "confidence": 0.90,
            "retrieved_at": datetime.utcnow().isoformat(),
        }


# ── Fixer Tools ───────────────────────────────────────────────────────────────

class FixerGeneratePatchTool(MCPTool):
    name = "fixer.generate_patch"
    description = (
        "Generate a production-safe code fix for a diagnosed incident using GPT-4o. "
        "Returns file path, original code, fixed code, and test suggestions."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "Incident identifier."},
            "root_cause": {"type": "string", "description": "Root cause from DiagnosticAgent."},
            "recommended_action": {
                "type": "string",
                "description": "Recommended action from DiagnosticAgent.",
            },
            "service": {"type": "string", "description": "Target service to fix."},
        },
        "required": ["incident_id", "root_cause"],
    }

    async def execute(self, params: dict) -> dict:
        await asyncio.sleep(0.6)
        return {
            "incident_id": params.get("incident_id"),
            "file_path": f"src/services/{params.get('service', 'unknown')}.ts",
            "description": "Auto-generated fix via MCP tool",
            "original_code": "// original code",
            "fixed_code": "// fixed code",
            "risk_level": "low",
            "test_suggestions": ["Unit test coverage", "Load test post-fix"],
            "generated_at": datetime.utcnow().isoformat(),
        }


class FixerValidateFixTool(MCPTool):
    name = "fixer.validate_fix"
    description = (
        "Validate that a generated fix is correct and safe to deploy. "
        "Runs static analysis, security scan, and code review heuristics."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "fix_id": {"type": "string", "description": "Fix identifier from generate_patch."},
            "file_path": {"type": "string", "description": "File that will be modified."},
            "fixed_code": {"type": "string", "description": "The proposed fixed code."},
        },
        "required": ["fix_id"],
    }

    async def execute(self, params: dict) -> dict:
        await asyncio.sleep(0.3)
        return {
            "fix_id": params.get("fix_id"),
            "valid": True,
            "security_scan": "passed",
            "static_analysis": "passed",
            "risk_assessment": "low",
            "validated_at": datetime.utcnow().isoformat(),
        }


# ── Deploy Tools ──────────────────────────────────────────────────────────────

class DeployExecuteDeploymentTool(MCPTool):
    name = "deploy.execute_deployment"
    description = (
        "Execute a rolling deployment of a validated fix to production. "
        "Runs test suite, pre-deploy validation, rolling rollout, and health checks."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "Incident identifier."},
            "fix_id": {"type": "string", "description": "Fix identifier to deploy."},
            "service": {"type": "string", "description": "Target service."},
            "strategy": {
                "type": "string",
                "enum": ["rolling", "blue_green", "canary"],
                "default": "rolling",
                "description": "Deployment strategy.",
            },
        },
        "required": ["incident_id", "fix_id"],
    }

    async def execute(self, params: dict) -> dict:
        await asyncio.sleep(1.0)
        return {
            "incident_id": params.get("incident_id"),
            "fix_id": params.get("fix_id"),
            "success": True,
            "deployed_version": f"v{random.randint(100, 999)}",
            "strategy": params.get("strategy", "rolling"),
            "deployed_at": datetime.utcnow().isoformat(),
        }


class DeployRollbackTool(MCPTool):
    name = "deploy.rollback"
    description = (
        "Rollback a failed deployment to the last known stable version. "
        "Executes graceful rollback with health check verification."
    )
    input_schema = {
        "type": "object",
        "properties": {
            "incident_id": {"type": "string", "description": "Incident identifier."},
            "service": {"type": "string", "description": "Service to rollback."},
            "reason": {"type": "string", "description": "Reason for rollback."},
        },
        "required": ["incident_id", "service"],
    }

    async def execute(self, params: dict) -> dict:
        await asyncio.sleep(0.5)
        return {
            "incident_id": params.get("incident_id"),
            "service": params.get("service"),
            "rolled_back_to": "previous-stable",
            "success": True,
            "rolled_back_at": datetime.utcnow().isoformat(),
        }


# ─── Registry ─────────────────────────────────────────────────────────────────

TOOL_REGISTRY: dict[str, MCPTool] = {
    t.name: t
    for t in [
        MonitorCheckHealthTool(),
        MonitorGetMetricsTool(),
        DiagnosticAnalyzeIncidentTool(),
        DiagnosticGetRootCauseTool(),
        FixerGeneratePatchTool(),
        FixerValidateFixTool(),
        DeployExecuteDeploymentTool(),
        DeployRollbackTool(),
    ]
}
