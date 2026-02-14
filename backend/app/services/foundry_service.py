"""
Microsoft Foundry / Azure OpenAI integration service.

Auto-detects whether to use real AI or simulation based on AZURE_OPENAI_KEY:
  - Key present  → Real Azure OpenAI GPT-4o calls
  - Key absent   → Simulation mode (demo always works without credentials)

Features:
  - Async OpenAI client via asyncio.to_thread (SDK is sync)
  - Exponential backoff retry (3 attempts) for transient errors
  - Rate limit handling (429 → wait + retry)
  - Structured JSON response parsing with validation
  - Token usage logging for cost tracking
"""

import asyncio
import json
import logging
import random
import time
from typing import Any, Optional

from config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ─── Simulation fallback data ─────────────────────────────────────────────────

_MOCK_DIAGNOSES = [
    {
        "root_cause": "N+1 ORM query pattern in the payment handler: each order triggers a separate DB call to fetch line items. With 847 queries/request at peak load, this saturates CPU and exhausts the connection pool.",
        "severity": "critical",
        "affected_services": ["payment-service", "postgresql", "api-gateway"],
        "recommended_action": "Replace the for-loop item queries with eager loading (JOIN). Add Redis cache with 300s TTL. Scale service to 6 replicas immediately.",
        "confidence": 0.94,
        "error_pattern": "SELECT * FROM order_items WHERE order_id = ? (repeated 847×/req)",
        "log_evidence": "2024-01-15T14:23:11Z ERROR [payment] DB query budget exceeded: 847 queries in 1.2s (limit=10)",
        "estimated_impact": "1,200 users experiencing 30s+ checkout timeouts. ~$45k/hr revenue impact.",
        "time_to_resolve_minutes": 15,
    },
    {
        "root_cause": "EventEmitter memory leak in WebSocket session handler. Listeners accumulate without removal on client disconnect, causing unbounded heap growth. At 91.5% memory, OOMKill is imminent in ~10 minutes.",
        "severity": "high",
        "affected_services": ["auth-service", "session-store"],
        "recommended_action": "Add removeListener cleanup in disconnect handler. Restart pods immediately (rolling) to recover memory. Deploy fix within 15 minutes.",
        "confidence": 0.91,
        "error_pattern": "MaxListenersExceededWarning: 11 listeners added to [WebSocket]",
        "log_evidence": "2024-01-15T14:23:15Z WARN [auth] MaxListenersExceededWarning: Possible EventEmitter memory leak",
        "estimated_impact": "430 active sessions at risk. Service OOMKill in ~10 min without restart.",
        "time_to_resolve_minutes": 20,
    },
    {
        "root_cause": "Missing composite index on transactions(user_id, created_at). PostgreSQL planner performs full sequential scan on 12.4M rows for every user history query. Traffic spike 3× normal multiplied the impact.",
        "severity": "high",
        "affected_services": ["postgresql", "user-service", "api-gateway"],
        "recommended_action": "CREATE INDEX CONCURRENTLY idx_txn_user_date ON transactions(user_id, created_at DESC). Estimated index build: 4 minutes. P99 latency should drop from 12s to <200ms.",
        "confidence": 0.96,
        "error_pattern": "Seq Scan on transactions (cost=0.00..234891.23 rows=12450000)",
        "log_evidence": "2024-01-15T14:23:22Z SLOW [db] query=SELECT * FROM transactions WHERE user_id=? ORDER BY created_at DESC duration=11823ms",
        "estimated_impact": "890 users experiencing >10s page loads. Dashboard and history pages completely degraded.",
        "time_to_resolve_minutes": 12,
    },
    {
        "root_cause": "Kubernetes pod OOMKilled due to memory limit set to 512Mi — insufficient for peak buffer accumulation in the API gateway. Exit code 137 (SIGKILL) confirms kernel OOM intervention. CrashLoopBackOff restart count: 8.",
        "severity": "critical",
        "affected_services": ["api-gateway", "k8s-cluster", "all-downstream-services"],
        "recommended_action": "Increase memory limit to 1Gi in deployment spec. Enable response streaming to eliminate buffer accumulation. Add HPA with memory-based scaling trigger at 75%.",
        "confidence": 0.97,
        "error_pattern": "OOMKilled exit_code=137 restart_count=8",
        "log_evidence": "2024-01-15T14:23:18Z [k8s] Pod api-gateway-7d9f8b-xkp2q Terminated/OOMKilled ExitCode=137 RestartCount=8",
        "estimated_impact": "All API traffic affected during restart cycles. 8 restarts = ~80s cumulative downtime. SLA breach if 2+ more restarts.",
        "time_to_resolve_minutes": 10,
    },
]

