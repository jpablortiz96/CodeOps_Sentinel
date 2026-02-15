"""
MonitorAgent — Detects production anomalies via Azure Monitor.

Includes 8 realistic incident scenarios with production-grade mock logs,
trace IDs, and service topology context that feed directly into the
DiagnosticAgent's GPT-4o context.

Also polls the real ShopDemo app health endpoint every
MONITORING_INTERVAL_SECONDS and fires incidents automatically when
anomalies are detected.
"""
import asyncio
import random
import logging
from collections import deque
from datetime import datetime, timedelta
from typing import Optional

import httpx

from config import get_settings
from models.incident import Incident, IncidentSeverity
from models.agent_messages import AgentStatus

settings = get_settings()

logger = logging.getLogger(__name__)

# ─── Real-time metric history (last 60 readings ≈ 10 min at 10 s interval) ────
metric_history: deque = deque(maxlen=60)

# ─── Real demo-app polling ─────────────────────────────────────────────────────

async def poll_demo_app() -> Optional[dict]:
    """
    Fetch /health from the real ShopDemo app.
    Returns the parsed JSON or None on network error.
    """
    url = f"{settings.DEMO_APP_URL}/health"
    try:
        async with httpx.AsyncClient(timeout=8.0) as client:
            resp = await client.get(url)
            resp.raise_for_status()
            data = resp.json()
            data["_polled_at"] = datetime.utcnow().isoformat()
            metric_history.append(data)
            return data
    except Exception as exc:
        logger.warning(f"[MONITOR] poll_demo_app failed: {exc}")
        return None


def classify_demo_health(health: dict) -> Optional[dict]:
    """
    Compare health snapshot against configured thresholds.
    Returns an anomaly dict if any threshold is breached, else None.
    """
    mem   = health.get("memory_usage_mb", 0)
    cpu   = health.get("cpu_percent", 0)
    err   = health.get("error_rate", 0)          # already in %
    lat   = health.get("avg_latency_ms", 0)
    chaos = health.get("active_chaos", [])
    status = health.get("status", "healthy")

    if status == "healthy":
        return None

    issues = []
    severity = IncidentSeverity.LOW

    if mem > settings.ALERT_MEMORY_MB_CRITICAL:
        issues.append(f"memory {mem:.0f} MB > {settings.ALERT_MEMORY_MB_CRITICAL:.0f} MB")
        severity = IncidentSeverity.CRITICAL
    elif mem > settings.ALERT_MEMORY_MB_DEGRADED:
        issues.append(f"memory {mem:.0f} MB elevated")
        severity = max(severity, IncidentSeverity.HIGH, key=lambda s: ["low","medium","high","critical"].index(s))

    if cpu > settings.ALERT_CPU_PERCENT_CRITICAL:
        issues.append(f"CPU {cpu:.0f}% > {settings.ALERT_CPU_PERCENT_CRITICAL:.0f}%")
        severity = IncidentSeverity.CRITICAL
    elif cpu > settings.ALERT_CPU_PERCENT_DEGRADED:
        issues.append(f"CPU {cpu:.0f}% elevated")

    err_frac = err / 100.0  # health endpoint returns %, thresholds use fraction
    if err_frac > settings.ALERT_ERROR_RATE_CRITICAL:
        issues.append(f"error rate {err:.1f}% > {settings.ALERT_ERROR_RATE_CRITICAL*100:.0f}%")
        severity = IncidentSeverity.CRITICAL
    elif err_frac > settings.ALERT_ERROR_RATE_DEGRADED:
        issues.append(f"error rate {err:.1f}% elevated")
        if severity == IncidentSeverity.LOW:
            severity = IncidentSeverity.HIGH

    if lat > settings.ALERT_LATENCY_MS_CRITICAL:
        issues.append(f"latency {lat:.0f} ms > {settings.ALERT_LATENCY_MS_CRITICAL:.0f} ms")
        if severity == IncidentSeverity.LOW:
            severity = IncidentSeverity.HIGH
    elif lat > settings.ALERT_LATENCY_MS_DEGRADED:
        issues.append(f"latency {lat:.0f} ms elevated")

    if chaos:
        issues.append(f"active chaos: {', '.join(chaos)}")

    if not issues:
        return None

    return {
        "severity":    severity,
        "issues":      issues,
        "chaos":       chaos,
        "metrics": {
            "memory_usage_mb": mem,
            "cpu_percent":     cpu,
            "error_rate":      err_frac,
            "avg_latency_ms":  lat,
            "status":          status,
        },
    }

