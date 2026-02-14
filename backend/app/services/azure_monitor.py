"""
Azure Monitor integration service.
In simulation mode, returns realistic mock data.
In production, uses azure-monitor-query SDK.
"""
import logging
import random
from datetime import datetime, timedelta
from typing import Optional

from ..config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class AzureMonitorService:
    def __init__(self):
        self.subscription_id = settings.AZURE_SUBSCRIPTION_ID
        self.resource_group = settings.AZURE_RESOURCE_GROUP
        self.workspace_id = settings.AZURE_MONITOR_WORKSPACE
        self._simulation = settings.SIMULATION_MODE

    async def query_metrics(self, resource_id: str, metric_names: list, timespan_minutes: int = 15) -> dict:
        """Query Azure Monitor metrics for a resource."""
        if self._simulation:
            return self._mock_metrics(resource_id, metric_names, timespan_minutes)

        # Real implementation would use azure-monitor-query SDK
        try:
            from azure.identity import DefaultAzureCredential
            from azure.monitor.query import MetricsQueryClient
            # ... real implementation
        except ImportError:
            logger.warning("azure-monitor-query not available, using simulation")
            return self._mock_metrics(resource_id, metric_names, timespan_minutes)

    async def run_kql_query(self, workspace_id: str, query: str, timespan_hours: int = 1) -> list:
        """Run a KQL query against Log Analytics workspace."""
        if self._simulation:
            return self._mock_log_results(query)

        try:
            from azure.identity import DefaultAzureCredential
            from azure.monitor.query import LogsQueryClient
            # ... real implementation
        except ImportError:
            return self._mock_log_results(query)

    async def get_active_alerts(self, severity: Optional[str] = None) -> list:
        """Get active Azure Monitor alerts."""
        if self._simulation:
            return self._mock_alerts(severity)
        return []

    def _mock_metrics(self, resource_id: str, metric_names: list, timespan_minutes: int) -> dict:
        """Generate realistic mock metric data."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=timespan_minutes)
        interval_count = min(timespan_minutes, 30)

        metrics = {}
        for metric in metric_names:
            base_value = {
                "Percentage CPU": random.uniform(60, 98),
                "Available Memory Bytes": random.uniform(500_000_000, 2_000_000_000),
                "Http5xx": random.uniform(0, 50),
                "RequestsPerSecond": random.uniform(100, 5000),
                "ResponseTime": random.uniform(0.1, 12.5),
            }.get(metric, random.uniform(0, 100))

            timeseries = []
            for i in range(interval_count):
                ts = start_time + timedelta(minutes=i * (timespan_minutes // interval_count))
                noise = random.uniform(-5, 5)
                timeseries.append({
                    "timestamp": ts.isoformat(),
                    "average": round(base_value + noise, 2),
                    "maximum": round(base_value + abs(noise) + 3, 2),
                    "minimum": round(base_value - abs(noise), 2),
                })

            metrics[metric] = {
                "unit": "Percent" if "Percentage" in metric else "Count",
                "timeseries": timeseries,
                "current": round(base_value, 2),
            }

        return {
            "resource_id": resource_id,
            "timespan": f"{start_time.isoformat()}/{end_time.isoformat()}",
            "metrics": metrics,
        }

    def _mock_log_results(self, query: str) -> list:
        """Generate mock KQL query results."""
        return [
            {
                "TimeGenerated": (datetime.utcnow() - timedelta(minutes=random.randint(1, 15))).isoformat(),
                "Level": random.choice(["ERROR", "ERROR", "WARNING", "CRITICAL"]),
                "ServiceName": "payment-service",
                "Message": random.choice([
                    "Unhandled exception in payment processor",
                    "Connection timeout to downstream service",
                    "Memory threshold exceeded: 91.5%",
                    "Circuit breaker triggered for auth-service",
                    "Database query exceeded 30000ms",
                ]),
                "Count": random.randint(10, 500),
            }
            for _ in range(random.randint(5, 15))
        ]

    def _mock_alerts(self, severity: Optional[str] = None) -> list:
        alerts = [
            {
                "id": "alert-001",
                "name": "High CPU Alert",
                "severity": "critical",
                "service": "payment-service",
                "fired_at": (datetime.utcnow() - timedelta(minutes=3)).isoformat(),
                "condition": "CPU > 95% for 5 minutes",
            },
            {
                "id": "alert-002",
                "name": "Memory Pressure Alert",
                "severity": "high",
                "service": "auth-service",
                "fired_at": (datetime.utcnow() - timedelta(minutes=8)).isoformat(),
                "condition": "Available memory < 512MB",
            },
        ]
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        return alerts
