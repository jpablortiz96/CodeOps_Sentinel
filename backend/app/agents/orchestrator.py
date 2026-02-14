"""
OrchestratorAgent — Coordinates all agents through the auto-remediation pipeline.

State machine:
  DETECTED → DIAGNOSING → FIXING → DEPLOYING → RESOLVED
                                       └──────→ ROLLED_BACK  (deploy/test failure)
                           └──────→ HUMAN_REVIEW              (low confidence < threshold)

Confidence routing (CONFIDENCE_THRESHOLD from config, default 70):
  >= threshold  → full automated remediation
  <  threshold  → skip fix/deploy, escalate to human review with full diagnosis

All state transitions are:
  - Logged with structured metadata (timestamps, agent, duration)
  - Broadcast via WebSocket in real time
  - Written to the incident timeline
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from config import get_settings
from models.incident import Incident, IncidentStatus
from models.agent_messages import AgentStatus
from api.websocket import manager
from .monitor_agent import MonitorAgent
from .diagnostic_agent import DiagnosticAgent
from .fixer_agent import FixerAgent
from .deploy_agent import DeployAgent

logger = logging.getLogger(__name__)
settings = get_settings()


class OrchestratorAgent:
    """
    Coordinates MonitorAgent → DiagnosticAgent → FixerAgent → DeployAgent.
    Decides between automated remediation and human escalation based on
    diagnosis confidence score vs CONFIDENCE_THRESHOLD.
    """

    def __init__(self, incidents_db: dict, agent_statuses: dict):
        self.incidents_db = incidents_db
        self.monitor = MonitorAgent(agent_statuses["monitor"])
        self.diagnostic = DiagnosticAgent(agent_statuses["diagnostic"])
        self.fixer = FixerAgent(agent_statuses["fixer"])
        self.deploy = DeployAgent(agent_statuses["deploy"])
        self._threshold = settings.CONFIDENCE_THRESHOLD  # 0-100

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _transition_state(
        self,
        incident: Incident,
        new_status: IncidentStatus,
        message: str = "",
        elapsed_ms: Optional[int] = None,
    ):
        """Transition incident to a new state and broadcast via WebSocket."""
        old_status = incident.status
        incident.status = new_status
        self.incidents_db[incident.id] = incident

        elapsed_str = f" [{elapsed_ms}ms]" if elapsed_ms is not None else ""
        logger.info(
            f"[{incident.id}] State: {old_status} → {new_status}{elapsed_str} | {message}"
        )

        await manager.broadcast_event(
            event_type="state_transition",
            incident_id=incident.id,
            agent="orchestrator",
            data={
                "incident_id": incident.id,
                "old_status": old_status,
                "new_status": new_status,
                "message": message,
                "elapsed_ms": elapsed_ms,
                "incident": incident.model_dump(),
            },
        )

    async def _broadcast(
        self,
        agent_name: str,
        action: str,
        details: str,
        incident_id: str,
        elapsed_ms: Optional[int] = None,
    ):
        """Broadcast a structured agent activity event."""
        await manager.broadcast_event(
            event_type="agent_activity",
            incident_id=incident_id,
            agent=agent_name,
            data={
                "agent": agent_name,
                "action": action,
                "details": details,
                "elapsed_ms": elapsed_ms,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    @staticmethod
    def _ms(start: datetime) -> int:
        """Milliseconds elapsed since `start`."""
        return int((datetime.utcnow() - start).total_seconds() * 1000)

    def _confidence_score(self, confidence: float) -> int:
        """Convert 0.0-1.0 float confidence to 0-100 integer score."""
        return int(confidence * 100)

    # ── Main orchestration flow ────────────────────────────────────────────────

    async def handle_incident(self, incident: Incident):
        """
        Full auto-remediation pipeline.

        Phases:
          1. DETECTED    — Incident registered, routing begins
          2. DIAGNOSING  — DiagnosticAgent analyzes logs/metrics via GPT-4o
             ↳ if confidence < threshold → HUMAN_REVIEW (escalate, stop here)
          3. FIXING      — FixerAgent generates code fix via GPT-4o + PR
          4. DEPLOYING   — DeployAgent runs tests → deploys → validates
          5. RESOLVED    — All checks passed, fix is live
             or ROLLED_BACK — Deploy/test failure, reverted to stable version
        """
        pipeline_start = datetime.utcnow()
        logger.info(
            f"[{incident.id}] ── Orchestrator starting pipeline ──────────────────────\n"
            f"  Title:    {incident.title}\n"
            f"  Service:  {incident.service}\n"
            f"  Severity: {incident.severity.upper()}\n"
            f"  Threshold: {self._threshold}% confidence for auto-fix\n"
            f"─────────────────────────────────────────────────────────────────"
        )

        try:
            # ═══════════════════════════════════════════════════════════════
            # PHASE 1 — DETECTED
            # ═══════════════════════════════════════════════════════════════
            phase_start = datetime.utcnow()
            await self._transition_state(
                incident,
                IncidentStatus.DETECTED,
                f"Incident registered: severity={incident.severity.upper()}, "
                f"service={incident.service}, affected_users={incident.affected_users:,}",
            )
            await self._broadcast(
                "orchestrator",
                "Pipeline Started",
                (
                    f"Auto-remediation pipeline initiated for {incident.id}. "
                    f"Severity: {incident.severity.upper()}. "
                    f"Auto-fix threshold: {self._threshold}% confidence. "
                    f"Routing to Diagnostic Agent."
                ),
                incident.id,
            )
            await asyncio.sleep(0.4)

            # ═══════════════════════════════════════════════════════════════
            # PHASE 2 — DIAGNOSING
            # ═══════════════════════════════════════════════════════════════
            phase_start = datetime.utcnow()
            await self._transition_state(
                incident,
                IncidentStatus.DIAGNOSING,
                "DiagnosticAgent analyzing logs, metrics, and error traces",
                elapsed_ms=self._ms(pipeline_start),
            )
            await self._broadcast(
                "diagnostic",
                "Analysis Started",
                (
                    f"Fetching logs from {incident.service} (last 15 min). "
                    f"Querying Azure Monitor + Log Analytics. "
                    f"Preparing GPT-4o context."
                ),
                incident.id,
            )

            diagnosis = await self.diagnostic.diagnose(incident)
            self.incidents_db[incident.id] = incident

            diag_elapsed = self._ms(phase_start)
            confidence_pct = self._confidence_score(diagnosis.confidence)

            logger.info(
                f"[{incident.id}] Diagnosis complete in {diag_elapsed}ms — "
                f"confidence={confidence_pct}%, threshold={self._threshold}%"
            )

            await self._broadcast(
                "orchestrator",
                "Diagnosis Received",
                (
                    f"Root cause identified. "
                    f"Confidence: {confidence_pct}% "
                    f"({'✓ auto-fix' if confidence_pct >= self._threshold else '⚠ escalate'} "
                    f"— threshold: {self._threshold}%). "
                    f"Affected services: {', '.join(diagnosis.affected_services)}."
                ),
                incident.id,
                elapsed_ms=diag_elapsed,
            )

            # ── Confidence gate: escalate if below threshold ──────────────
            if confidence_pct < self._threshold:
                await self._handle_low_confidence(incident, diagnosis, confidence_pct, pipeline_start)
                return

            await asyncio.sleep(0.3)

            # ═══════════════════════════════════════════════════════════════
            # PHASE 3 — FIXING
            # ═══════════════════════════════════════════════════════════════
            phase_start = datetime.utcnow()
            await self._transition_state(
                incident,
                IncidentStatus.FIXING,
                "FixerAgent generating code fix via GPT-4o",
                elapsed_ms=self._ms(pipeline_start),
            )
            await self._broadcast(
                "fixer",
                "Fix Generation Started",
                (
                    f"GitHub Copilot + GPT-4o analyzing {incident.service} codebase. "
                    f"Applying: {diagnosis.recommended_action[:80]}..."
                ),
                incident.id,
            )

            fix = await self.fixer.generate_fix(incident, diagnosis)
            self.incidents_db[incident.id] = incident

            fix_elapsed = self._ms(phase_start)
            logger.info(
                f"[{incident.id}] Fix generated in {fix_elapsed}ms — "
                f"PR #{fix.pr_number}, file={fix.file_path}"
            )

            await self._broadcast(
                "orchestrator",
                "Fix Ready for Deployment",
                (
                    f"PR #{fix.pr_number} created: '{fix.description}'. "
                    f"File: {fix.file_path}. "
                    f"Routing to Deploy Agent for test suite + rolling deployment."
                ),
                incident.id,
                elapsed_ms=fix_elapsed,
            )
            await asyncio.sleep(0.3)

            # ═══════════════════════════════════════════════════════════════
            # PHASE 4 — DEPLOYING
            # ═══════════════════════════════════════════════════════════════
            phase_start = datetime.utcnow()
            await self._transition_state(
                incident,
                IncidentStatus.DEPLOYING,
                "DeployAgent running tests and rolling deployment",
                elapsed_ms=self._ms(pipeline_start),
            )
            await self._broadcast(
                "deploy",
                "Deployment Pipeline Started",
                (
                    f"Running test suite (Unit + Integration + E2E). "
                    f"Then: pre-deploy validation → rolling deployment → health checks."
                ),
                incident.id,
            )

            # Run test suite
            test_results = await self.deploy.run_tests(incident)
            self.incidents_db[incident.id] = incident

            if not test_results["all_passed"]:
                logger.warning(
                    f"[{incident.id}] Tests failed: "
                    f"{test_results['total_failed']} failures — initiating rollback"
                )
                await self._broadcast(
                    "deploy",
                    "Test Suite Failed",
                    (
                        f"{test_results['total_failed']} test failures detected. "
                        f"Passed: {test_results['total_passed']}/{test_results['total_tests']}. "
                        f"Initiating rollback to stable version."
                    ),
                    incident.id,
                )
                await self.deploy.rollback(incident)
                incident.resolved_at = datetime.utcnow()
                self.incidents_db[incident.id] = incident
                await self._transition_state(
                    incident,
                    IncidentStatus.ROLLED_BACK,
                    "Test suite failed — rolled back. Manual review required.",
                    elapsed_ms=self._ms(pipeline_start),
                )
                self._log_completion(incident, pipeline_start, "ROLLED_BACK (test failure)")
                return

            # Pre-deploy validation
            pre_ok = await self.deploy.validate_pre_deploy(incident, fix)
            self.incidents_db[incident.id] = incident

            if not pre_ok:
                logger.warning(f"[{incident.id}] Pre-deploy validation failed — rollback")
                await self._broadcast(
                    "deploy",
                    "Pre-deploy Validation Failed",
                    "Security scan or staging health check failed. Rolling back.",
                    incident.id,
                )
                await self.deploy.rollback(incident)
                await self._transition_state(
                    incident,
                    IncidentStatus.ROLLED_BACK,
                    "Pre-deploy validation failed — rolled back",
                    elapsed_ms=self._ms(pipeline_start),
                )
                self._log_completion(incident, pipeline_start, "ROLLED_BACK (pre-deploy)")
                return

            # Deploy the fix
            deploy_result = await self.deploy.deploy_fix(incident, fix)
            self.incidents_db[incident.id] = incident

            if not deploy_result["success"]:
                logger.warning(
                    f"[{incident.id}] Deployment failed: {deploy_result.get('reason')} — rollback"
                )
                await self.deploy.rollback(incident)
                incident.resolved_at = datetime.utcnow()
                self.incidents_db[incident.id] = incident
                await self._transition_state(
                    incident,
                    IncidentStatus.ROLLED_BACK,
                    deploy_result.get("reason", "Deployment health check failed"),
                    elapsed_ms=self._ms(pipeline_start),
                )
                self._log_completion(incident, pipeline_start, "ROLLED_BACK (deploy health)")
                return

            # ═══════════════════════════════════════════════════════════════
            # PHASE 5 — RESOLVED
            # ═══════════════════════════════════════════════════════════════
            total_ms = self._ms(pipeline_start)
            incident.resolved_at = datetime.utcnow()
            await self._transition_state(
                incident,
                IncidentStatus.RESOLVED,
                (
                    f"Fix deployed successfully. "
                    f"Version {deploy_result.get('deployed_version', 'N/A')} is live. "
                    f"MTTR: {total_ms / 1000:.1f}s"
                ),
                elapsed_ms=total_ms,
            )
            incident.add_timeline_event(
                agent="orchestrator",
                action="Incident Resolved ✓",
                details=(
                    f"Auto-remediation complete. "
                    f"Total pipeline: {total_ms / 1000:.1f}s | "
                    f"{len(incident.timeline)} timeline events | "
                    f"Fix: PR #{fix.pr_number} | "
                    f"Version: {deploy_result.get('deployed_version', 'N/A')}"
                ),
                status="success",
            )
            self.incidents_db[incident.id] = incident

            await self._broadcast(
                "orchestrator",
                "Remediation Complete ✓",
                (
                    f"{incident.service} is operating normally. "
                    f"Fix: {fix.description}. "
                    f"MTTR: {total_ms / 1000:.1f}s."
                ),
                incident.id,
                elapsed_ms=total_ms,
            )
            self._log_completion(incident, pipeline_start, "RESOLVED")

        except Exception as e:
            total_ms = self._ms(pipeline_start)
            logger.error(
                f"[{incident.id}] !! Orchestrator critical error after {total_ms}ms: {e}",
                exc_info=True,
            )
            incident.status = IncidentStatus.FAILED
            incident.add_timeline_event(
                agent="orchestrator",
                action="Pipeline Error",
                details=f"Unexpected error in orchestration pipeline: {str(e)}",
                status="error",
            )
            self.incidents_db[incident.id] = incident
            await manager.broadcast_event(
                event_type="error",
                incident_id=incident.id,
                agent="orchestrator",
                data={
                    "error": str(e),
                    "incident_id": incident.id,
                    "elapsed_ms": total_ms,
                },
            )

    # ── Confidence escalation ──────────────────────────────────────────────────

    async def _handle_low_confidence(
        self,
        incident: Incident,
        diagnosis,
        confidence_pct: int,
        pipeline_start: datetime,
    ):
        """Escalate to human review when confidence is below the threshold."""
        logger.warning(
            f"[{incident.id}] Confidence {confidence_pct}% < threshold {self._threshold}% "
            f"— escalating to human review"
        )

        incident.add_timeline_event(
            agent="orchestrator",
            action="Escalated to Human Review",
            details=(
                f"Confidence score {confidence_pct}% is below the auto-remediation threshold "
                f"of {self._threshold}%. Root cause: {diagnosis.root_cause[:120]}. "
                f"Human review required before applying fix."
            ),
            status="warning",
        )
        self.incidents_db[incident.id] = incident

        await self._broadcast(
            "orchestrator",
            "⚠ Human Review Required",
            (
                f"Confidence {confidence_pct}% < {self._threshold}% threshold. "
                f"Diagnosis provided but auto-remediation paused. "
                f"Root cause: {diagnosis.root_cause[:100]}. "
                f"Recommended action: {diagnosis.recommended_action[:100]}."
            ),
            incident.id,
            elapsed_ms=self._ms(pipeline_start),
        )

        # Set status to a special state (reuse DETECTED to keep pipeline visible)
        incident.status = IncidentStatus.DETECTED
        self.incidents_db[incident.id] = incident

    # ── Completion logger ──────────────────────────────────────────────────────

    def _log_completion(self, incident: Incident, start: datetime, outcome: str):
        total_ms = self._ms(start)
        logger.info(
            f"[{incident.id}] ── Pipeline complete ── {outcome} ──────────────────────\n"
            f"  Duration: {total_ms / 1000:.2f}s ({total_ms}ms)\n"
            f"  Timeline events: {len(incident.timeline)}\n"
            f"  Agents involved: {', '.join(incident.agents_involved)}\n"
            f"─────────────────────────────────────────────────────────────────"
        )