MOCK_SERVICES = [
    "payment-service",
    "auth-service",
    "user-service",
    "recommendation-service",
    "notification-service",
    "k8s-cluster",
    "api-gateway",
    "order-service",
]

# ─── Incident Scenarios ───────────────────────────────────────────────────────
# Each scenario includes realistic mock logs with timestamps, trace IDs,
# stack traces, and service names — exactly as they'd appear in production.

ANOMALY_SCENARIOS = [
    # ── 1. CPU Spike / N+1 queries ────────────────────────────────────────────
    {
        "type": "cpu_spike",
        "title": "CPU Saturation — Payment Service",
        "description": "CPU usage exceeding 97% threshold for 5 consecutive minutes. Request queue depth growing.",
        "severity": IncidentSeverity.CRITICAL,
        "service": "payment-service",
        "affected_users": 1250,
        "error_count": 342,
        "metrics": {
            "cpu_percent": 97.3,
            "memory_percent": 68.0,
            "error_rate": 0.12,
            "latency_p99_ms": 8200,
            "request_rate": 4850,
        },
        "mock_logs": (
            "2024-01-15T14:23:09.112Z INFO  [payment-service] [trace=8f3a2b1c] GET /api/v2/orders/process started\n"
            "2024-01-15T14:23:09.118Z DEBUG [payment-service] [trace=8f3a2b1c] ORM query: SELECT * FROM orders WHERE user_id='usr_4421' (1/847)\n"
            "2024-01-15T14:23:09.245Z DEBUG [payment-service] [trace=8f3a2b1c] ORM query: SELECT * FROM order_items WHERE order_id='ord_1001' (2/847)\n"
            "2024-01-15T14:23:09.312Z DEBUG [payment-service] [trace=8f3a2b1c] ORM query: SELECT * FROM order_items WHERE order_id='ord_1002' (3/847)\n"
            "2024-01-15T14:23:10.891Z WARN  [payment-service] DB query budget exceeded: 847 queries in 1.78s (budget=10)\n"
            "2024-01-15T14:23:11.003Z ERROR [payment-service] [trace=8f3a2b1c] Request timeout after 8200ms\n"
            "  at PaymentController.processOrder (payment.controller.ts:89)\n"
            "  at OrderService.getOrdersWithItems (order.service.ts:142)\n"
            "  Caused by: QueryBudgetExceededError: 847 queries executed (max: 10)\n"
            "2024-01-15T14:23:11.450Z WARN  [payment-service] CPU utilization: 97.3% (threshold: 80%)\n"
            "2024-01-15T14:23:11.890Z ERROR [k8s/payment-service] HPA: scaling event triggered (cpu=97.3% > 70%)\n"
            "2024-01-15T14:23:12.100Z INFO  [payment-service] Active connections: 284/300 (94.7% pool utilization)"
        ),
    },

    # ── 2. Memory Leak ────────────────────────────────────────────────────────
    {
        "type": "memory_leak",
        "title": "Memory Leak — Auth Service Heap Growth",
        "description": "Auth service heap growing unbounded at ~50MB/hour. OOMKill imminent in ~10 minutes.",
        "severity": IncidentSeverity.HIGH,
        "service": "auth-service",
        "affected_users": 430,
        "error_count": 87,
        "metrics": {
            "cpu_percent": 45.0,
            "memory_percent": 91.5,
            "error_rate": 0.08,
            "latency_p99_ms": 1200,
            "request_rate": 1200,
        },
        "mock_logs": (
            "2024-01-15T14:23:14.001Z INFO  [auth-service] Heap snapshot: used=7.3GB/8GB (91.5%)\n"
            "2024-01-15T14:23:14.220Z WARN  [auth-service] MaxListenersExceededWarning: Possible EventEmitter memory leak detected. 11 sessionUpdate listeners added to [WebSocketServer]. Use emitter.setMaxListeners() to increase limit\n"
            "2024-01-15T14:23:14.445Z WARN  [auth-service] GC pressure HIGH: 12 major collections in last 60s (normal: <3)\n"
            "2024-01-15T14:23:15.012Z DEBUG [auth-service] Active WebSocket connections: 8,432 (peak today)\n"
            "2024-01-15T14:23:15.230Z WARN  [auth-service] Memory growth rate: +52MB/hour (threshold: +10MB/hour)\n"
            "2024-01-15T14:23:15.556Z ERROR [auth-service] [trace=2d9f8a3e] JWT validation failed — heap allocation error\n"
            "  at SessionManager.validateToken (session.manager.ts:67)\n"
            "  at AuthMiddleware.verify (auth.middleware.ts:23)\n"
            "  Caused by: AllocationError: JavaScript heap out of memory\n"
            "2024-01-15T14:23:15.891Z INFO  [auth-service] Listener counts: sessionUpdate=11, tokenRefresh=9, disconnect=8\n"
            "2024-01-15T14:23:16.100Z CRIT  [k8s/auth-service] Pod auth-service-6f7b9d-qw3rt: memory=7.3GB/8GB limit — OOMKill predicted in ~10min"
        ),
    },

    # ── 3. High Error Rate / Circuit Breaker ──────────────────────────────────
    {
        "type": "high_error_rate",
        "title": "Circuit Breaker Open — API Gateway 502 Spike",
        "description": "API Gateway error rate spiked to 38% (threshold: 5%). Redis ECONNREFUSED cascading to all endpoints.",
        "severity": IncidentSeverity.HIGH,
        "service": "api-gateway",
        "affected_users": 890,
        "error_count": 2341,
        "metrics": {
            "cpu_percent": 62.0,
            "memory_percent": 55.0,
            "error_rate": 0.38,
            "latency_p99_ms": 5100,
            "request_rate": 3200,
        },
        "mock_logs": (
            "2024-01-15T14:23:18.001Z ERROR [api-gateway] [trace=9c4e7f2a] Redis connection refused: connect ECONNREFUSED 10.0.1.45:6379\n"
            "2024-01-15T14:23:18.045Z ERROR [api-gateway] [trace=9c4e7f2b] Redis connection refused: connect ECONNREFUSED 10.0.1.45:6379\n"
            "2024-01-15T14:23:18.102Z WARN  [api-gateway] Circuit breaker [redis-cache]: failure_count=10/10 — OPENING\n"
            "2024-01-15T14:23:18.230Z ERROR [api-gateway] [trace=9c4e7f2c] 502 Bad Gateway: upstream user-service returned 503\n"
            "2024-01-15T14:23:18.445Z WARN  [api-gateway] Circuit breaker [user-service]: OPEN (67% failure rate, threshold: 50%)\n"
            "2024-01-15T14:23:18.667Z ERROR [api-gateway] Error rate: 38.2% (1,218 errors in last 60s)\n"
            "2024-01-15T14:23:18.891Z INFO  [api-gateway] No fallback configured for /api/v2/users/** — returning 502\n"
            "2024-01-15T14:23:19.120Z WARN  [redis] sentinel-1: master-down: NOAUTH Authentication required\n"
            "2024-01-15T14:23:19.334Z ERROR [api-gateway] SLA breach: error_rate=38% (SLA limit: 0.1%)\n"
            "2024-01-15T14:23:19.556Z WARN  [pagerduty] High severity alert fired: API-GW-502-SPIKE (consecutive_failures=23)"
        ),
    },

    # ── 4. Database Latency / Missing Index ───────────────────────────────────
    {
        "type": "latency_spike",
        "title": "P99 Latency 12s — Missing DB Index (Recommendations)",
        "description": "P99 latency spiked from 180ms to 12.5s. PostgreSQL sequential scan on 12.4M-row table.",
        "severity": IncidentSeverity.MEDIUM,
        "service": "recommendation-service",
        "affected_users": 320,
        "error_count": 45,
        "metrics": {
            "cpu_percent": 78.0,
            "memory_percent": 70.0,
            "error_rate": 0.15,
            "latency_p99_ms": 12500,
            "request_rate": 950,
        },
        "mock_logs": (
            "2024-01-15T14:23:21.001Z SLOW [recommendation-db] query_duration=11823ms threshold=2000ms\n"
            "  Query: SELECT r.*, u.preferences FROM recommendations r JOIN users u ON r.user_id=u.id WHERE r.user_id='usr_8821' ORDER BY r.score DESC LIMIT 20\n"
            "  Plan: Seq Scan on recommendations (cost=0.00..234891.23 rows=12450000 width=156)\n"
            "        Filter: (user_id = 'usr_8821')\n"
            "        Rows removed by filter: 12449981\n"
            "2024-01-15T14:23:21.450Z WARN  [recommendation-service] SLO breach: p99_latency=12500ms (SLO: 2000ms)\n"
            "2024-01-15T14:23:22.001Z ERROR [recommendation-service] [trace=5b8d1e4f] Request timeout: GET /api/v2/recommendations/usr_8821\n"
            "2024-01-15T14:23:22.234Z INFO  [postgresql] pg_stat_activity: 12 long-running queries (>10s) on recommendations table\n"
            "2024-01-15T14:23:22.556Z WARN  [recommendation-service] Connection pool: 18/20 connections in use (90%)\n"
            "2024-01-15T14:23:22.891Z INFO  [postgresql] Table bloat: recommendations = 12,450,123 rows, last VACUUM: 14 days ago\n"
            "2024-01-15T14:23:23.100Z WARN  [postgresql] Missing index detected by pg_stat_user_tables: seq_scan=8,432 (today)"
        ),
    },

    # ── 5. Connection Pool Exhausted ──────────────────────────────────────────
    {
        "type": "connection_pool_exhausted",
        "title": "DB Connection Pool Exhausted — User Service",
        "description": "PostgreSQL connection pool at 100% capacity. Queries queuing, deadlock detected in payment processing.",
        "severity": IncidentSeverity.HIGH,
        "service": "user-service",
        "affected_users": 890,
        "error_count": 156,
        "metrics": {
            "cpu_percent": 55.0,
            "memory_percent": 80.0,
            "error_rate": 0.22,
            "db_connections": 100,
            "latency_p99_ms": 6400,
        },
        "mock_logs": (
            "2024-01-15T14:23:25.001Z ERROR [user-service] [trace=3a7c9f2e] FATAL: remaining connection slots are reserved for non-replication superuser connections\n"
            "2024-01-15T14:23:25.112Z ERROR [postgresql] max_connections=100 active_connections=100 (100%)\n"
            "2024-01-15T14:23:25.334Z WARN  [user-service] Connection pool: timed out waiting for connection (30000ms)\n"
            "  at PoolManager.acquire (pool.manager.ts:89)\n"
            "  at UserRepository.findById (user.repository.ts:45)\n"
            "2024-01-15T14:23:25.556Z ERROR [postgresql] deadlock detected\n"
            "  Process 12847 waits for ShareLock on transaction 98234; blocked by process 13021\n"
            "  Process 13021 waits for ShareLock on transaction 98235; blocked by process 12847\n"
            "2024-01-15T14:23:25.891Z WARN  [user-service] Long-running transactions: 8 queries >30s\n"
            "  Oldest: SELECT FOR UPDATE on users (47s) — pid=12847\n"
            "2024-01-15T14:23:26.100Z INFO  [user-service] Pool stats: size=20 active=20 idle=0 waiting=34\n"
            "2024-01-15T14:23:26.334Z WARN  [postgresql] pg_locks: 8 deadlock candidates detected"
        ),
    },

    # ── 6. Kubernetes CrashLoopBackOff / OOMKilled ────────────────────────────
    {
        "type": "k8s_crashloop",
        "title": "CrashLoopBackOff — API Gateway OOMKilled (exit 137)",
        "description": "API Gateway pod in CrashLoopBackOff. OOMKilled 8 times in 20 minutes. Memory limit 512Mi insufficient.",
        "severity": IncidentSeverity.CRITICAL,
        "service": "api-gateway",
        "affected_users": 3200,
        "error_count": 890,
        "metrics": {
            "cpu_percent": 42.0,
            "memory_percent": 99.8,
            "error_rate": 0.45,
            "latency_p99_ms": 15000,
            "restart_count": 8,
            "last_exit_code": 137,
        },
        "mock_logs": (
            "2024-01-15T14:21:03.001Z INFO  [k8s] Pod api-gateway-7d9f8b-xkp2q started (restart #8)\n"
            "2024-01-15T14:21:45.334Z WARN  [api-gateway] Memory usage: 498Mi/512Mi (97.3%)\n"
            "2024-01-15T14:21:58.556Z WARN  [api-gateway] Response buffer accumulation: 42 large responses buffered (>1MB each)\n"
            "2024-01-15T14:22:01.891Z CRIT  [api-gateway] Memory usage: 511Mi/512Mi (99.8%) — approaching OOM limit\n"
            "2024-01-15T14:22:02.002Z      [k8s] OOMKilling container api-gateway in pod api-gateway-7d9f8b-xkp2q\n"
            "2024-01-15T14:22:02.003Z      [k8s] Pod api-gateway-7d9f8b-xkp2q: container api-gateway terminated\n"
            "                                    Reason: OOMKilled\n"
            "                                    Exit Code: 137 (SIGKILL)\n"
            "                                    Last State: Terminated\n"
            "2024-01-15T14:22:02.550Z WARN  [k8s] Pod api-gateway-7d9f8b-xkp2q: RestartCount=8 BackoffLimit approaching\n"
            "2024-01-15T14:22:08.001Z INFO  [k8s] Pod api-gateway-7d9f8b-xkp2q: CrashLoopBackOff (next restart in 160s)\n"
            "2024-01-15T14:23:18.112Z WARN  [k8s] Deployment api-gateway: Available=1/3 Ready=1/3 (SLA breach)\n"
            "2024-01-15T14:23:18.334Z INFO  [k8s] Events: 8× OOMKilled in 20min — memory limit=512Mi insufficient for workload"
        ),
    },

    # ── 7. API Gateway 502 Spike / Upstream Timeout ───────────────────────────
    {
        "type": "api_gateway_502",
        "title": "502 Bad Gateway Spike — Upstream Service Timeout",
        "description": "API Gateway returning 502 for 35% of requests. Upstream order-service timeouts cascading.",
        "severity": IncidentSeverity.HIGH,
        "service": "api-gateway",
        "affected_users": 1800,
        "error_count": 4230,
        "metrics": {
            "cpu_percent": 58.0,
            "memory_percent": 62.0,
            "error_rate": 0.35,
            "latency_p99_ms": 30000,
            "request_rate": 2800,
        },
        "mock_logs": (
            "2024-01-15T14:23:30.001Z ERROR [api-gateway] [trace=6e2a9d4c] upstream timed out (30000ms) while reading response header from upstream, upstream: http://order-service:8080\n"
            "2024-01-15T14:23:30.112Z ERROR [api-gateway] [trace=6e2a9d4d] 502 Bad Gateway: order-service health check failing\n"
            "2024-01-15T14:23:30.334Z WARN  [api-gateway] Upstream: order-service — consecutive_failures=15 (circuit_breaker: HALF_OPEN)\n"
            "2024-01-15T14:23:30.556Z ERROR [order-service] [trace=6e2a9d4c] Thread pool exhausted: java.util.concurrent.RejectedExecutionException\n"
            "  at com.company.orders.OrderService.processOrder(OrderService.java:234)\n"
            "  at com.company.orders.OrderController.handleRequest(OrderController.java:89)\n"
            "2024-01-15T14:23:30.891Z WARN  [order-service] Thread pool: active=200/200 queue=1,847 rejected=342\n"
            "2024-01-15T14:23:31.001Z INFO  [order-service] Thread pool metrics: pool_size=200 core_size=50 max_size=200\n"
            "2024-01-15T14:23:31.230Z WARN  [api-gateway] 502 rate: 35.2% (987 errors/last 60s)\n"
            "2024-01-15T14:23:31.445Z ERROR [api-gateway] SLA breach: availability=64.8% (SLA: 99.9%)\n"
            "2024-01-15T14:23:31.667Z CRIT  [pagerduty] P1 incident: API-GW-502-CASCADE — all order endpoints affected"
        ),
    },

    # ── 8. Database Replication Lag ───────────────────────────────────────────
    {
        "type": "db_replication_lag",
        "title": "PostgreSQL Replication Lag Critical — 47s Behind Primary",
        "description": "Read replica replication lag at 47 seconds (threshold: 5s). Read queries serving stale data.",
        "severity": IncidentSeverity.HIGH,
        "service": "order-service",
        "affected_users": 560,
        "error_count": 234,
        "metrics": {
            "cpu_percent": 82.0,
            "memory_percent": 74.0,
            "error_rate": 0.18,
            "latency_p99_ms": 3400,
            "replication_lag_s": 47,
            "db_connections": 78,
        },
        "mock_logs": (
            "2024-01-15T14:23:35.001Z WARN  [postgresql-replica] pg_stat_replication: replay_lag=47s (threshold=5s)\n"
            "  Primary LSN: 0/8A3F2190\n"
            "  Replica LSN: 0/8A3B9440\n"
            "  Bytes behind: 4,083,024 (3.9MB pending replay)\n"
            "2024-01-15T14:23:35.334Z WARN  [postgresql-replica] WAL receiver: streaming replication connected but lagging\n"
            "  received_lsn=0/8A3F0000 last_msg_receive_time=2024-01-15 14:23:34\n"
            "2024-01-15T14:23:35.556Z ERROR [order-service] [trace=1f7c4d9a] Stale data detected: order status inconsistency\n"
            "  order_id=ord_98234 primary_status=SHIPPED replica_status=PROCESSING\n"
            "  replication_lag=47s\n"
            "2024-01-15T14:23:35.891Z WARN  [order-service] Read replica query count: 12,450 queries/min routed to lagging replica\n"
            "2024-01-15T14:23:36.001Z ERROR [order-service] Data consistency check FAILED: 342 orders with status mismatch in last 60s\n"
            "2024-01-15T14:23:36.230Z WARN  [postgresql-replica] Long-running WAL apply: vacuum operation blocking replay\n"
            "  VACUUM on orders table: running for 180s, blocking 4,083,024 bytes of WAL replay\n"
            "2024-01-15T14:23:36.445Z CRIT  [monitoring] replication_lag_alert: lag=47s SLA=5s — failover risk HIGH"
        ),
    },
]


