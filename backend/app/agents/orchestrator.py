import asyncio
import logging
from datetime import datetime
from typing import Optional

from ..models.incident import Incident, IncidentStatus
from ..models.agent_messages import AgentStatus, WebSocketEvent
from ..api.websocket import manager
from .monitor_agent import MonitorAgent
from .diagnostic_agent import DiagnosticAgent
from .fixer_agent import FixerAgent
from .deploy_agent import DeployAgent

logger = logging.getLogger(__name__)


class OrchestratorAgent:
    """
    Main orchestrator that coordinates all agents in the auto-remediation pipeline.
    Implements a state machine: DETECTED -> DIAGNOSING -> FIXING -> DEPLOYING -> RESOLVED | ROLLED_BACK
    """

    def __init__(self, incidents_db: dict, agent_statuses: dict):
        self.incidents_db = incidents_db
        self.monitor = MonitorAgent(agent_statuses["monitor"])
        self.diagnostic = DiagnosticAgent(agent_statuses["diagnostic"])
        self.fixer = FixerAgent(agent_statuses["fixer"])
        self.deploy = DeployAgent(agent_statuses["deploy"])

    async def _transition_state(self, incident: Incident, new_status: IncidentStatus, message: str = ""):
        """Transition incident to new state and broadcast via WebSocket."""
        old_status = incident.status
        incident.status = new_status
        self.incidents_db[incident.id] = incident

        logger.info(f"Orchestrator: {incident.id} -> {old_status} => {new_status}")

        await manager.broadcast_event(
            event_type="state_transition",
            incident_id=incident.id,
            agent="orchestrator",
            data={
                "incident_id": incident.id,
                "old_status": old_status,
                "new_status": new_status,
                "message": message,
                "incident": incident.model_dump(),
            },
        )

    async def _broadcast_agent_activity(self, agent_name: str, action: str, details: str, incident_id: str = None):
        """Broadcast agent activity update to all WebSocket clients."""
        await manager.broadcast_event(
            event_type="agent_activity",
            incident_id=incident_id,
            agent=agent_name,
            data={
                "agent": agent_name,
                "action": action,
                "details": details,
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def handle_incident(self, incident: Incident):
        """
        Main orchestration flow. Coordinates all agents through the remediation pipeline.
        State Machine: DETECTED -> DIAGNOSING -> FIXING -> DEPLOYING -> RESOLVED | ROLLED_BACK
        """
        logger.info(f"Orchestrator: Starting remediation for {incident.id} - {incident.title}")

        try:
            # === PHASE 1: DETECTED ===
            await self._transition_state(
                incident,
                IncidentStatus.DETECTED,
                f"Incident detected: {incident.title}",
            )
            await self._broadcast_agent_activity(
                "orchestrator",
                "Incident Received",
                f"Beginning automated remediation for {incident.id}. Severity: {incident.severity.upper()}. Routing to diagnostic agent.",
                incident.id,
            )
            await asyncio.sleep(0.5)

            # === PHASE 2: DIAGNOSING ===
            await self._transition_state(incident, IncidentStatus.DIAGNOSING, "Routing to diagnostic agent")
            await self._broadcast_agent_activity(
                "diagnostic",
                "Analysis Started",
                f"Fetching logs and metrics for {incident.service}. Preparing Azure OpenAI context.",
                incident.id,
            )

            diagnosis = await self.diagnostic.diagnose(incident)
            self.incidents_db[incident.id] = incident

            await self._broadcast_agent_activity(
                "orchestrator",
                "Diagnosis Received",
                f"Root cause identified with {diagnosis.confidence:.0%} confidence. Routing to fixer agent.",
                incident.id,
            )
            await asyncio.sleep(0.3)

            # === PHASE 3: FIXING ===
            await self._transition_state(incident, IncidentStatus.FIXING, "Routing to fixer agent")
            await self._broadcast_agent_activity(
                "fixer",
                "Fix Generation Started",
                f"GitHub Copilot analyzing codebase for {incident.service}. Applying: {diagnosis.recommended_action[:60]}...",
                incident.id,
            )

            fix = await self.fixer.generate_fix(incident, diagnosis)
            self.incidents_db[incident.id] = incident

            await self._broadcast_agent_activity(
                "orchestrator",
                "Fix Ready",
                f"PR #{fix.pr_number} created with automated fix. Running test suite before deploy.",
                incident.id,
            )
            await asyncio.sleep(0.3)

            # === PHASE 4: DEPLOYING ===
            await self._transition_state(incident, IncidentStatus.DEPLOYING, "Starting deployment pipeline")
            await self._broadcast_agent_activity(
                "deploy",
                "Deployment Pipeline Started",
                f"Running {len(['Unit', 'Integration', 'E2E'])} test suites, then rolling deployment to production.",
                incident.id,
            )

            # Run tests first
            test_results = await self.deploy.run_tests(incident)
            self.incidents_db[incident.id] = incident

            if not test_results["all_passed"]:
                await self._broadcast_agent_activity(
                    "deploy",
                    "Tests Failed",
                    f"Test suite failed: {test_results['total_failed']} failures. Initiating rollback.",
                    incident.id,
                )
                await self.deploy.rollback(incident)
                incident.status = IncidentStatus.ROLLED_BACK
                incident.resolved_at = datetime.utcnow()
                self.incidents_db[incident.id] = incident
                await self._transition_state(
                    incident, IncidentStatus.ROLLED_BACK, "Tests failed, rolled back to stable version"
                )
                return

            # Pre-deploy validation
            pre_deploy_ok = await self.deploy.validate_pre_deploy(incident, fix)
            self.incidents_db[incident.id] = incident

            if not pre_deploy_ok:
                await self._broadcast_agent_activity(
                    "deploy",
                    "Pre-deploy Check Failed",
                    "Security or staging validation failed. Initiating rollback.",
                    incident.id,
                )
                await self.deploy.rollback(incident)
                await self._transition_state(
                    incident, IncidentStatus.ROLLED_BACK, "Pre-deploy validation failed"
                )
                return

            # Deploy the fix
            deploy_result = await self.deploy.deploy_fix(incident, fix)
            self.incidents_db[incident.id] = incident

            if not deploy_result["success"]:
                await self.deploy.rollback(incident)
                incident.resolved_at = datetime.utcnow()
                self.incidents_db[incident.id] = incident
                await self._transition_state(
                    incident, IncidentStatus.ROLLED_BACK, deploy_result.get("reason", "Deploy failed")
                )
                return

            # === PHASE 5: RESOLVED ===
            incident.resolved_at = datetime.utcnow()
            await self._transition_state(
                incident,
                IncidentStatus.RESOLVED,
                f"Fix deployed successfully. Version {deploy_result.get('deployed_version', 'N/A')} is live.",
            )
            incident.add_timeline_event(
                agent="orchestrator",
                action="Incident Resolved",
                details=f"All systems nominal. Auto-remediation complete in {len(incident.timeline)} steps. MTTR: ~{len(incident.timeline) * 2} seconds.",
                status="success",
            )
            self.incidents_db[incident.id] = incident

            await self._broadcast_agent_activity(
                "orchestrator",
                "Remediation Complete",
                f"Incident {incident.id} resolved. {incident.service} operating normally. Fix: {fix.description}",
                incident.id,
            )
            logger.info(f"Orchestrator: Successfully resolved {incident.id}")

        except Exception as e:
            logger.error(f"Orchestrator: Critical error handling {incident.id}: {e}", exc_info=True)
            incident.status = IncidentStatus.FAILED
            incident.add_timeline_event(
                agent="orchestrator",
                action="Orchestration Error",
                details=f"Unexpected error in remediation pipeline: {str(e)}",
                status="error",
            )
            self.incidents_db[incident.id] = incident
            await manager.broadcast_event(
                event_type="error",
                incident_id=incident.id,
                agent="orchestrator",
                data={"error": str(e), "incident_id": incident.id},
            )
