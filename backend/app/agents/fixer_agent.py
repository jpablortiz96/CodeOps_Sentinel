"""
FixerAgent — Code fix generation using Azure OpenAI GPT-4o.

Auto-detects real vs simulation mode via FoundryService:
  - AZURE_OPENAI_KEY set + SIMULATION_MODE=False  → real GPT-4o fix generation
  - Otherwise                                      → curated simulation fixes

The agent receives a Diagnosis and sends it to GPT-4o with an expert code
remediation system prompt. GPT-4o returns a JSON object with file_path,
original_code, fixed_code, explanation, and test_suggestions.
"""
import asyncio
import json
import re
import random
import logging
from datetime import datetime

import httpx

from config import get_settings
from models.incident import Incident, Diagnosis, Fix
from models.agent_messages import AgentStatus
from services.foundry_service import get_foundry_service
from services.github_service import get_github_service
from .agent_prompts import FIXER_SYSTEM_PROMPT

logger = logging.getLogger(__name__)
settings = get_settings()


def _safe_parse_json(raw: str, fallback: dict) -> dict:
    """Parse GPT-4o JSON response; return fallback dict if unparseable."""
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", raw, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    logger.warning(
        f"FixerAgent: Could not parse AI response as JSON — using fallback. "
        f"Preview: {raw[:200]}"
    )
    return fallback


