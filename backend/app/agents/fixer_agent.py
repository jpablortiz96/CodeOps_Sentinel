import asyncio
import random
import logging
from datetime import datetime

from ..models.incident import Incident, Diagnosis, Fix
from ..models.agent_messages import AgentStatus

logger = logging.getLogger(__name__)

FIX_TEMPLATES = {
    "N+1 query": {
        "file_path": "src/services/order.service.ts",
        "description": "Replace N+1 query pattern with eager loading and add Redis cache",
        "original_code": """async getOrdersWithItems(userId: string) {
  const orders = await this.orderRepo.find({ userId });
  for (const order of orders) {
    order.items = await this.itemRepo.find({ orderId: order.id });
  }
  return orders;
}""",
        "fixed_code": """async getOrdersWithItems(userId: string) {
  // Fix: Use eager loading to avoid N+1 queries
  const cacheKey = `orders:user:${userId}`;
  const cached = await this.redis.get(cacheKey);
  if (cached) return JSON.parse(cached);

  const orders = await this.orderRepo.find({
    where: { userId },
    relations: ['items'],  // Eager load items in single query
    cache: { id: cacheKey, milliseconds: 30000 },
  });

  await this.redis.setex(cacheKey, 300, JSON.stringify(orders));
  return orders;
}""",
    },
    "memory leak": {
        "file_path": "src/hooks/useWebSocket.ts",
        "description": "Add cleanup function to remove event listeners on unmount",
        "original_code": """useEffect(() => {
  const ws = new WebSocket(url);
  ws.addEventListener('message', handleMessage);
  ws.addEventListener('error', handleError);
  setSocket(ws);
}, [url]);""",
        "fixed_code": """useEffect(() => {
  const ws = new WebSocket(url);
  ws.addEventListener('message', handleMessage);
  ws.addEventListener('error', handleError);
  setSocket(ws);

  // Fix: Cleanup listeners to prevent memory leak
  return () => {
    ws.removeEventListener('message', handleMessage);
    ws.removeEventListener('error', handleError);
    ws.close(1000, 'Component unmounted');
    setSocket(null);
  };
}, [url]);""",
    },
    "circuit breaker": {
        "file_path": "src/services/cache.service.ts",
        "description": "Implement circuit breaker pattern with fallback for Redis connection failures",
        "original_code": """async get(key: string): Promise<string | null> {
  return await this.redis.get(key);
}""",
        "fixed_code": """async get(key: string): Promise<string | null> {
  // Fix: Circuit breaker with fallback to database
  if (this.circuitBreaker.isOpen()) {
    logger.warn(`Circuit breaker OPEN - bypassing cache for key: ${key}`);
    return null; // Fallback: skip cache, hit DB directly
  }

  try {
    const result = await this.redis.get(key);
    this.circuitBreaker.recordSuccess();
    return result;
  } catch (error) {
    this.circuitBreaker.recordFailure();
    logger.error(`Cache miss (failure) for key: ${key}`, error);
    return null; // Graceful degradation
  }
}""",
    },
    "index": {
        "file_path": "migrations/20240115_add_transactions_index.sql",
        "description": "Add composite database index to eliminate full table scan",
        "original_code": """-- No index exists on transactions(user_id, created_at)
-- Current query plan: Seq Scan (cost: 234891.00)""",
        "fixed_code": """-- Fix: Add composite index for common query pattern
-- Using CONCURRENTLY to avoid table lock in production
CREATE INDEX CONCURRENTLY IF NOT EXISTS
  idx_transactions_user_date
ON transactions(user_id, created_at DESC)
WHERE deleted_at IS NULL;  -- Partial index for active records

-- Expected improvement: Seq Scan -> Index Scan
-- Estimated cost reduction: 234891.00 -> 0.42 (99.9% improvement)
ANALYZE transactions;""",
    },
    "connection pool": {
        "file_path": "config/database.config.ts",
        "description": "Increase connection pool size and add timeout configuration",
        "original_code": """export const dbConfig = {
  host: process.env.DB_HOST,
  database: process.env.DB_NAME,
  pool: {
    max: 20,
    min: 2,
  },
};""",
        "fixed_code": """export const dbConfig = {
  host: process.env.DB_HOST,
  database: process.env.DB_NAME,
  pool: {
    max: 50,       // Fix: Increased from 20 to handle load spikes
    min: 5,        // Fix: Keep minimum ready connections
    acquire: 30000, // 30s timeout to acquire connection
    idle: 10000,   // Release idle connections after 10s
    evict: 1000,   // Check for idle connections every 1s
  },
  dialectOptions: {
    statement_timeout: 30000,        // Fix: 30s query timeout
    idle_in_transaction_session_timeout: 60000,
  },
};""",
    },
}

