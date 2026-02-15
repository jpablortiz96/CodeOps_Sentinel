"""
Agent-to-Agent (A2A) Protocol — standardized message format for inter-agent communication.

All agent communication in CodeOps Sentinel flows through structured A2AMessage
objects. This enables:
  - Full traceability of the incident pipeline
  - Correlation of related messages via correlation_id
  - Replay and audit capabilities
  - Dashboard visualization of message flows

Message flow for a typical incident:
  orchestrator → monitor      [REQUEST]  monitor.get_metrics
  monitor      → orchestrator [RESPONSE] {metrics snapshot}
  orchestrator → diagnostic   [REQUEST]  diagnostic.analyze_incident
  diagnostic   → orchestrator [RESPONSE] {diagnosis, confidence=0.94}
  orchestrator → fixer        [REQUEST]  fixer.generate_patch
  fixer        → orchestrator [RESPONSE] {fix, pr_url}
  orchestrator → deploy       [REQUEST]  deploy.execute_deployment
  deploy       → orchestrator [RESPONSE] {success, version}
  orchestrator → *            [EVENT]    incident.resolved
"""
import uuid
from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class MessageType(str, Enum):
    REQUEST = "REQUEST"    # Agent requesting another agent to do something
    RESPONSE = "RESPONSE"  # Reply to a REQUEST
    EVENT = "EVENT"        # Broadcast notification (no reply expected)
    ERROR = "ERROR"        # Error response to a failed REQUEST


class A2AMessage(BaseModel):
    """
    A structured message between two agents.

    The correlation_id ties all messages belonging to the same
    incident pipeline together (across multiple agents and steps).
    """

    message_id: str = Field(
        default_factory=lambda: f"msg-{str(uuid.uuid4())[:8]}"
    )
    correlation_id: str = Field(
        default_factory=lambda: str(uuid.uuid4())[:12],
        description="Shared ID for the entire incident pipeline trace.",
    )
    from_agent: str
    to_agent: str
    message_type: MessageType
    tool_name: str = ""  # MCP tool being called/responding to
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: str = Field(
        default_factory=lambda: datetime.utcnow().isoformat()
    )
    elapsed_ms: Optional[int] = None
    incident_id: Optional[str] = None
    step_num: Optional[int] = None  # Which plan step this message belongs to

    def to_response(
        self, payload: dict, elapsed_ms: Optional[int] = None
    ) -> "A2AMessage":
        """Create a RESPONSE message based on this REQUEST."""
        return A2AMessage(
            correlation_id=self.correlation_id,
            from_agent=self.to_agent,
            to_agent=self.from_agent,
            message_type=MessageType.RESPONSE,
            tool_name=self.tool_name,
            payload=payload,
            elapsed_ms=elapsed_ms,
            incident_id=self.incident_id,
            step_num=self.step_num,
        )

    def to_error(self, error: str, elapsed_ms: Optional[int] = None) -> "A2AMessage":
        """Create an ERROR message based on this REQUEST."""
        return A2AMessage(
            correlation_id=self.correlation_id,
            from_agent=self.to_agent,
            to_agent=self.from_agent,
            message_type=MessageType.ERROR,
            tool_name=self.tool_name,
            payload={"error": error},
            elapsed_ms=elapsed_ms,
            incident_id=self.incident_id,
            step_num=self.step_num,
        )


def make_request(
    from_agent: str,
    to_agent: str,
    tool_name: str,
    payload: dict,
    correlation_id: Optional[str] = None,
    incident_id: Optional[str] = None,
    step_num: Optional[int] = None,
) -> A2AMessage:
    """Factory for creating A2A REQUEST messages."""
    return A2AMessage(
        correlation_id=correlation_id or str(uuid.uuid4())[:12],
        from_agent=from_agent,
        to_agent=to_agent,
        message_type=MessageType.REQUEST,
        tool_name=tool_name,
        payload=payload,
        incident_id=incident_id,
        step_num=step_num,
    )


def make_event(
    from_agent: str,
    event_name: str,
    payload: dict,
    correlation_id: Optional[str] = None,
    incident_id: Optional[str] = None,
) -> A2AMessage:
    """Factory for creating broadcast EVENT messages."""
    return A2AMessage(
        correlation_id=correlation_id or str(uuid.uuid4())[:12],
        from_agent=from_agent,
        to_agent="broadcast",
        message_type=MessageType.EVENT,
        tool_name=event_name,
        payload=payload,
        incident_id=incident_id,
    )
