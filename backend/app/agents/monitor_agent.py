import asyncio
import random
import logging
from datetime import datetime, timedelta
from typing import Optional

from ..models.incident import Incident, IncidentSeverity
from ..models.agent_messages import AgentStatus

logger = logging.getLogger(__name__)

MOCK_SERVICES = [
    "payment-service",
    "auth-service",
    "user-service",
    "recommendation-service",
    "notification-service",
    "k8s-cluster",
]

ANOMALY_SCENARIOS = [
    {
        "type": "cpu_spike",
        "description": "CPU usage exceeding 95% threshold",
        "severity": IncidentSeverity.CRITICAL,
        "metrics": {"cpu_percent": 97.3, "memory_percent": 68.0, "error_rate": 0.12},
    },
    {
        "type": "memory_leak",
        "description": "Memory growing unbounded, potential leak detected",
        "severity": IncidentSeverity.HIGH,
        "metrics": {"cpu_percent": 45.0, "memory_percent": 91.5, "error_rate": 0.08},
    },
    {
        "type": "high_error_rate",
        "description": "Error rate spiked above 30% (threshold: 5%)",
        "severity": IncidentSeverity.HIGH,
        "metrics": {"cpu_percent": 62.0, "memory_percent": 55.0, "error_rate": 0.38},
    },
    {
        "type": "latency_spike",
        "description": "P99 latency exceeded 10 seconds (threshold: 2s)",
        "severity": IncidentSeverity.MEDIUM,
        "metrics": {"cpu_percent": 78.0, "memory_percent": 70.0, "error_rate": 0.15, "latency_p99_ms": 12500},
    },
    {
        "type": "connection_pool_exhausted",
        "description": "Database connection pool at 100% capacity",
        "severity": IncidentSeverity.HIGH,
        "metrics": {"cpu_percent": 55.0, "memory_percent": 80.0, "error_rate": 0.22, "db_connections": 100},
    },
]


class MonitorAgent:
    def __init__(self, agent_status: AgentStatus):
        self.name = "monitor"
        self.status = agent_status
        self._polling_interval = 30  # seconds in real mode

    def _set_working(self, task: str):
        self.status.status = "working"
        self.status.current_task = task
        self.status.last_action = task
        self.status.last_action_time = datetime.utcnow()

    def _set_idle(self):
        self.status.status = "idle"
        self.status.current_task = None

    async def check_pipeline_status(self) -> dict:
        """Simulate checking Azure Monitor pipeline status."""
        self._set_working("Checking pipeline status")
        await asyncio.sleep(0.5)

        pipeline_data = {
            "timestamp": datetime.utcnow().isoformat(),
            "pipelines": [],
        }

        for service in MOCK_SERVICES:
            cpu = random.uniform(10, 99)
            memory = random.uniform(20, 95)
            error_rate = random.uniform(0, 0.5)
            latency = random.uniform(50, 15000)

            pipeline_data["pipelines"].append({
                "service": service,
                "status": "healthy" if cpu < 80 and error_rate < 0.1 else "degraded",
                "cpu_percent": round(cpu, 1),
                "memory_percent": round(memory, 1),
                "error_rate": round(error_rate, 3),
                "latency_p99_ms": round(latency, 0),
                "last_deploy": (datetime.utcnow() - timedelta(hours=random.randint(1, 72))).isoformat(),
            })

        logger.info(f"MonitorAgent: Checked {len(pipeline_data['pipelines'])} pipelines")
        return pipeline_data

    async def analyze_metrics(self, pipeline_data: dict) -> Optional[dict]:
        """Detect anomalies in the collected metrics."""
        self._set_working("Analyzing metrics for anomalies")
        await asyncio.sleep(0.3)

        anomalies = []
        for pipeline in pipeline_data.get("pipelines", []):
            issues = []
            if pipeline["cpu_percent"] > 90:
                issues.append(f"CPU at {pipeline['cpu_percent']}%")
            if pipeline["memory_percent"] > 88:
                issues.append(f"Memory at {pipeline['memory_percent']}%")
            if pipeline["error_rate"] > 0.2:
                issues.append(f"Error rate at {pipeline['error_rate']*100:.1f}%")
            if pipeline.get("latency_p99_ms", 0) > 5000:
                issues.append(f"P99 latency at {pipeline['latency_p99_ms']}ms")

            if issues:
                anomalies.append({
                    "service": pipeline["service"],
                    "issues": issues,
                    "metrics": pipeline,
                })

        if anomalies:
            logger.warning(f"MonitorAgent: Detected {len(anomalies)} anomalies")
            return {"anomalies": anomalies, "count": len(anomalies)}

        return None

    async def create_incident(self, service: str, description: str, severity: IncidentSeverity, metrics: dict) -> Incident:
        """Create a structured incident from detected anomaly."""
        self._set_working(f"Creating incident for {service}")
        await asyncio.sleep(0.2)

        title_map = {
            IncidentSeverity.CRITICAL: f"[CRITICAL] {service} - {description[:40]}",
            IncidentSeverity.HIGH: f"[HIGH] {service} - {description[:40]}",
            IncidentSeverity.MEDIUM: f"[MEDIUM] {service} - {description[:40]}",
            IncidentSeverity.LOW: f"[LOW] {service} - {description[:40]}",
        }

        incident = Incident(
            title=title_map[severity],
            description=description,
            severity=severity,
            service=service,
            metrics_snapshot=metrics,
            error_count=int(metrics.get("error_rate", 0.1) * random.randint(500, 5000)),
            affected_users=random.randint(50, 2000) if severity in [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH] else random.randint(0, 200),
        )

        incident.add_timeline_event(
            agent=self.name,
            action="Anomaly Detected",
            details=f"Monitoring detected: {description}. Metrics: CPU={metrics.get('cpu_percent', 'N/A')}%, Memory={metrics.get('memory_percent', 'N/A')}%, ErrorRate={metrics.get('error_rate', 'N/A')}",
            status="warning",
        )

        self.status.incidents_handled += 1
        self._set_idle()
        logger.info(f"MonitorAgent: Created incident {incident.id} for {service}")
        return incident

    async def run_simulation(self) -> Incident:
        """Run a full simulated monitoring cycle and return an incident."""
        scenario = random.choice(ANOMALY_SCENARIOS)
        service = random.choice(MOCK_SERVICES)

        incident = await self.create_incident(
            service=service,
            description=scenario["description"],
            severity=scenario["severity"],
            metrics=scenario["metrics"],
        )
        return incident
