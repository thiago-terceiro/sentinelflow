from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

StreamEventType = Literal[
    "run_started",
    "agent_message",
    "agent_status_updated",
    "tool_started",
    "tool_completed",
    "analyzer_started",
    "analyzer_completed",
    "evidence_added",
    "hypothesis_updated",
    "risk_updated",
    "final_report_ready",
    "approval_required",
    "guardrail_triggered",
    "hallucination_detected",
    "run_completed",
    "run_failed",
    "heartbeat",
]


class StreamEvent(BaseModel):
    id: str
    type: StreamEventType
    timestamp: datetime
    data: dict[str, Any] = Field(default_factory=dict)
