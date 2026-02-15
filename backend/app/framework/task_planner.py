"""
Task Planner — generates and executes dynamic remediation plans.

The TaskPlanner is the strategic brain of the Orchestrator. For each incident
it generates a step-by-step execution plan, executes steps in order,
and can re-plan dynamically if a step fails.

Plan structure:
  Step 1: monitor.get_metrics          → collect baseline data
  Step 2: diagnostic.analyze_incident  → GPT-4o root cause analysis
  Step 3: [confidence gate]            → auto-fix (>=70%) or escalate (<70%)
  Step 4: fixer.generate_patch         → code fix generation
  Step 5: fixer.validate_fix           → safety validation
  Step 6: deploy.execute_deployment    → rolling deployment
  Step 7: monitor.check_health         → verify resolution

All plan updates are broadcast via WebSocket so the dashboard can
render the ExecutionPlan component in real time.
"""
import asyncio
import logging
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class PlanStepStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStep(BaseModel):
    step_num: int
    agent: str                       # Which agent owns this step
    action: str                      # Human-readable action name
    tool: str                        # MCP tool to call
    params: dict = Field(default_factory=dict)
    condition: str = ""              # Human-readable condition for execution
    status: PlanStepStatus = PlanStepStatus.PENDING
    result: Optional[dict] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_ms: Optional[int] = None
    skip_reason: Optional[str] = None


class ExecutionPlan(BaseModel):
    plan_id: str = Field(default_factory=lambda: f"plan-{str(uuid.uuid4())[:8]}")
    incident_id: str
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:12])
    steps: list[PlanStep] = Field(default_factory=list)
    status: str = "planning"         # planning | executing | completed | replanned | failed
    replanned_reason: Optional[str] = None
    replanned_count: int = 0
    created_at: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    completed_at: Optional[str] = None
    total_elapsed_ms: Optional[int] = None
    current_step_num: int = 0


