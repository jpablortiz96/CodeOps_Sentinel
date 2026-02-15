"""
DiagnosticAgent — Root cause analysis using Azure OpenAI GPT-4o.

Auto-detects real vs simulation mode via FoundryService:
  - AZURE_OPENAI_KEY set + SIMULATION_MODE=False  → real GPT-4o call
  - Otherwise                                      → curated simulation data

The agent builds a rich incident context (metrics, logs, trace IDs) and sends
it to GPT-4o with an expert SRE/DevOps system prompt that includes few-shot
examples. Response is parsed into the Diagnosis pydantic model.
"""
import asyncio
import json
import re
import logging
from datetime import datetime

import httpx

from config import get_settings
from models.incident import Incident, IncidentSeverity, Diagnosis
from models.agent_messages import AgentStatus
from services.foundry_service import get_foundry_service
from .agent_prompts import DIAGNOSTIC_SYSTEM_PROMPT

settings = get_settings()

logger = logging.getLogger(__name__)


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
        f"DiagnosticAgent: Could not parse AI response as JSON — using fallback. "
        f"Preview: {raw[:200]}"
    )
    return fallback


class DiagnosticAgent:
    """
    Analyzes production incidents using Azure OpenAI GPT-4o.
    Falls back to curated simulation data when no credentials are configured.
    """

    def __init__(self, agent_status: AgentStatus):
        self.name = "diagnostic"
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

    async def _fetch_demo_metrics(self) -> dict:
        """
        Fetch /metrics (Prometheus text) and /chaos/status from the real demo app.
        Returns a dict with raw text + chaos experiment state.
        Falls back gracefully on network errors.
        """
        base = settings.DEMO_APP_URL
        result = {}
        try:
            async with httpx.AsyncClient(timeout=6.0) as client:
                metrics_resp = await client.get(f"{base}/metrics")
                if metrics_resp.status_code == 200:
                    result["prometheus_metrics"] = metrics_resp.text[:2000]

                chaos_resp = await client.get(f"{base}/chaos/status")
                if chaos_resp.status_code == 200:
                    result["chaos_status"] = chaos_resp.json()
        except Exception as exc:
            logger.warning(f"DiagnosticAgent: demo metrics fetch failed: {exc}")
        return result

    def _build_incident_context(self, incident: Incident, demo_extra: dict | None = None) -> str:
        """Format incident data as a structured context string for GPT-4o."""
        m = incident.metrics_snapshot
        logs = m.get("mock_logs", "No structured logs captured in this snapshot.")

        base = (
            f"INCIDENT ID:        {incident.id}\n"
            f"SERVICE:            {incident.service}\n"
            f"SEVERITY:           {incident.severity.upper()}\n"
            f"TITLE:              {incident.title}\n"
            f"DESCRIPTION:        {incident.description}\n"
            f"ENVIRONMENT:        {incident.environment}\n"
            f"AFFECTED USERS:     {incident.affected_users:,}\n"
            f"ERROR COUNT (5min): {incident.error_count:,}\n"
            f"\n"
            f"METRICS SNAPSHOT:\n"
            f"  cpu_percent:       {m.get('cpu_percent', 'N/A')}%\n"
            f"  memory_percent:    {m.get('memory_percent', 'N/A')}%\n"
            f"  memory_usage_mb:   {m.get('memory_usage_mb', 'N/A')} MB\n"
            f"  error_rate:        {m.get('error_rate', 'N/A')}\n"
            f"  avg_latency_ms:    {m.get('avg_latency_ms', m.get('latency_p99_ms', 'N/A'))} ms\n"
            f"  db_connections:    {m.get('db_connections', 'N/A')}\n"
            f"  restart_count:     {m.get('restart_count', 'N/A')}\n"
            f"  last_exit_code:    {m.get('last_exit_code', 'N/A')}\n"
            f"  replication_lag_s: {m.get('replication_lag_s', 'N/A')} s\n"
            f"  request_rate:      {m.get('request_rate', 'N/A')} req/s\n"
            f"  active_chaos:      {m.get('active_chaos', 'N/A')}\n"
            f"\n"
            f"RECENT LOGS (last 15 min):\n{logs}\n"
        )

        if demo_extra:
            chaos = demo_extra.get("chaos_status", {})
            if chaos.get("any_active"):
                experiments = chaos.get("experiments", {})
                active = [
                    f"{name} (running {info.get('running_for', '?')})"
                    for name, info in experiments.items()
                    if info.get("active")
                ]
                base += f"\nACTIVE CHAOS EXPERIMENTS:\n  {', '.join(active)}\n"
            if demo_extra.get("prometheus_metrics"):
                base += f"\nPROMETHEUS METRICS (live):\n{demo_extra['prometheus_metrics']}\n"

        return base

    # ── Response parser ────────────────────────────────────────────────────────

    def _parse_ai_diagnosis(self, raw_json: dict, incident: Incident) -> Diagnosis:
        """Parse GPT-4o JSON response into a Diagnosis model with safe defaults."""
        severity_map = {
            "critical": IncidentSeverity.CRITICAL,
            "high": IncidentSeverity.HIGH,
            "medium": IncidentSeverity.MEDIUM,
            "low": IncidentSeverity.LOW,
        }
        severity = severity_map.get(
            str(raw_json.get("severity", "")).lower(),
            incident.severity,
        )

        # Clamp confidence to a valid float range
        confidence = float(raw_json.get("confidence", 0.80))
        confidence = max(0.01, min(0.99, confidence))

        # Normalize affected_services (may come as string or list from GPT-4o)
        affected = raw_json.get("affected_services", [incident.service])
        if isinstance(affected, str):
            affected = [s.strip() for s in affected.split(",")]

        return Diagnosis(
            root_cause=raw_json.get(
                "root_cause", "Root cause undetermined — manual investigation required"
            ),
            severity=severity,
            affected_services=affected,
            recommended_action=raw_json.get(
                "recommended_action", "Manual investigation required"
            ),
            confidence=round(confidence, 2),
            error_pattern=raw_json.get("error_pattern"),
            log_evidence=raw_json.get("log_evidence"),
        )

    # ── Main method ────────────────────────────────────────────────────────────

    async def diagnose(self, incident: Incident) -> Diagnosis:
        """
        Analyze an incident and determine root cause.

        Flow:
          1. Collect log/metrics context
          2. Send to GPT-4o via FoundryService (or use simulation fallback)
          3. Parse JSON response into Diagnosis model
          4. Emit detailed WebSocket timeline events throughout
        """
        self._set_working(f"Analyzing {incident.id}")
        use_real_ai = self._foundry.use_real_ai
        source_label = "GPT-4o / Azure OpenAI" if use_real_ai else "Simulation Engine"

        # ── Step 1: Log collection ─────────────────────────────────────────────
        incident.add_timeline_event(
            agent=self.name,
            action="Log Collection Started",
            details=(
                f"Fetching logs from {incident.service} (last 15 min). "
                f"Correlating {incident.error_count:,} error events with metrics snapshot."
            ),
            status="info",
        )
        await asyncio.sleep(0.5)

        # ── Step 2: Azure Monitor KQL query ───────────────────────────────────
        incident.add_timeline_event(
            agent=self.name,
            action="KQL Query — Azure Monitor",
            details=(
                f"Querying Log Analytics workspace. "
                f"CPU={incident.metrics_snapshot.get('cpu_percent', '?')}%, "
                f"Memory={incident.metrics_snapshot.get('memory_percent', '?')}%, "
                f"ErrorRate={incident.metrics_snapshot.get('error_rate', '?')}"
            ),
            status="info",
        )
        await asyncio.sleep(0.4)

        # ── Step 3: AI analysis ────────────────────────────────────────────────
        demo_extra = None
        if incident.service == "shopdemo":
            demo_extra = await self._fetch_demo_metrics()
            if demo_extra:
                incident.add_timeline_event(
                    agent=self.name,
                    action="Live Demo-App Metrics Fetched",
                    details=(
                        f"Fetched /metrics and /chaos/status from ShopDemo. "
                        f"Chaos active: {demo_extra.get('chaos_status', {}).get('any_active', False)}"
                    ),
                    status="info",
                )
        context = self._build_incident_context(incident, demo_extra)
        incident.add_timeline_event(
            agent=self.name,
            action=f"Sending Context to {source_label}",
            details=(
                f"Context: {len(context)} chars. "
                f"System prompt includes expert SRE few-shot examples. "
                f"Deployment: {self._foundry.deployment}"
            ),
            status="info",
        )

        result = await self._foundry.chat_completion(
            system_prompt=DIAGNOSTIC_SYSTEM_PROMPT,
            user_message=(
                f"Analyze this production incident and provide root cause analysis:\n\n{context}"
            ),
            temperature=0.1,
            max_tokens=1200,
        )

        # ── Step 4: Parse response ─────────────────────────────────────────────
        fallback = self._foundry.get_mock_diagnosis()

        if result.get("content"):
            parsed = _safe_parse_json(result["content"], fallback)
            diagnosis = self._parse_ai_diagnosis(parsed, incident)
            tokens_info = (
                f"{result.get('tokens_used', '?')} tokens, "
                f"{result.get('latency_ms', '?')} ms"
            )
            logger.info(
                f"DiagnosticAgent: GPT-4o responded for {incident.id} — "
                f"confidence={diagnosis.confidence:.0%}, {tokens_info}"
            )
        else:
            # Simulation or error fallback — always works without credentials
            diagnosis = self._parse_ai_diagnosis(fallback, incident)
            tokens_info = "simulation mode"
            logger.info(
                f"DiagnosticAgent: Simulation data used for {incident.id} "
                f"(source={result.get('source', 'unknown')})"
            )

        incident.diagnosis = diagnosis

        # ── Step 5: Emit results to timeline ──────────────────────────────────
        incident.add_timeline_event(
            agent=self.name,
            action="Root Cause Identified",
            details=(
                f"[{source_label}] [{tokens_info}] "
                f"Confidence: {diagnosis.confidence:.0%}. "
                f"{diagnosis.root_cause[:150]}"
                f"{'...' if len(diagnosis.root_cause) > 150 else ''}"
            ),
            status="success",
        )
        incident.add_timeline_event(
            agent=self.name,
            action="Recommended Remediation",
            details=diagnosis.recommended_action,
            status="info",
        )
        if diagnosis.error_pattern:
            incident.add_timeline_event(
                agent=self.name,
                action="Error Pattern Captured",
                details=f"Alerting rule candidate: {diagnosis.error_pattern}",
                status="info",
            )

        self.status.incidents_handled += 1
        self._set_idle()
        return diagnosis