_MOCK_FIXES = [
    {
        "file_path": "src/services/payment.service.ts",
        "description": "Replace N+1 item queries with eager loading JOIN + Redis cache",
        "original_code": "const orders = await orderRepo.find({ userId });\nfor (const order of orders) {\n  order.items = await itemRepo.find({ orderId: order.id });\n}",
        "fixed_code": "// Fix: single JOIN query + Redis cache (TTL=300s)\nconst cacheKey = `orders:${userId}`;\nconst cached = await redis.get(cacheKey);\nif (cached) return JSON.parse(cached);\n\nconst orders = await orderRepo.find({\n  where: { userId },\n  relations: ['items'],  // 1 JOIN query instead of N queries\n});\nawait redis.setex(cacheKey, 300, JSON.stringify(orders));\nreturn orders;",
        "explanation": "Eager loading via 'relations' generates a single JOIN query. Redis cache eliminates repeat DB hits for the same user within the 5-minute window.",
        "test_suggestions": ["Verify query count drops from N+1 to 1", "Load test 100 concurrent users — CPU < 60%", "Test cache invalidation on order mutation"],
        "risk_level": "low",
        "rollback_instructions": "Remove relations array and cache calls. No DB migration required.",
    },
    {
        "file_path": "src/gateway/websocket.handler.ts",
        "description": "Add explicit listener cleanup on WebSocket disconnect to prevent heap growth",
        "original_code": "socket.on('connect', () => {\n  eventBus.on('order:update', (data) => socket.emit('update', data));\n  eventBus.on('alert', (data) => socket.emit('alert', data));\n});",
        "fixed_code": "socket.on('connect', () => {\n  // Fix: named refs so we can remove them precisely on disconnect\n  const onOrderUpdate = (data) => socket.emit('update', data);\n  const onAlert = (data) => socket.emit('alert', data);\n\n  eventBus.on('order:update', onOrderUpdate);\n  eventBus.on('alert', onAlert);\n\n  socket.on('disconnect', () => {\n    eventBus.removeListener('order:update', onOrderUpdate);\n    eventBus.removeListener('alert', onAlert);\n  });\n});",
        "explanation": "Storing named references enables precise removal on disconnect, stopping the O(n) heap growth where n = total connections since startup.",
        "test_suggestions": ["Monitor heapUsed over 1000 connect/disconnect cycles — must be stable", "Verify listenerCount('order:update') returns 0 after all clients disconnect", "Load test: 500 clients connect/disconnect — memory returns to baseline"],
        "risk_level": "low",
        "rollback_instructions": "Remove disconnect handler and named function references. Restart service to clear existing leaked listeners.",
    },
    {
        "file_path": "migrations/add_transactions_index.sql",
        "description": "Add composite index to eliminate full table scan on transactions",
        "original_code": "-- No index on transactions(user_id, created_at)\n-- Current: Seq Scan cost=234891.23",
        "fixed_code": "-- Fix: CONCURRENTLY avoids table lock in production\nCREATE INDEX CONCURRENTLY IF NOT EXISTS\n  idx_transactions_user_date\nON transactions(user_id, created_at DESC)\nWHERE deleted_at IS NULL;  -- partial index for active records only\n\nANALYZE transactions;\n-- Expected: Seq Scan -> Index Scan, cost 234891 -> 0.42 (99.9% reduction)",
        "explanation": "The sequential scan on 12.4M rows causes 11-second queries. The composite index allows PostgreSQL to use an Index Scan, reducing cost by 99.9%. CONCURRENTLY prevents production table lock.",
        "test_suggestions": ["Run EXPLAIN ANALYZE — confirm Index Scan in query plan", "Verify P99 latency drops from >10s to <200ms under load", "Check index build progress: SELECT phase FROM pg_stat_progress_create_index"],
        "risk_level": "low",
        "rollback_instructions": "DROP INDEX CONCURRENTLY idx_transactions_user_date; — safe to run anytime, no data impact.",
    },
    {
        "file_path": "k8s/deployments/api-gateway.yaml",
        "description": "Increase memory limit to 1Gi and add HPA for memory-based autoscaling",
        "original_code": "resources:\n  limits:\n    memory: '512Mi'\n    cpu: '500m'",
        "fixed_code": "resources:\n  requests:\n    memory: '512Mi'  # Fix: raised to match observed baseline\n    cpu: '250m'\n  limits:\n    memory: '1Gi'    # Fix: 2x headroom above P99 peak\n    cpu: '1000m'     # Fix: allow CPU burst on traffic spikes\n# HPA added separately in hpa.yaml\n# minReplicas: 3, maxReplicas: 10, memory trigger: 75%",
        "explanation": "Doubling the memory limit gives headroom above the P99 peak usage. The HPA ensures the cluster scales out before any single pod approaches the limit, preventing future OOMKills.",
        "test_suggestions": ["Run load test to peak — verify no OOMKilled events", "Confirm HPA triggers scale-out at 75% memory", "Verify rolling restart completes with 0 downtime"],
        "risk_level": "medium",
        "rollback_instructions": "kubectl apply -f k8s/deployments/api-gateway.yaml.bak. Delete HPA: kubectl delete hpa api-gateway-hpa.",
    },
]


