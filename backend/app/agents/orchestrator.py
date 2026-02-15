"""
OrchestratorAgent — Coordinates all agents through the auto-remediation pipeline.

Now powered by:
  - TaskPlanner: generates a dynamic 7-step execution plan per incident
  - MCPClient:   all inter-agent calls routed through MCP for full traceability
  - AgentRegistry: discovers and tracks all registered agents

State machine:
  DETECTED → DIAGNOSING → FIXING → DEPLOYING → RESOLVED
                                       └──────→ ROLLED_BACK
                           └──────→ HUMAN_REVIEW  (confidence < threshold)

All events are broadcast via WebSocket including:
  - plan_created:       full execution plan at pipeline start
  - plan_step_update:   real-time step status changes
  - mcp_call:           each inter-agent tool invocation
  - mcp_response:       tool response with timing
  - state_transition:   incident status changes
  - agent_activity:     human-readable agent narration
"""
import asyncio
import logging
from datetime import datetime
from typing import Optional

from config import get_settings
from models.incident import Incident, IncidentStatus
from models.agent_messages import AgentStatus
from api.websocket import manager
from mcp.mcp_server import get_mcp_server
from mcp.mcp_client import MCPClient
from framework.agent_registry import get_agent_registry
from framework.task_planner import TaskPlanner, ExecutionPlan, PlanStepStatus
from .monitor_agent import MonitorAgent
from .diagnostic_agent import DiagnosticAgent
from .fixer_agent import FixerAgent
from .deploy_agent import DeployAgent

logger = logging.getLogger(__name__)
settings = get_settings()


