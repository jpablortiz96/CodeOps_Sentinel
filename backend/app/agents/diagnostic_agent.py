import asyncio
import random
import logging
from datetime import datetime
from typing import Optional

from ..models.incident import Incident, IncidentSeverity, Diagnosis
from ..models.agent_messages import AgentStatus

logger = logging.getLogger(__name__)

ROOT_CAUSE_TEMPLATES = {
    "cpu_spike": {
        "root_cause": "Unbounded loop in request handler causing CPU saturation. N+1 query pattern detected in ORM layer generating thousands of micro-queries per request.",
        "affected_services": ["database", "cache"],
        "recommended_action": "Optimize ORM queries with eager loading (select_related/prefetch_related). Add query result caching with Redis TTL 300s.",
        "error_pattern": "SELECT * FROM orders WHERE user_id = %s (called 847 times in single request)",
    },
    "memory_leak": {
        "root_cause": "Event listener not being cleaned up on component unmount. Large objects retained in closure scope preventing garbage collection.",
        "affected_services": ["monitoring", "alerting"],
        "recommended_action": "Add cleanup in useEffect return function. Use WeakMap for caching to allow GC. Implement circuit breaker for long-running operations.",
        "error_pattern": "EventEmitter memory leak detected: 11 listeners added (max 10)",
    },
    "high_error_rate": {
        "root_cause": "Downstream dependency (Redis cache) returning ECONNREFUSED. Service lacks circuit breaker pattern causing cascading failures.",
        "affected_services": ["redis", "session-store"],
        "recommended_action": "Implement circuit breaker with fallback to database. Add health check endpoints for all dependencies. Configure retry with exponential backoff.",
        "error_pattern": "Error: connect ECONNREFUSED 10.0.1.45:6379 (repeated 342 times/min)",
    },
    "latency_spike": {
        "root_cause": "Missing database index on frequently queried column (user_id in transactions table). Full table scan on 12M+ row table.",
        "affected_services": ["postgresql", "api-gateway"],
        "recommended_action": "Add composite index: CREATE INDEX CONCURRENTLY idx_transactions_user_date ON transactions(user_id, created_at DESC). Review EXPLAIN ANALYZE output.",
        "error_pattern": "Seq Scan on transactions (cost=0.00..234891.00 rows=12450123 width=156)",
    },
    "connection_pool_exhausted": {
        "root_cause": "Long-running transactions not releasing connections. Default pool size (20) insufficient for current load. Deadlock detected in payment processing.",
        "affected_services": ["postgresql", "payment-processor"],
        "recommended_action": "Increase connection pool to 50. Set statement_timeout=30s. Implement connection pool monitoring. Review transaction isolation levels.",
        "error_pattern": "FATAL: remaining connection slots are reserved for non-replication superuser connections",
    },
}

GENERIC_ROOT_CAUSES = [
    "Resource exhaustion due to unoptimized query patterns and missing cache invalidation strategy",
    "Race condition in concurrent request handling causing data inconsistency and service degradation",
    "Configuration drift between environment versions causing unexpected behavior in production",
    "Cascading failure from upstream service timeout propagating through the service mesh",
]

MOCK_LOG_EVIDENCE = [
    "2024-01-15 14:23:11 ERROR [payment-service] Unhandled exception in /api/v2/process\n  at processPayment (payment.service.ts:142)\n  Caused by: TimeoutError: Database query exceeded 30000ms",
    "2024-01-15 14:23:15 WARN  [auth-service] Memory usage at 91.5% (threshold: 85%)\n  Heap used: 7.3GB / 8GB\n  GC pressure: HIGH (12 major collections in last 60s)",
    "2024-01-15 14:23:18 ERROR [k8s] Pod crash loop: payment-service-7d9f8b-xkp2q\n  Reason: OOMKilled\n  Last exit code: 137",
    "2024-01-15 14:23:22 CRITICAL [api-gateway] Circuit breaker OPEN for user-service\n  Failure rate: 67% (threshold: 50%)\n  Consecutive failures: 23",
]


class DiagnosticAgent:
    def __init__(self, agent_status: AgentStatus):
        self.name = "diagnostic"
        self.status = agent_status

    def _set_working(self, task: str):
        self.status.status = "working"
        self.status.current_task = task
        self.status.last_action = task
        self.status.last_action_time = datetime.utcnow()

    def _set_idle(self):
        self.status.status = "idle"
        self.status.current_task = None

    def _infer_scenario(self, incident: Incident) -> str:
        metrics = incident.metrics_snapshot
        desc = incident.description.lower()

        if "cpu" in desc or metrics.get("cpu_percent", 0) > 90:
            return "cpu_spike"
        if "memory" in desc or metrics.get("memory_percent", 0) > 88:
            return "memory_leak"
        if "error" in desc or metrics.get("error_rate", 0) > 0.25:
            return "high_error_rate"
        if "latency" in desc or "slow" in desc or metrics.get("latency_p99_ms", 0) > 5000:
            return "latency_spike"
        if "connection" in desc or "pool" in desc:
            return "connection_pool_exhausted"
        return "high_error_rate"  # default

    async def diagnose(self, incident: Incident) -> Diagnosis:
        """Analyze incident and determine root cause using AI (simulated)."""
        self._set_working(f"Analyzing {incident.id}")

        incident.add_timeline_event(
            agent=self.name,
            action="Log Analysis Started",
            details=f"Fetching logs from {incident.service} for last 15 minutes. Correlating with metrics snapshots.",
            status="info",
        )
        await asyncio.sleep(1.0)

        incident.add_timeline_event(
            agent=self.name,
            action="Querying Azure Monitor",
            details=f"Running KQL query against Log Analytics workspace. Analyzing {random.randint(10000, 50000)} log entries.",
            status="info",
        )
        await asyncio.sleep(0.8)

        scenario = self._infer_scenario(incident)
        template = ROOT_CAUSE_TEMPLATES.get(scenario, {
            "root_cause": random.choice(GENERIC_ROOT_CAUSES),
            "affected_services": [incident.service],
            "recommended_action": "Investigate service logs and apply appropriate patch",
            "error_pattern": None,
        })

        incident.add_timeline_event(
            agent=self.name,
            action="Azure OpenAI Analysis",
            details=f"Sending context to GPT-4o for root cause analysis. Pattern: '{template.get('error_pattern', 'N/A')}'",
            status="info",
        )
        await asyncio.sleep(1.2)

        confidence = random.uniform(0.78, 0.97)
        diagnosis = Diagnosis(
            root_cause=template["root_cause"],
            severity=incident.severity,
            affected_services=template["affected_services"],
            recommended_action=template["recommended_action"],
            confidence=round(confidence, 2),
            error_pattern=template.get("error_pattern"),
            log_evidence=random.choice(MOCK_LOG_EVIDENCE),
        )

        incident.diagnosis = diagnosis
        incident.add_timeline_event(
            agent=self.name,
            action="Root Cause Identified",
            details=f"Confidence: {confidence:.0%}. Root cause: {diagnosis.root_cause[:100]}...",
            status="success",
        )

        self.status.incidents_handled += 1
        self._set_idle()
        logger.info(f"DiagnosticAgent: Diagnosed {incident.id} - {scenario} (confidence: {confidence:.0%})")
        return diagnosis