GENERIC_FIX = {
    "file_path": "src/services/main.service.ts",
    "description": "Apply performance optimization and error handling improvements",
    "original_code": "// Original code with performance issues",
    "fixed_code": "// Optimized code with proper error handling and caching",
}


class FixerAgent:
    def __init__(self, agent_status: AgentStatus):
        self.name = "fixer"
        self.status = agent_status

    def _set_working(self, task: str):
        self.status.status = "working"
        self.status.current_task = task
        self.status.last_action = task
        self.status.last_action_time = datetime.utcnow()

    def _set_idle(self):
        self.status.status = "idle"
        self.status.current_task = None

    def _select_fix_template(self, diagnosis: Diagnosis) -> dict:
        root_cause_lower = diagnosis.root_cause.lower()
        for keyword, template in FIX_TEMPLATES.items():
            if keyword in root_cause_lower:
                return template
        return GENERIC_FIX

    async def generate_fix(self, incident: Incident, diagnosis: Diagnosis) -> Fix:
        """Generate a code fix based on the diagnosis using GitHub Copilot Agent Mode."""
        self._set_working(f"Generating fix for {incident.id}")

        incident.add_timeline_event(
            agent=self.name,
            action="Analyzing Codebase",
            details=f"GitHub Copilot scanning repository '{incident.service}' for relevant code patterns. Reviewing {random.randint(15, 45)} related files.",
            status="info",
        )
        await asyncio.sleep(1.0)

        incident.add_timeline_event(
            agent=self.name,
            action="Generating Patch",
            details=f"GitHub Copilot Agent Mode generating fix. Recommendation: {diagnosis.recommended_action[:80]}...",
            status="info",
        )
        await asyncio.sleep(1.2)

        template = self._select_fix_template(diagnosis)

        fix = Fix(
            description=template["description"],
            file_path=template["file_path"],
            original_code=template["original_code"],
            fixed_code=template["fixed_code"],
        )

        incident.add_timeline_event(
            agent=self.name,
            action="Fix Generated",
            details=f"Patch ready: {fix.description}. Modified file: {fix.file_path}",
            status="info",
        )

        await asyncio.sleep(0.5)
        pr = await self.create_pull_request(incident, fix)
        fix.pr_url = pr["url"]
        fix.pr_number = pr["number"]

        incident.fix = fix
        incident.add_timeline_event(
            agent=self.name,
            action="Pull Request Created",
            details=f"PR #{fix.pr_number} created: '{fix.description}'. Ready for automated testing.",
            status="success",
        )

        self.status.incidents_handled += 1
        self._set_idle()
        logger.info(f"FixerAgent: Generated fix for {incident.id}, PR #{fix.pr_number}")
        return fix

    async def create_pull_request(self, incident: Incident, fix: Fix) -> dict:
        """Simulate creating a GitHub Pull Request."""
        await asyncio.sleep(0.6)
        pr_number = random.randint(100, 999)
        return {
            "number": pr_number,
            "url": f"https://github.com/your-org/your-repo/pull/{pr_number}",
            "title": f"fix: {fix.description} [auto-remediation for {incident.id}]",
            "branch": f"auto-fix/{incident.id.lower()}-{fix.fix_id}",
        }