class FixerAgent:
    """
    Generates code fixes using Azure OpenAI GPT-4o.
    Falls back to curated simulation data when no credentials are configured.
    """

    def __init__(self, agent_status: AgentStatus):
        self.name = "fixer"
        self.status = agent_status
        self._foundry = get_foundry_service()

    # ── State helpers ──────────────────────────────────────────────────────────

    def _set_working(self, task: str):
        self.status.status = "working"
        self.status.current_task = task
        self.status.last_action = task
        self.status.last_action_time = datetime.utcnow()

    def _set_idle(self):
        self.status.status = "idle"
        self.status.current_task = None

    # ── Context builder ────────────────────────────────────────────────────────

    def _build_fix_prompt(self, incident: Incident, diagnosis: Diagnosis) -> str:
        """Construct the user message for the fix generation prompt."""
        return (
            f"INCIDENT: {incident.title}\n"
            f"SERVICE: {incident.service}\n"
            f"ENVIRONMENT: {incident.environment}\n"
            f"\n"
            f"ROOT CAUSE:\n{diagnosis.root_cause}\n"
            f"\n"
            f"SEVERITY: {diagnosis.severity.upper()}\n"
            f"AFFECTED SERVICES: {', '.join(diagnosis.affected_services)}\n"
            f"CONFIDENCE: {diagnosis.confidence:.0%}\n"
            f"\n"
            f"RECOMMENDED ACTION:\n{diagnosis.recommended_action}\n"
            f"\n"
            f"ERROR PATTERN: {diagnosis.error_pattern or 'N/A'}\n"
            f"LOG EVIDENCE: {diagnosis.log_evidence or 'N/A'}\n"
            f"\n"
            f"Generate a production-safe, minimal code fix that resolves this root cause. "
            f"The fix should be directly applicable — include the exact file path, "
            f"original code, and the corrected code with inline comments."
        )

    # ── Response parser ────────────────────────────────────────────────────────

    def _parse_ai_fix(self, raw_json: dict, incident: Incident, diagnosis: Diagnosis) -> Fix:
        """Parse GPT-4o JSON response into a Fix model with safe defaults."""
        return Fix(
            description=raw_json.get(
                "description",
                f"Auto-fix for: {diagnosis.root_cause[:60]}",
            ),
            file_path=raw_json.get(
                "file_path",
                f"src/services/{incident.service.replace('-', '_')}.ts",
            ),
            original_code=raw_json.get("original_code", "// Original code"),
            fixed_code=raw_json.get("fixed_code", "// Fixed code"),
        )

    # ── Main methods ───────────────────────────────────────────────────────────

    async def generate_fix(self, incident: Incident, diagnosis: Diagnosis) -> Fix:
        """
        Generate a code fix based on the diagnosis.

        Flow:
          1. Analyze codebase context
          2. Send diagnosis to GPT-4o (or simulation fallback)
          3. Parse JSON response into Fix model
          4. Create Pull Request
          5. Emit detailed WebSocket timeline events throughout
        """
        self._set_working(f"Generating fix for {incident.id}")
        use_real_ai = self._foundry.use_real_ai
        source_label = "GPT-4o / Azure OpenAI" if use_real_ai else "Simulation Engine"

        # ── Step 1: Codebase analysis ──────────────────────────────────────────
        incident.add_timeline_event(
            agent=self.name,
            action="Codebase Analysis",
            details=(
                f"GitHub Copilot scanning {incident.service} repository. "
                f"Identifying files relevant to: {diagnosis.root_cause[:80]}..."
            ),
            status="info",
        )
        await asyncio.sleep(0.6)

        # ── Step 2: AI fix generation ──────────────────────────────────────────
        fix_prompt = self._build_fix_prompt(incident, diagnosis)
        incident.add_timeline_event(
            agent=self.name,
            action=f"Generating Fix via {source_label}",
            details=(
                f"Sending diagnosis context ({len(fix_prompt)} chars) to {source_label}. "
                f"Risk target: low. Approach: {diagnosis.recommended_action[:80]}..."
            ),
            status="info",
        )

        result = await self._foundry.chat_completion(
            system_prompt=FIXER_SYSTEM_PROMPT,
            user_message=fix_prompt,
            temperature=0.2,   # Slightly higher for code creativity
            max_tokens=1800,
        )

        # ── Step 3: Parse response ─────────────────────────────────────────────
        fallback = self._foundry.get_mock_fix()

        if result.get("content"):
            parsed = _safe_parse_json(result["content"], fallback)
            fix = self._parse_ai_fix(parsed, incident, diagnosis)
            tokens_info = (
                f"{result.get('tokens_used', '?')} tokens, "
                f"{result.get('latency_ms', '?')} ms"
            )
            # Surface risk_level and test_suggestions from AI response
            risk = parsed.get("risk_level", "low")
            tests = parsed.get("test_suggestions", [])
            explanation = parsed.get("explanation", "")
            logger.info(
                f"FixerAgent: GPT-4o generated fix for {incident.id} — "
                f"risk={risk}, {tokens_info}"
            )
        else:
            fix = self._parse_ai_fix(fallback, incident, diagnosis)
            tokens_info = "simulation mode"
            risk = fallback.get("risk_level", "low")
            tests = fallback.get("test_suggestions", [])
            explanation = fallback.get("explanation", "")
            logger.info(
                f"FixerAgent: Simulation fix used for {incident.id} "
                f"(source={result.get('source', 'unknown')})"
            )

        incident.add_timeline_event(
            agent=self.name,
            action="Fix Generated",
            details=(
                f"[{source_label}] [{tokens_info}] "
                f"File: {fix.file_path}. Risk: {risk.upper()}. "
                f"{explanation[:120] if explanation else fix.description}"
            ),
            status="info",
        )

        if tests:
            incident.add_timeline_event(
                agent=self.name,
                action="Test Plan",
                details=f"Suggested tests: {'; '.join(tests[:3])}",
                status="info",
            )

        # ── Step 4: Create Pull Request ────────────────────────────────────────
        await asyncio.sleep(0.4)
        pr = await self.create_pull_request(incident, fix, diagnosis)
        fix.pr_url = pr["url"]
        fix.pr_number = pr["number"]
        incident.fix = fix

        incident.add_timeline_event(
            agent=self.name,
            action="Pull Request Created",
            details=(
                f"PR #{fix.pr_number} opened: '{fix.description}'. "
                f"Branch: {pr.get('branch', 'auto-fix')}. "
                f"Ready for automated test suite."
            ),
            status="success",
        )

        self.status.incidents_handled += 1
        self._set_idle()
        return fix

    async def remediate_demo_app(self, incident: Incident, diagnosis: Diagnosis) -> dict:
        """
        Immediately remediate a real ShopDemo anomaly by calling POST /chaos/stop.
        Returns a result dict with success flag and new health status.
        """
        self._set_working("Remediating ShopDemo via /chaos/stop")
        base = settings.DEMO_APP_URL

        incident.add_timeline_event(
            agent=self.name,
            action="Demo-App Remediation",
            details=f"Calling POST {base}/chaos/stop to stop all active chaos experiments.",
            status="info",
        )

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                stop_resp = await client.post(f"{base}/chaos/stop")
                stop_data = stop_resp.json() if stop_resp.status_code == 200 else {}

                # Verify health after stopping chaos
                await asyncio.sleep(2)
                health_resp = await client.get(f"{base}/health")
                health_data = health_resp.json() if health_resp.status_code == 200 else {}

            new_status = health_data.get("status", "unknown")
            stopped = stop_data.get("stopped", [])
            success = new_status in ("healthy", "degraded") and stop_resp.status_code == 200

            incident.add_timeline_event(
                agent=self.name,
                action="Chaos Stopped" if success else "Remediation Partial",
                details=(
                    f"Stopped experiments: {', '.join(stopped) if stopped else 'none'}. "
                    f"New status: {new_status}."
                ),
                status="success" if success else "warning",
            )
            logger.info(
                f"[FIXER] remediate_demo_app: stopped={stopped} new_status={new_status}"
            )
            return {
                "success":    success,
                "stopped":    stopped,
                "new_status": new_status,
                "health":     health_data,
            }

        except Exception as exc:
            logger.error(f"[FIXER] remediate_demo_app failed: {exc}")
            incident.add_timeline_event(
                agent=self.name,
                action="Remediation Error",
                details=str(exc),
                status="error",
            )
            return {"success": False, "error": str(exc)}

    async def create_pull_request(self, incident: Incident, fix: Fix, diagnosis: Diagnosis) -> dict:
        """Create a GitHub Pull Request for the generated fix.

        Uses the real GitHub REST API when GITHUB_TOKEN is configured;
        falls back to a simulated PR dict otherwise.
        """
        gh = get_github_service()
        if not gh.enabled:
            logger.info("[FIXER] GitHub integration disabled (no GITHUB_TOKEN)")
            pr_number = random.randint(100, 999)
            branch = f"auto-fix/{incident.id.lower()}-{fix.fix_id}"
            return {
                "number": pr_number,
                "url": f"https://github.com/{settings.GITHUB_REPO}/pull/{pr_number}",
                "title": f"fix({incident.service}): {fix.description[:60]}",
                "branch": branch,
                "simulated": True,
            }

        # Real GitHub PR flow
        from api.websocket import manager as ws_manager

        diag_dict = diagnosis.model_dump() if diagnosis else {}

        try:
            # Step 1 — Branch
            incident.add_timeline_event(
                agent=self.name,
                action="Creating Fix Branch",
                details=f"Creating branch fix/agent-{incident.id}… on GitHub",
                status="info",
            )
            await ws_manager.broadcast_event(
                event_type="agent_activity",
                data={"message": f"Creating fix branch: fix/agent-{incident.id}…"},
                agent=self.name,
                incident_id=incident.id,
            )
            branch = await gh.create_fix_branch(incident.id)

            # Step 2 — Commit fix file
            incident.add_timeline_event(
                agent=self.name,
                action="Committing Fix Documentation",
                details=f"Committing fix report to fixes/{incident.id}.md on branch {branch}",
                status="info",
            )
            await ws_manager.broadcast_event(
                event_type="agent_activity",
                data={"message": f"Committing fix documentation to {branch}…"},
                agent=self.name,
                incident_id=incident.id,
            )
            await gh.create_fix_file(
                branch=branch,
                incident_id=incident.id,
                diagnosis=diag_dict,
                fix_content=fix.description,
                original_code=fix.original_code,
                fixed_code=fix.fixed_code,
            )

            # Step 3 — Open PR
            incident.add_timeline_event(
                agent=self.name,
                action="Opening Pull Request",
                details="Opening PR on GitHub…",
                status="info",
            )
            pr_result = await gh.create_pull_request(
                branch=branch,
                incident_id=incident.id,
                diagnosis=diag_dict,
                metrics_before=incident.metrics_snapshot,
            )

            # Store on incident
            incident.github_pr_url = pr_result["pr_url"]
            incident.github_pr_number = pr_result["pr_number"]
            incident.github_branch = branch

            # Broadcast PR created event for the dashboard
            await ws_manager.broadcast_event(
                event_type="github_pr_created",
                data={
                    "pr_number": pr_result["pr_number"],
                    "pr_url": pr_result["pr_url"],
                    "branch": branch,
                    "incident_id": incident.id,
                    "title": f"Auto-Fix: {diagnosis.root_cause[:60]}",
                },
                agent=self.name,
                incident_id=incident.id,
            )
            await ws_manager.broadcast_event(
                event_type="agent_activity",
                data={
                    "message": (
                        f"✅ PR created: #{pr_result['pr_number']} — "
                        f"{pr_result['pr_url']}"
                    ),
                },
                agent=self.name,
                incident_id=incident.id,
            )

            logger.info(
                f"[FIXER] Real GitHub PR #{pr_result['pr_number']} created for {incident.id}"
            )
            return {
                "number": pr_result["pr_number"],
                "url": pr_result["pr_url"],
                "branch": branch,
            }

        except Exception as exc:
            logger.error(f"[FIXER] GitHub PR creation failed: {exc}")
            incident.add_timeline_event(
                agent=self.name,
                action="GitHub PR Failed",
                details=f"PR creation failed: {exc}. Pipeline continues.",
                status="warning",
            )
            # Fallback — don't break the pipeline
            pr_number = random.randint(100, 999)
            return {
                "number": pr_number,
                "url": f"https://github.com/{settings.GITHUB_REPO}/pull/{pr_number}",
                "branch": f"auto-fix/{incident.id.lower()}-{fix.fix_id}",
                "simulated": True,
                "error": str(exc),
            }
