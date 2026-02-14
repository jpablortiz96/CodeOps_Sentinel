from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Any, Optional
import uuid


class MessageType(str, Enum):
    INCIDENT_DETECTED = "INCIDENT_DETECTED"
    DIAGNOSIS_COMPLETE = "DIAGNOSIS_COMPLETE"
    FIX_GENERATED = "FIX_GENERATED"
    DEPLOY_STARTED = "DEPLOY_STARTED"
    DEPLOY_COMPLETE = "DEPLOY_COMPLETE"
    ROLLBACK_TRIGGERED = "ROLLBACK_TRIGGERED"
    STATUS_UPDATE = "STATUS_UPDATE"
    ERROR = "ERROR"
    HEARTBEAT = "HEARTBEAT"


class AgentMessage(BaseModel):
    message_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    from_agent: str
    to_agent: str
    message_type: MessageType
    payload: dict = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    correlation_id: Optional[str] = None  # Links messages in same incident flow


class WebSocketEvent(BaseModel):
    event_type: str
    incident_id: Optional[str] = None
    agent: Optional[str] = None
    data: Any = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentStatus(BaseModel):
    agent_name: str
    status: str = "idle"  # idle | working | done | error
    current_task: Optional[str] = None
    last_action: Optional[str] = None
    last_action_time: Optional[datetime] = None
    incidents_handled: int = 0
    success_rate: float = 1.0
