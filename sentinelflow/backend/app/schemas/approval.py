from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ApprovalDecision(BaseModel):
    decision: Literal["approve", "deny"]
    comment: str = Field(min_length=1, max_length=4000)


class ApprovalRecord(BaseModel):
    user_id: str
    role: str
    decision: Literal["approve", "deny"]
    comment: str
    timestamp: datetime
    dispute_id: str
    investigation_id: str
    risk_score: float
    recommendation_version: str
    checkpoint_id: str