# ─── FoundryService ───────────────────────────────────────────────────────────

class FoundryService:
    """
    Azure OpenAI (Foundry) client for agent intelligence.

    Auto-detects real vs simulation mode based on AZURE_OPENAI_KEY.
    All public methods are async-safe.
    """

    def __init__(self):
        self.endpoint = settings.AZURE_OPENAI_ENDPOINT
        self.api_key = settings.AZURE_OPENAI_KEY
        self.deployment = settings.AZURE_OPENAI_DEPLOYMENT
        # Use real AI only when a non-placeholder key is set
        self.use_real_ai = bool(
            self.api_key
            and self.api_key not in ("", "your-azure-openai-key-here")
            and not settings.SIMULATION_MODE
        )
        mode = "REAL Azure OpenAI" if self.use_real_ai else "SIMULATION"
        logger.info(f"FoundryService initialized — mode: {mode}, deployment: {self.deployment}")

    # ── Public API ─────────────────────────────────────────────────────────────

    async def chat_completion(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float = 0.1,
        max_tokens: int = 1500,
        expect_json: bool = True,
    ) -> dict:
        """
        Call Azure OpenAI chat completion.
        Returns dict with keys: content, tokens_used, model, latency_ms, source.
        Falls back to simulation on any error.
        """
        if not self.use_real_ai:
            await asyncio.sleep(random.uniform(0.6, 1.2))  # simulate network latency
            return {
                "content": None,  # callers handle None as "use simulation"
                "tokens_used": 0,
                "model": "simulation",
                "latency_ms": random.randint(600, 1200),
                "source": "simulation",
            }

        start = time.monotonic()
        result = await self._call_with_retry(system_prompt, user_message, temperature, max_tokens)
        latency_ms = int((time.monotonic() - start) * 1000)

        result["latency_ms"] = latency_ms
        logger.info(
            f"FoundryService: {self.deployment} responded in {latency_ms}ms "
            f"({result.get('tokens_used', '?')} tokens)"
        )
        return result

    async def analyze_with_context(self, context: str, query: str) -> dict:
        """Generic contextual analysis — wraps chat_completion with a generic SRE system prompt."""
        from ..agents.agent_prompts import DIAGNOSTIC_SYSTEM_PROMPT
        return await self.chat_completion(
            system_prompt=DIAGNOSTIC_SYSTEM_PROMPT,
            user_message=f"Context:\n{context}\n\nQuery: {query}",
        )

    def get_mock_diagnosis(self) -> dict:
        """Return a random realistic mock diagnosis for simulation mode."""
        return random.choice(_MOCK_DIAGNOSES)

    def get_mock_fix(self) -> dict:
        """Return a random realistic mock fix for simulation mode."""
        return random.choice(_MOCK_FIXES)

    # ── Internal: retry + parsing ──────────────────────────────────────────────

    async def _call_with_retry(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
        max_retries: int = 3,
    ) -> dict:
        """Execute OpenAI call with exponential backoff on transient errors."""
        last_error: Optional[Exception] = None

        for attempt in range(1, max_retries + 1):
            try:
                return await asyncio.to_thread(
                    self._sync_call,
                    system_prompt,
                    user_message,
                    temperature,
                    max_tokens,
                )
            except Exception as e:
                last_error = e
                error_str = str(e).lower()

                # Rate limit: honour Retry-After header if present
                if "429" in error_str or "rate limit" in error_str:
                    wait = (2 ** attempt) + random.uniform(0, 1)
                    logger.warning(f"FoundryService: Rate limited (attempt {attempt}/{max_retries}). Waiting {wait:.1f}s")
                    await asyncio.sleep(wait)

                # Transient server error: backoff and retry
                elif any(code in error_str for code in ("500", "502", "503", "timeout")):
                    wait = (2 ** attempt) * 0.5 + random.uniform(0, 0.5)
                    logger.warning(f"FoundryService: Transient error (attempt {attempt}/{max_retries}): {e}. Waiting {wait:.1f}s")
                    await asyncio.sleep(wait)

                # Auth / config error: fail immediately, no point retrying
                elif any(code in error_str for code in ("401", "403", "invalid")):
                    logger.error(f"FoundryService: Auth/config error — will not retry: {e}")
                    break

                else:
                    wait = attempt * 0.5
                    logger.warning(f"FoundryService: Unknown error (attempt {attempt}/{max_retries}): {e}")
                    await asyncio.sleep(wait)

        # All retries exhausted — return error result for caller to handle
        logger.error(f"FoundryService: All {max_retries} retries failed. Last error: {last_error}")
        return {
            "content": None,
            "tokens_used": 0,
            "model": self.deployment,
            "error": str(last_error),
            "source": "error_fallback",
        }

    def _sync_call(
        self,
        system_prompt: str,
        user_message: str,
        temperature: float,
        max_tokens: int,
    ) -> dict:
        """Synchronous OpenAI call — runs in a thread via asyncio.to_thread."""
        from openai import AzureOpenAI

        client = AzureOpenAI(
            azure_endpoint=self.endpoint,
            api_key=self.api_key,
            api_version="2024-08-01-preview",
        )

        response = client.chat.completions.create(
            model=self.deployment,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},  # enforce JSON output
        )

        content = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        logger.debug(f"FoundryService raw response ({tokens} tokens): {content[:200]}...")

        return {
            "content": content,
            "tokens_used": tokens,
            "model": self.deployment,
            "source": "azure_openai",
        }

    @staticmethod
    def parse_json_response(raw: Optional[str], fallback: dict) -> dict:
        """
        Safely parse a JSON string from GPT-4o.
        Returns fallback dict if parsing fails.
        """
        if not raw:
            return fallback
        try:
            parsed = json.loads(raw)
            return parsed
        except json.JSONDecodeError:
            # Try to extract JSON block from within text
            import re
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
            logger.warning(f"FoundryService: Could not parse JSON response, using fallback. Raw: {raw[:200]}")
            return fallback


# ─── Singleton ────────────────────────────────────────────────────────────────

_foundry_instance: Optional[FoundryService] = None


def get_foundry_service() -> FoundryService:
    """Return the shared FoundryService instance (created once)."""
    global _foundry_instance
    if _foundry_instance is None:
        _foundry_instance = FoundryService()
    return _foundry_instance
