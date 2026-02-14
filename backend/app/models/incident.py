from pydantic import BaseModel, Field
from enum import Enum
from datetime import datetime
from typing import Optional, List
import uuid


class IncidentSeverity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class IncidentStatus(str, Enum):
    DETECTED = "DETECTED"
    DIAGNOSING = "DIAGNOSING"
    FIXING = "FIXING"
    DEPLOYING = "DEPLOYING"
    RESOLVED = "RESOLVED"
    ROLLED_BACK = "ROLLED_BACK"
    FAILED = "FAILED"


class IncidentTimeline(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    agent: str
    action: str
    details: str
    status: str = "info"  # info | success | error | warning


class Diagnosis(BaseModel):
    root_cause: str
    severity: IncidentSeverity
    affected_services: List[str]
    recommended_action: str
    confidence: float = Field(ge=0.0, le=1.0, default=0.85)
    error_pattern: Optional[str] = None
    log_evidence: Optional[str] = None


class Fix(BaseModel):
    fix_id: str = Field(default_factory=lambda: str(uuid.uuid4())[:8])
    description: str
    file_path: str
    original_code: str
    fixed_code: str
    pr_url: Optional[str] = None
    pr_number: Optional[int] = None


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: f"INC-{str(uuid.uuid4())[:8].upper()}")
    title: str
    description: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.DETECTED
    service: str
    environment: str = "production"
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = None
    agents_involved: List[str] = Field(default_factory=list)
    timeline: List[IncidentTimeline] = Field(default_factory=list)
    diagnosis: Optional[Diagnosis] = None
    fix: Optional[Fix] = None
    error_count: int = 0
    affected_users: int = 0
    metrics_snapshot: dict = Field(default_factory=dict)

    def add_timeline_event(self, agent: str, action: str, details: str, status: str = "info"):
        event = IncidentTimeline(
            agent=agent,
            action=action,
            details=details,
            status=status,
        )
        self.timeline.append(event)
        if agent not in self.agents_involved:
            self.agents_involved.append(agent)
        return event