class TaskPlanner:
    """
    Generates and manages dynamic execution plans for incident remediation.

    The planner is created per-incident by the Orchestrator.
    It broadcasts all plan updates via WebSocket for real-time dashboard display.
    """

    def __init__(self, confidence_threshold: int = 70):
        self._threshold = confidence_threshold

    def create_plan(self, incident) -> ExecutionPlan:
        """
        Generate a remediation plan for the given incident.

        The plan is deterministic based on the incident severity and
        contains conditional branches (confidence gate at step 3).
        """
        from models.incident import IncidentSeverity

        is_critical = incident.severity in (
            IncidentSeverity.CRITICAL, IncidentSeverity.HIGH
        )

        steps = [
            PlanStep(
                step_num=1,
                agent="monitor",
                action="Collect Metrics",
                tool="monitor.get_metrics",
                params={"service": incident.service, "window_minutes": 15},
                condition="Always — establish baseline before analysis",
            ),
            PlanStep(
                step_num=2,
                agent="diagnostic",
                action="Analyze Incident (GPT-4o)",
                tool="diagnostic.analyze_incident",
                params={
                    "incident_id": incident.id,
                    "service": incident.service,
                    "description": incident.description,
                },
                condition="After metrics collected — root cause analysis",
            ),
            PlanStep(
                step_num=3,
                agent="orchestrator",
                action=f"Confidence Gate (≥{self._threshold}% → auto-fix)",
                tool="orchestrator.evaluate_confidence",
                params={"threshold": self._threshold},
                condition=(
                    f"If confidence ≥ {self._threshold}%: proceed to fix. "
                    f"If confidence < {self._threshold}%: escalate to human review."
                ),
            ),
            PlanStep(
                step_num=4,
                agent="fixer",
                action="Generate Code Fix (GPT-4o)",
                tool="fixer.generate_patch",
                params={
                    "incident_id": incident.id,
                    "service": incident.service,
                },
                condition=f"Only if confidence ≥ {self._threshold}% (step 3 passed)",
            ),
            PlanStep(
                step_num=5,
                agent="fixer",
                action="Validate Fix",
                tool="fixer.validate_fix",
                params={"incident_id": incident.id},
                condition="After patch generated — security + static analysis",
            ),
            PlanStep(
                step_num=6,
                agent="deploy",
                action="Execute Rolling Deployment",
                tool="deploy.execute_deployment",
                params={
                    "incident_id": incident.id,
                    "service": incident.service,
                    "strategy": "rolling",
                },
                condition="After fix validated — rolling deployment with health checks",
            ),
            PlanStep(
                step_num=7,
                agent="monitor",
                action="Verify Resolution",
                tool="monitor.check_health",
                params={"service": incident.service},
                condition="After deployment — confirm service health restored",
            ),
        ]

        plan = ExecutionPlan(
            incident_id=incident.id,
            steps=steps,
        )
        logger.info(
            f"TaskPlanner: Plan {plan.plan_id} created for {incident.id} "
            f"({len(steps)} steps, threshold={self._threshold}%)"
        )
        return plan

    async def replan(
        self,
        plan: ExecutionPlan,
        failed_step: PlanStep,
        reason: str,
    ) -> ExecutionPlan:
        """
        Generate a modified plan after a step failure.

        Current strategy: skip remaining automatic steps and add
        a human-review escalation step.
        """
        logger.warning(
            f"TaskPlanner: Re-planning {plan.plan_id} — "
            f"step {failed_step.step_num} failed: {reason}"
        )

        # Mark remaining pending steps as skipped
        for step in plan.steps:
            if step.status == PlanStepStatus.PENDING:
                step.status = PlanStepStatus.SKIPPED
                step.skip_reason = f"Skipped due to replan: {reason}"

        # Append escalation step
        escalation = PlanStep(
            step_num=len(plan.steps) + 1,
            agent="orchestrator",
            action="Escalate to Human Review",
            tool="orchestrator.escalate",
            params={"reason": reason, "failed_step": failed_step.step_num},
            condition="Automatic after step failure — human intervention required",
            status=PlanStepStatus.PENDING,
        )
        plan.steps.append(escalation)

        plan.status = "replanned"
        plan.replanned_reason = reason
        plan.replanned_count += 1

        await self._broadcast_plan(plan)
        return plan

    # ── Step lifecycle helpers ─────────────────────────────────────────────────

    async def start_step(self, plan: ExecutionPlan, step_num: int) -> PlanStep:
        """Mark a step as in-progress and broadcast the update."""
        step = self._get_step(plan, step_num)
        if step:
            step.status = PlanStepStatus.IN_PROGRESS
            step.started_at = datetime.utcnow().isoformat()
            plan.current_step_num = step_num
            plan.status = "executing"
            await self._broadcast_plan_step(plan, step)
        return step

    async def complete_step(
        self,
        plan: ExecutionPlan,
        step_num: int,
        result: dict,
        elapsed_ms: int,
    ) -> PlanStep:
        """Mark a step as completed and broadcast the update."""
        step = self._get_step(plan, step_num)
        if step:
            step.status = PlanStepStatus.COMPLETED
            step.result = result
            step.elapsed_ms = elapsed_ms
            step.completed_at = datetime.utcnow().isoformat()
            await self._broadcast_plan_step(plan, step)
        return step

    async def fail_step(
        self,
        plan: ExecutionPlan,
        step_num: int,
        error: str,
        elapsed_ms: int,
    ) -> PlanStep:
        """Mark a step as failed and broadcast the update."""
        step = self._get_step(plan, step_num)
        if step:
            step.status = PlanStepStatus.FAILED
            step.result = {"error": error}
            step.elapsed_ms = elapsed_ms
            step.completed_at = datetime.utcnow().isoformat()
            await self._broadcast_plan_step(plan, step)
        return step

    async def skip_step(
        self,
        plan: ExecutionPlan,
        step_num: int,
        reason: str,
    ) -> PlanStep:
        """Mark a step as skipped (e.g. confidence gate not met)."""
        step = self._get_step(plan, step_num)
        if step:
            step.status = PlanStepStatus.SKIPPED
            step.skip_reason = reason
            step.completed_at = datetime.utcnow().isoformat()
            await self._broadcast_plan_step(plan, step)
        return step

    async def complete_plan(
        self, plan: ExecutionPlan, outcome: str, total_ms: int
    ) -> None:
        """Finalize the plan and broadcast completion."""
        plan.status = outcome  # "completed" | "failed" | "escalated"
        plan.completed_at = datetime.utcnow().isoformat()
        plan.total_elapsed_ms = total_ms
        await self._broadcast_plan(plan)

    # ── Broadcast helpers ──────────────────────────────────────────────────────

    async def _broadcast_plan(self, plan: ExecutionPlan) -> None:
        """Broadcast the full plan state."""
        try:
            from api.websocket import manager

            await manager.broadcast_event(
                event_type="plan_created",
                incident_id=plan.incident_id,
                agent="orchestrator",
                data=plan.model_dump(),
            )
        except Exception as e:
            logger.warning(f"TaskPlanner: Failed to broadcast plan: {e}")

    async def _broadcast_plan_step(
        self, plan: ExecutionPlan, step: PlanStep
    ) -> None:
        """Broadcast a single step status update."""
        try:
            from api.websocket import manager

            await manager.broadcast_event(
                event_type="plan_step_update",
                incident_id=plan.incident_id,
                agent=step.agent,
                data={
                    "plan_id": plan.plan_id,
                    "incident_id": plan.incident_id,
                    "step": step.model_dump(),
                    "plan_status": plan.status,
                    "current_step_num": plan.current_step_num,
                },
            )
        except Exception as e:
            logger.warning(f"TaskPlanner: Failed to broadcast step update: {e}")

    # ── Internal ───────────────────────────────────────────────────────────────

    def _get_step(self, plan: ExecutionPlan, step_num: int) -> Optional[PlanStep]:
        for step in plan.steps:
            if step.step_num == step_num:
                return step
        return None