class MonitorAgent:
    def __init__(self, agent_status: AgentStatus):
        self.name = "monitor"
        self.status = agent_status
        self._polling_interval = 30  # seconds in real mode

    # ── State helpers ──────────────────────────────────────────────────────────

    def _set_working(self, task: str):
        self.status.status = "working"
        self.status.current_task = task
        self.status.last_action = task
        self.status.last_action_time = datetime.utcnow()

    def _set_idle(self):
        self.status.status = "idle"
        self.status.current_task = None

    # ── Pipeline monitoring ────────────────────────────────────────────────────

    async def check_pipeline_status(self) -> dict:
        """Check Azure Monitor pipeline status across all services."""
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
                "last_deploy": (
                    datetime.utcnow() - timedelta(hours=random.randint(1, 72))
                ).isoformat(),
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
                issues.append(f"Error rate at {pipeline['error_rate'] * 100:.1f}%")
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

    async def create_incident(
        self,
        service: str,
        description: str,
        severity: IncidentSeverity,
        metrics: dict,
        title: str = "",
        affected_users: int = 0,
        error_count: int = 0,
        mock_logs: str = "",
    ) -> Incident:
        """Create a structured incident from detected anomaly."""
        self._set_working(f"Creating incident for {service}")
        await asyncio.sleep(0.2)

        sev_prefix = {
            IncidentSeverity.CRITICAL: "[CRITICAL]",
            IncidentSeverity.HIGH: "[HIGH]",
            IncidentSeverity.MEDIUM: "[MEDIUM]",
            IncidentSeverity.LOW: "[LOW]",
        }
        incident_title = title or f"{sev_prefix[severity]} {service} — {description[:50]}"

        # Embed mock_logs into metrics_snapshot so DiagnosticAgent can include
        # them in the GPT-4o context
        full_metrics = dict(metrics)
        if mock_logs:
            full_metrics["mock_logs"] = mock_logs

        incident = Incident(
            title=incident_title,
            description=description,
            severity=severity,
            service=service,
            metrics_snapshot=full_metrics,
            error_count=error_count or int(metrics.get("error_rate", 0.1) * random.randint(500, 5000)),
            affected_users=affected_users or (
                random.randint(200, 2000) if severity in [IncidentSeverity.CRITICAL, IncidentSeverity.HIGH]
                else random.randint(10, 200)
            ),
        )

        incident.add_timeline_event(
            agent=self.name,
            action="Anomaly Detected",
            details=(
                f"Azure Monitor alert fired: {description}. "
                f"Metrics — CPU: {metrics.get('cpu_percent', 'N/A')}%, "
                f"Memory: {metrics.get('memory_percent', 'N/A')}%, "
                f"ErrorRate: {metrics.get('error_rate', 'N/A')}, "
                f"P99: {metrics.get('latency_p99_ms', 'N/A')}ms"
            ),
            status="warning",
        )

        self.status.incidents_handled += 1
        self._set_idle()
        logger.info(f"MonitorAgent: Created incident {incident.id} for {service}")
        return incident

    async def run_simulation(self) -> Incident:
        """Run a full simulated monitoring cycle and return an incident."""
        scenario = random.choice(ANOMALY_SCENARIOS)
        return await self.create_incident(
            service=scenario.get("service", random.choice(MOCK_SERVICES)),
            title=scenario.get("title", ""),
            description=scenario["description"],
            severity=scenario["severity"],
            metrics=scenario["metrics"],
            affected_users=scenario.get("affected_users", 0),
            error_count=scenario.get("error_count", 0),
            mock_logs=scenario.get("mock_logs", ""),
        )

    async def create_demo_incident(self, health: dict, anomaly: dict) -> Incident:
        """Create an incident from a real demo-app health anomaly."""
        chaos = anomaly.get("chaos", [])
        chaos_str = f" Chaos active: {', '.join(chaos)}." if chaos else ""
        description = (
            f"ShopDemo anomaly detected: {'; '.join(anomaly['issues'])}.{chaos_str} "
            f"Status: {health.get('status', 'unknown')}."
        )
        title_prefix = {
            IncidentSeverity.CRITICAL: "[CRITICAL]",
            IncidentSeverity.HIGH:     "[HIGH]",
            IncidentSeverity.MEDIUM:   "[MEDIUM]",
            IncidentSeverity.LOW:      "[LOW]",
        }[anomaly["severity"]]

        chaos_type = chaos[0].replace("_active", "") if chaos else "anomaly"
        title = f"{title_prefix} ShopDemo — {chaos_type.replace('_', ' ').title()} detected"

        metrics = dict(anomaly["metrics"])
        metrics["active_chaos"] = chaos

        return await self.create_incident(
            service="shopdemo",
            title=title,
            description=description,
            severity=anomaly["severity"],
            metrics=metrics,
            affected_users=0,
            error_count=int(health.get("request_count", 0) * health.get("error_rate", 0) / 100),
        )

    async def background_poll(
        self,
        incidents_db: dict,
        agent_statuses: dict,
        stop_event: asyncio.Event,
    ) -> None:
        """
        Continuously poll ShopDemo /health and auto-create + remediate incidents.
        Runs as a background asyncio task (started in main.py lifespan).
        """
        from api.websocket import manager as ws_manager

        logger.info(
            f"[MONITOR] Background polling started — "
            f"interval={settings.MONITORING_INTERVAL_SECONDS}s "
            f"target={settings.DEMO_APP_URL}"
        )
        _last_incident_id: Optional[str] = None

        while not stop_event.is_set():
            try:
                health = await poll_demo_app()
                if health:
                    # Broadcast live metrics to dashboard
                    await ws_manager.broadcast_event(
                        event_type="demo_app_metrics",
                        data={
                            "status":          health.get("status"),
                            "memory_usage_mb": health.get("memory_usage_mb"),
                            "cpu_percent":     health.get("cpu_percent"),
                            "error_rate":      health.get("error_rate"),
                            "avg_latency_ms":  health.get("avg_latency_ms"),
                            "active_chaos":    health.get("active_chaos", []),
                            "request_count":   health.get("request_count"),
                            "polled_at":       health.get("_polled_at"),
                        },
                    )

                    anomaly = classify_demo_health(health)
                    if anomaly and _last_incident_id is None:
                        # Create incident and hand off to orchestrator
                        incident = await self.create_demo_incident(health, anomaly)
                        incidents_db[incident.id] = incident
                        _last_incident_id = incident.id
                        logger.warning(
                            f"[MONITOR] New demo-app incident {incident.id}: "
                            f"{'; '.join(anomaly['issues'])}"
                        )

                        # Trigger orchestrator pipeline
                        try:
                            from agents.orchestrator import OrchestratorAgent
                            orch = OrchestratorAgent(
                                incidents_db=incidents_db,
                                agent_statuses=agent_statuses,
                            )
                            asyncio.create_task(orch.handle_incident(incident))
                        except Exception as orch_err:
                            logger.error(f"[MONITOR] Orchestrator launch failed: {orch_err}")

                    elif health.get("status") == "healthy":
                        # Reset so the next anomaly creates a fresh incident
                        _last_incident_id = None

            except Exception as poll_err:
                logger.error(f"[MONITOR] Poll loop error: {poll_err}", exc_info=True)

            try:
                await asyncio.wait_for(
                    asyncio.shield(stop_event.wait()),
                    timeout=settings.MONITORING_INTERVAL_SECONDS,
                )
            except asyncio.TimeoutError:
                pass  # normal — just time for next poll

        logger.info("[MONITOR] Background polling stopped.")