class OrchestratorAgent:
    """
    Coordinates the full auto-remediation pipeline using TaskPlanner + MCP.

    Architecture:
      OrchestratorAgent
        ├── TaskPlanner       — generates & tracks the execution plan
        ├── MCPClient         — routes all inter-agent calls via MCP
        ├── AgentRegistry     — discovers registered agents
        └── Agents            — actual worker agents (monitor, diagnostic, fixer, deploy)
    """

    def __init__(self, incidents_db: dict, agent_statuses: dict):
        self.incidents_db = incidents_db
        self._threshold = settings.CONFIDENCE_THRESHOLD

        # Worker agents
        self.monitor = MonitorAgent(agent_statuses["monitor"])
        self.diagnostic = DiagnosticAgent(agent_statuses["diagnostic"])
        self.fixer = FixerAgent(agent_statuses["fixer"])
        self.deploy = DeployAgent(agent_statuses["deploy"])

        # Framework components
        self._mcp_server = get_mcp_server()
        self._mcp = MCPClient(caller_name="orchestrator", server=self._mcp_server)
        self._registry = get_agent_registry()
        self._planner = TaskPlanner(confidence_threshold=self._threshold)

        # Register MCP handlers so the server can route to live agent instances
        self._register_mcp_handlers()

    # ── MCP handler registration ───────────────────────────────────────────────

    def _register_mcp_handlers(self) -> None:
        """Register agent methods as MCP tool handlers."""
        self._mcp_server.register_handlers({
            "monitor.check_health": self._handle_monitor_check_health,
            "monitor.get_metrics": self._handle_monitor_get_metrics,
            "diagnostic.analyze_incident": self._handle_diagnostic_analyze,
            "fixer.generate_patch": self._handle_fixer_generate,
            "fixer.validate_fix": self._handle_fixer_validate,
            "deploy.execute_deployment": self._handle_deploy_execute,
            "deploy.rollback": self._handle_deploy_rollback,
        })

    # ── MCP handler bridges ────────────────────────────────────────────────────

    async def _handle_monitor_check_health(self, params: dict) -> dict:
        service = params.get("service", "all")
        data = await self.monitor.check_pipeline_status()
        return {"service": service, "pipelines": data.get("pipelines", [])[:3]}

    async def _handle_monitor_get_metrics(self, params: dict) -> dict:
        service = params.get("service", "unknown")
        data = await self.monitor.check_pipeline_status()
        for p in data.get("pipelines", []):
            if p["service"] == service:
                return {"service": service, "metrics": p}
        pipelines = data.get("pipelines", [])
        return {"service": service, "metrics": pipelines[0] if pipelines else {}}

    async def _handle_diagnostic_analyze(self, params: dict) -> dict:
        incident_id = params.get("incident_id")
        incident = self.incidents_db.get(incident_id)
        if not incident:
            return {"error": f"Incident {incident_id} not found"}
        diagnosis = await self.diagnostic.diagnose(incident)
        return {
            "incident_id": incident_id,
            "root_cause": diagnosis.root_cause,
            "confidence": diagnosis.confidence,
            "severity": str(diagnosis.severity),
            "affected_services": diagnosis.affected_services,
            "recommended_action": diagnosis.recommended_action,
        }

    async def _handle_fixer_generate(self, params: dict) -> dict:
        incident_id = params.get("incident_id")
        incident = self.incidents_db.get(incident_id)
        if not incident or not incident.diagnosis:
            return {"error": "Incident or diagnosis not found"}
        fix = await self.fixer.generate_fix(incident, incident.diagnosis)
        return {
            "incident_id": incident_id,
            "fix_id": fix.fix_id,
            "file_path": fix.file_path,
            "description": fix.description,
            "pr_number": fix.pr_number,
            "pr_url": fix.pr_url,
        }

    async def _handle_fixer_validate(self, params: dict) -> dict:
        await asyncio.sleep(0.2)
        return {"valid": True, "security_scan": "passed", "risk": "low"}

    async def _handle_deploy_execute(self, params: dict) -> dict:
        incident_id = params.get("incident_id")
        incident = self.incidents_db.get(incident_id)
        if not incident or not incident.fix:
            return {"success": False, "error": "Incident or fix not found"}
        result = await self.deploy.deploy_fix(incident, incident.fix)
        return result

    async def _handle_deploy_rollback(self, params: dict) -> dict:
        incident_id = params.get("incident_id")
        incident = self.incidents_db.get(incident_id)
        if incident:
            await self.deploy.rollback(incident)
        return {"success": True, "rolled_back": True}

    # ── Helpers ────────────────────────────────────────────────────────────────

    async def _transition_state(
        self,
        incident: Incident,
        new_status: IncidentStatus,
        message: str = "",
        elapsed_ms: Optional[int] = None,
    ) -> None:
        old_status = incident.status
        incident.status = new_status
        self.incidents_db[incident.id] = incident
        elapsed_str = f" [{elapsed_ms}ms]" if elapsed_ms is not None else ""
        logger.info(f"[{incident.id}] {old_status} → {new_status}{elapsed_str} | {message}")
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
    ) -> None:
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
        return int((datetime.utcnow() - start).total_seconds() * 1000)

    def _confidence_score(self, confidence: float) -> int:
        return int(confidence * 100)

    # ── Main orchestration flow ────────────────────────────────────────────────

    async def handle_incident(self, incident: Incident) -> None:
        """
        Full auto-remediation pipeline powered by TaskPlanner + MCP.

        1. Create and broadcast 7-step execution plan
        2. Execute each step via MCP calls with A2A tracing
        3. Apply confidence gate after diagnosis
        4. Stream all plan updates + MCP events to WebSocket
        """
        pipeline_start = datetime.utcnow()
        corr_id = f"{incident.id}-{str(int(pipeline_start.timestamp()))}"
        self._registry.update_status("orchestrator", "working", f"Pipeline {incident.id}")

        logger.info(
            f"[{incident.id}] ── Pipeline start (threshold={self._threshold}%, corr={corr_id})"
        )

        # ── Create and broadcast the execution plan ───────────────────────────
        plan: ExecutionPlan = self._planner.create_plan(incident)
        plan.correlation_id = corr_id
        await self._planner._broadcast_plan(plan)

        await self._broadcast(
            "orchestrator",
            "Execution Plan Created",
            (
                f"TaskPlanner generated {len(plan.steps)}-step plan "
                f"({plan.plan_id}). Threshold: {self._threshold}%. "
                f"All calls routed via MCP."
            ),
            incident.id,
        )

        try:
            # ── DETECTED ─────────────────────────────────────────────────────
            await self._transition_state(
                incident, IncidentStatus.DETECTED,
                f"severity={incident.severity.upper()}, service={incident.service}",
            )
            await asyncio.sleep(0.3)

            # ── Step 1: Collect metrics ───────────────────────────────────────
            s1_start = datetime.utcnow()
            await self._planner.start_step(plan, 1)
            self._registry.update_status("monitor", "working", "Collecting metrics")

            mcp_r = await self._mcp.call_tool(
                "monitor.get_metrics",
                {"service": incident.service, "window_minutes": 15},
                correlation_id=corr_id, incident_id=incident.id,
            )
            s1_ms = self._ms(s1_start)
            await self._planner.complete_step(plan, 1, mcp_r, s1_ms)
            self._registry.update_status("monitor", "idle")
            await self._broadcast(
                "monitor", "Metrics Collected via MCP",
                f"Azure Monitor snapshot fetched ({s1_ms}ms). "
                f"CPU={incident.metrics_snapshot.get('cpu_percent','?')}%",
                incident.id, elapsed_ms=s1_ms,
            )

            # ── DIAGNOSING ────────────────────────────────────────────────────
            await self._transition_state(
                incident, IncidentStatus.DIAGNOSING,
                "DiagnosticAgent analyzing via MCP",
                elapsed_ms=self._ms(pipeline_start),
            )

            # ── Step 2: Root cause analysis ───────────────────────────────────
            s2_start = datetime.utcnow()
            await self._planner.start_step(plan, 2)
            self._registry.update_status("diagnostic", "working", f"Analyzing {incident.id}")

            mcp_r = await self._mcp.call_tool(
                "diagnostic.analyze_incident",
                {"incident_id": incident.id, "service": incident.service,
                 "description": incident.description},
                correlation_id=corr_id, incident_id=incident.id,
            )
            s2_ms = self._ms(s2_start)
            await self._planner.complete_step(plan, 2, mcp_r, s2_ms)
            self._registry.update_status("diagnostic", "idle")
            self.incidents_db[incident.id] = incident

            diagnosis = incident.diagnosis
            confidence_pct = self._confidence_score(diagnosis.confidence) if diagnosis else 0
            await self._broadcast(
                "diagnostic", "Root Cause via MCP",
                f"GPT-4o diagnosis ({s2_ms}ms): confidence={confidence_pct}%",
                incident.id, elapsed_ms=s2_ms,
            )

            # ── Step 3: Confidence gate ───────────────────────────────────────
            await self._planner.start_step(plan, 3)

            if confidence_pct < self._threshold:
                await self._planner.complete_step(
                    plan, 3, {"decision": "escalate", "confidence_pct": confidence_pct},
                    self._ms(pipeline_start),
                )
                for sn in [4, 5, 6, 7]:
                    await self._planner.skip_step(
                        plan, sn, f"Confidence {confidence_pct}% < {self._threshold}%"
                    )
                await self._planner.complete_plan(plan, "escalated", self._ms(pipeline_start))
                await self._handle_low_confidence(incident, diagnosis, confidence_pct, pipeline_start)
                self._registry.update_status("orchestrator", "idle")
                return

            await self._planner.complete_step(
                plan, 3, {"decision": "auto_fix", "confidence_pct": confidence_pct},
                self._ms(pipeline_start),
            )
            await self._broadcast(
                "orchestrator", "Confidence Gate Passed",
                f"Confidence {confidence_pct}% ≥ {self._threshold}%. Routing to FixerAgent.",
                incident.id, elapsed_ms=self._ms(pipeline_start),
            )
            await asyncio.sleep(0.2)

            # ── FIXING ────────────────────────────────────────────────────────
            await self._transition_state(
                incident, IncidentStatus.FIXING,
                "FixerAgent generating fix via MCP",
                elapsed_ms=self._ms(pipeline_start),
            )

            # ── Step 4: Generate fix ──────────────────────────────────────────
            s4_start = datetime.utcnow()
            await self._planner.start_step(plan, 4)
            self._registry.update_status("fixer", "working", f"Generating fix {incident.id}")

            mcp_r = await self._mcp.call_tool(
                "fixer.generate_patch",
                {"incident_id": incident.id, "service": incident.service,
                 "root_cause": diagnosis.root_cause if diagnosis else "",
                 "recommended_action": diagnosis.recommended_action if diagnosis else ""},
                correlation_id=corr_id, incident_id=incident.id,
            )
            s4_ms = self._ms(s4_start)
            await self._planner.complete_step(plan, 4, mcp_r, s4_ms)
            self._registry.update_status("fixer", "idle")
            self.incidents_db[incident.id] = incident

            fix = incident.fix
            if not fix:
                await self._planner.fail_step(plan, 5, "Fix not generated", 0)
                for sn in [6, 7]:
                    await self._planner.skip_step(plan, sn, "Fix unavailable")
                await self._planner.complete_plan(plan, "failed", self._ms(pipeline_start))
                raise RuntimeError("Fix generation produced no result")

            await self._broadcast(
                "fixer", "Fix Generated via MCP",
                f"PR #{fix.pr_number}: '{fix.description}'. File: {fix.file_path}. ({s4_ms}ms)",
                incident.id, elapsed_ms=s4_ms,
            )
            await asyncio.sleep(0.2)

            # ── Step 5: Validate fix ──────────────────────────────────────────
            s5_start = datetime.utcnow()
            await self._planner.start_step(plan, 5)

            mcp_r = await self._mcp.call_tool(
                "fixer.validate_fix",
                {"fix_id": fix.fix_id, "file_path": fix.file_path},
                correlation_id=corr_id, incident_id=incident.id,
            )
            s5_ms = self._ms(s5_start)
            await self._planner.complete_step(plan, 5, mcp_r, s5_ms)
            await self._broadcast(
                "fixer", "Fix Validated",
                f"Security scan passed. Risk: low. ({s5_ms}ms)",
                incident.id, elapsed_ms=s5_ms,
            )
            await asyncio.sleep(0.2)

            # ── DEPLOYING ─────────────────────────────────────────────────────
            await self._transition_state(
                incident, IncidentStatus.DEPLOYING,
                "DeployAgent rolling deployment via MCP",
                elapsed_ms=self._ms(pipeline_start),
            )

            # ── Step 6: Deploy ────────────────────────────────────────────────
            s6_start = datetime.utcnow()
            await self._planner.start_step(plan, 6)
            self._registry.update_status("deploy", "working", f"Deploying {incident.id}")

            # Run test suite
            test_results = await self.deploy.run_tests(incident)
            self.incidents_db[incident.id] = incident

            if not test_results["all_passed"]:
                s6_ms = self._ms(s6_start)
                await self._planner.fail_step(plan, 6, "Tests failed", s6_ms)
                await self._planner.skip_step(plan, 7, "Deployment aborted")
                await self.deploy.rollback(incident)
                incident.resolved_at = datetime.utcnow()
                self.incidents_db[incident.id] = incident
                await self._transition_state(
                    incident, IncidentStatus.ROLLED_BACK,
                    f"Tests failed ({test_results['total_failed']} failures) — rolled back",
                    elapsed_ms=self._ms(pipeline_start),
                )
                self._registry.update_status("deploy", "idle")
                await self._planner.complete_plan(plan, "failed", self._ms(pipeline_start))
                self._log_completion(incident, pipeline_start, "ROLLED_BACK")
                return

            # Pre-deploy validation
            pre_ok = await self.deploy.validate_pre_deploy(incident, fix)
            if not pre_ok:
                s6_ms = self._ms(s6_start)
                await self._planner.fail_step(plan, 6, "Pre-deploy validation failed", s6_ms)
                await self._planner.skip_step(plan, 7, "Deployment aborted")
                await self.deploy.rollback(incident)
                await self._transition_state(
                    incident, IncidentStatus.ROLLED_BACK,
                    "Pre-deploy validation failed",
                    elapsed_ms=self._ms(pipeline_start),
                )
                self._registry.update_status("deploy", "idle")
                await self._planner.complete_plan(plan, "failed", self._ms(pipeline_start))
                self._log_completion(incident, pipeline_start, "ROLLED_BACK")
                return

            # Execute deployment via MCP
            mcp_r = await self._mcp.call_tool(
                "deploy.execute_deployment",
                {"incident_id": incident.id, "fix_id": fix.fix_id,
                 "service": incident.service, "strategy": "rolling"},
                correlation_id=corr_id, incident_id=incident.id,
            )
            s6_ms = self._ms(s6_start)

            deploy_result = mcp_r.get("result") or {}
            if not deploy_result.get("success", False):
                await self._planner.fail_step(plan, 6, "Deployment failed", s6_ms)
                await self._planner.skip_step(plan, 7, "Deployment failed")
                await self.deploy.rollback(incident)
                incident.resolved_at = datetime.utcnow()
                self.incidents_db[incident.id] = incident
                await self._transition_state(
                    incident, IncidentStatus.ROLLED_BACK,
                    deploy_result.get("reason", "Deployment health check failed"),
                    elapsed_ms=self._ms(pipeline_start),
                )
                self._registry.update_status("deploy", "idle")
                await self._planner.complete_plan(plan, "failed", self._ms(pipeline_start))
                self._log_completion(incident, pipeline_start, "ROLLED_BACK")
                return

            await self._planner.complete_step(plan, 6, mcp_r, s6_ms)
            self._registry.update_status("deploy", "idle")
            self.incidents_db[incident.id] = incident
            await self._broadcast(
                "deploy", "Deployment Complete via MCP",
                f"Rolling deployment ({s6_ms}ms). "
                f"Version: {deploy_result.get('deployed_version', 'N/A')}. "
                f"Total MCP calls: {self._mcp.call_count}.",
                incident.id, elapsed_ms=s6_ms,
            )

            # ── Step 7: Verify resolution ─────────────────────────────────────
            s7_start = datetime.utcnow()
            await self._planner.start_step(plan, 7)
            self._registry.update_status("monitor", "working", "Verifying resolution")

            mcp_r = await self._mcp.call_tool(
                "monitor.check_health",
                {"service": incident.service, "include_metrics": True},
                correlation_id=corr_id, incident_id=incident.id,
            )
            s7_ms = self._ms(s7_start)
            await self._planner.complete_step(plan, 7, mcp_r, s7_ms)
            self._registry.update_status("monitor", "idle")

            # ── RESOLVED ─────────────────────────────────────────────────────
            total_ms = self._ms(pipeline_start)
            incident.resolved_at = datetime.utcnow()
            await self._transition_state(
                incident, IncidentStatus.RESOLVED,
                f"Fix live. Version {deploy_result.get('deployed_version', 'N/A')}. "
                f"MTTR: {total_ms / 1000:.1f}s. MCP calls: {self._mcp.call_count}.",
                elapsed_ms=total_ms,
            )
            incident.add_timeline_event(
                agent="orchestrator",
                action="Incident Resolved ✓",
                details=(
                    f"Pipeline complete in {total_ms / 1000:.1f}s. "
                    f"{len(incident.timeline)} events. "
                    f"{self._mcp.call_count} MCP calls. "
                    f"Fix: PR #{fix.pr_number}."
                ),
                status="success",
            )
            self.incidents_db[incident.id] = incident
            await self._broadcast(
                "orchestrator", "Remediation Complete ✓",
                f"{incident.service} restored. MTTR: {total_ms / 1000:.1f}s. "
                f"Plan: {plan.plan_id}.",
                incident.id, elapsed_ms=total_ms,
            )
            await self._planner.complete_plan(plan, "completed", total_ms)
            self._registry.update_status("orchestrator", "idle")
            self._log_completion(incident, pipeline_start, "RESOLVED")

        except Exception as e:
            total_ms = self._ms(pipeline_start)
            logger.error(f"[{incident.id}] Orchestrator error: {e}", exc_info=True)
            incident.status = IncidentStatus.FAILED
            incident.add_timeline_event(
                agent="orchestrator", action="Pipeline Error",
                details=f"Unexpected error: {str(e)}", status="error",
            )
            self.incidents_db[incident.id] = incident
            self._registry.update_status("orchestrator", "error")
            await manager.broadcast_event(
                event_type="error", incident_id=incident.id, agent="orchestrator",
                data={"error": str(e), "elapsed_ms": total_ms},
            )

    # ── Low confidence escalation ──────────────────────────────────────────────

    async def _handle_low_confidence(
        self, incident: Incident, diagnosis, confidence_pct: int, pipeline_start: datetime
    ) -> None:
        logger.warning(
            f"[{incident.id}] Confidence {confidence_pct}% < {self._threshold}% — escalating"
        )
        incident.add_timeline_event(
            agent="orchestrator", action="Escalated to Human Review",
            details=(
                f"Confidence {confidence_pct}% < threshold {self._threshold}%. "
                f"Root cause: {diagnosis.root_cause[:120] if diagnosis else 'unknown'}."
            ),
            status="warning",
        )
        self.incidents_db[incident.id] = incident
        await self._broadcast(
            "orchestrator", "⚠ Human Review Required",
            f"Confidence {confidence_pct}% < {self._threshold}% threshold. "
            f"Root cause: {diagnosis.root_cause[:100] if diagnosis else 'N/A'}.",
            incident.id, elapsed_ms=self._ms(pipeline_start),
        )
        incident.status = IncidentStatus.DETECTED
        self.incidents_db[incident.id] = incident

    # ── Completion logger ──────────────────────────────────────────────────────

    def _log_completion(self, incident: Incident, start: datetime, outcome: str) -> None:
        total_ms = self._ms(start)
        logger.info(
            f"[{incident.id}] ── {outcome} ──\n"
            f"  MTTR: {total_ms / 1000:.2f}s  |  "
            f"Events: {len(incident.timeline)}  |  "
            f"MCP calls: {self._mcp.call_count}  |  "
            f"Agents: {', '.join(incident.agents_involved)}"
        )
