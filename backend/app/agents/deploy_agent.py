import asyncio
import random
import logging
from datetime import datetime
from typing import Optional

import httpx

from config import get_settings
from models.incident import Incident, Fix, IncidentStatus
from models.agent_messages import AgentStatus

logger = logging.getLogger(__name__)
settings = get_settings()

TEST_SUITES = [
    {"name": "Unit Tests", "total": 342, "duration_s": 12},
    {"name": "Integration Tests", "total": 87, "duration_s": 34},
    {"name": "E2E Tests", "total": 24, "duration_s": 89},
    {"name": "Performance Tests", "total": 12, "duration_s": 45},
    {"name": "Security Scan", "total": 156, "duration_s": 28},
]

DEPLOY_STAGES = [
    "Building Docker image",
    "Pushing to container registry",
    "Updating Kubernetes manifests",
    "Rolling deployment to staging",
    "Running smoke tests",
    "Promoting to production",
    "Verifying deployment health",
]


class DeployAgent:
    def __init__(self, agent_status: AgentStatus):
        self.name = "deploy"
        self.status = agent_status
        self._success_rate = 0.88  # 88% success rate for realism

    def _set_working(self, task: str):
        self.status.status = "working"
        self.status.current_task = task
        self.status.last_action = task
        self.status.last_action_time = datetime.utcnow()

    def _set_idle(self):
        self.status.status = "idle"
        self.status.current_task = None

    async def run_tests(self, incident: Incident) -> dict:
        """Simulate running the full test suite."""
        self._set_working("Running test suite")

        all_passed = True
        results = []

        for suite in TEST_SUITES[:3]:  # Run first 3 suites for speed
            await asyncio.sleep(0.4)
            failed = random.randint(0, 2) if random.random() > 0.9 else 0
            passed = suite["total"] - failed
            results.append({
                "suite": suite["name"],
                "passed": passed,
                "failed": failed,
                "total": suite["total"],
                "duration_s": suite["duration_s"],
                "status": "passed" if failed == 0 else "failed",
            })
            if failed > 0:
                all_passed = False

        summary = {
            "all_passed": all_passed,
            "total_passed": sum(r["passed"] for r in results),
            "total_failed": sum(r["failed"] for r in results),
            "total_tests": sum(r["total"] for r in results),
            "suites": results,
            "coverage": round(random.uniform(82, 96), 1),
        }

        incident.add_timeline_event(
            agent=self.name,
            action="Tests Complete",
            details=f"{'All tests passed' if all_passed else 'Some tests failed'}. {summary['total_passed']}/{summary['total_tests']} passed. Coverage: {summary['coverage']}%",
            status="success" if all_passed else "error",
        )

        return summary

    async def validate_pre_deploy(self, incident: Incident, fix: Fix) -> bool:
        """Run pre-deployment validation checks."""
        self._set_working("Pre-deploy validation")

        incident.add_timeline_event(
            agent=self.name,
            action="Pre-deploy Checks",
            details="Validating: code review passed, security scan clean, staging environment healthy, rollback plan ready.",
            status="info",
        )
        await asyncio.sleep(0.7)

        checks = {
            "code_review": True,
            "security_scan": random.random() > 0.05,  # 95% pass
            "staging_healthy": random.random() > 0.1,
            "rollback_ready": True,
            "change_approved": True,
        }

        all_passed = all(checks.values())
        incident.add_timeline_event(
            agent=self.name,
            action="Pre-deploy Validation",
            details=f"Checks: {', '.join(f'{k}={v}' for k, v in checks.items())}",
            status="success" if all_passed else "warning",
        )
        return all_passed

    async def deploy_fix(self, incident: Incident, fix: Fix) -> dict:
        """Deploy the fix to production via rolling deployment."""
        self._set_working(f"Deploying fix for {incident.id}")

        incident.add_timeline_event(
            agent=self.name,
            action="Deployment Started",
            details=f"Merging PR #{fix.pr_number} and triggering deployment pipeline for {incident.service}.",
            status="info",
        )

        # Simulate deployment stages
        for i, stage in enumerate(DEPLOY_STAGES[:5]):
            await asyncio.sleep(0.4)
            incident.add_timeline_event(
                agent=self.name,
                action=stage,
                details=f"Stage {i+1}/{len(DEPLOY_STAGES[:5])}: {stage} for {incident.service}",
                status="info",
            )

        # Simulate potential deployment failure
        deploy_success = random.random() < self._success_rate

        if not deploy_success:
            incident.add_timeline_event(
                agent=self.name,
                action="Deployment Failed",
                details=f"Health check failed after deployment. Rolling back to previous version.",
                status="error",
            )
            return {"success": False, "reason": "Health check failed post-deployment"}

        await asyncio.sleep(0.5)
        incident.add_timeline_event(
            agent=self.name,
            action="Post-deploy Validation",
            details=f"All {incident.service} pods healthy. Error rate normalized. Latency within SLA.",
            status="success",
        )

        self.status.incidents_handled += 1
        self._set_idle()
        return {
            "success": True,
            "deployed_version": f"v{random.randint(1, 9)}.{random.randint(0, 99)}.{random.randint(1, 50)}",
            "pods_updated": random.randint(3, 8),
            "rollout_duration_s": random.randint(45, 180),
        }

    async def rollback(self, incident: Incident) -> dict:
        """Perform emergency rollback to previous known-good version."""
        self._set_working(f"Rolling back {incident.service}")

        incident.add_timeline_event(
            agent=self.name,
            action="Rollback Initiated",
            details=f"Reverting {incident.service} to last known-good version. ETA: 60-90 seconds.",
            status="warning",
        )
        await asyncio.sleep(1.5)

        incident.add_timeline_event(
            agent=self.name,
            action="Rollback Complete",
            details=f"{incident.service} successfully reverted. Service stability restored. Incident marked as ROLLED_BACK for manual review.",
            status="warning",
        )

        self._set_idle()
        return {
            "success": True,
            "rolled_back_to": f"v{random.randint(1, 5)}.{random.randint(0, 50)}.{random.randint(0, 20)}-stable",
            "duration_s": random.randint(60, 120),
        }

    async def verify_remediation(self, incident: Incident, timeout_s: int = 30) -> dict:
        """
        Poll ShopDemo /health every 5 s for up to timeout_s seconds to confirm
        the app returned to a healthy or degraded state after remediation.
        """
        self._set_working("Verifying ShopDemo remediation")
        base = settings.DEMO_APP_URL
        interval = 5
        attempts = max(1, timeout_s // interval)

        incident.add_timeline_event(
            agent=self.name,
            action="Verification Started",
            details=f"Polling {base}/health every {interval}s (max {timeout_s}s).",
            status="info",
        )

        last_health: dict = {}
        for attempt in range(1, attempts + 1):
            try:
                async with httpx.AsyncClient(timeout=8.0) as client:
                    resp = await client.get(f"{base}/health")
                    if resp.status_code == 200:
                        last_health = resp.json()
                        status = last_health.get("status", "unknown")
                        logger.info(
                            f"[DEPLOY] verify attempt {attempt}/{attempts}: status={status}"
                        )
                        if status in ("healthy", "degraded"):
                            incident.add_timeline_event(
                                agent=self.name,
                                action="Remediation Verified",
                                details=(
                                    f"ShopDemo status={status} after {attempt * interval}s. "
                                    f"Memory={last_health.get('memory_usage_mb', '?')} MB, "
                                    f"CPU={last_health.get('cpu_percent', '?')}%, "
                                    f"ErrorRate={last_health.get('error_rate', '?')}%."
                                ),
                                status="success",
                            )
                            self._set_idle()
                            return {"verified": True, "status": status, "health": last_health, "attempts": attempt}
            except Exception as exc:
                logger.warning(f"[DEPLOY] verify attempt {attempt} failed: {exc}")

            if attempt < attempts:
                await asyncio.sleep(interval)

        # Timeout — still report whatever we got
        incident.add_timeline_event(
            agent=self.name,
            action="Verification Timeout",
            details=(
                f"App did not fully recover within {timeout_s}s. "
                f"Last status: {last_health.get('status', 'unknown')}."
            ),
            status="warning",
        )
        self._set_idle()
        return {
            "verified": False,
            "status":   last_health.get("status", "unknown"),
            "health":   last_health,
            "attempts": attempts,
        }
