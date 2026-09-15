from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

DisputeStatus = Literal["open", "investigating", "pending_review", "closed"]


class DisputeSummary(BaseModel):
    id: str
    case_code: str
    title: str
    amount: float
    currency: str = "USD"
    status: DisputeStatus
    created_at: datetime


class DisputeDetail(DisputeSummary):
    customer_id: str
    merchant_id: str
    narrative: str
    tags: list[str] = Field(default_factory=list)


class DisputeCreateRequest(BaseModel):
    case_code: str | None = None
    title: str = Field(min_length=3, max_length=255)
    narrative: str = Field(min_length=3)
    customer_id: str = Field(min_length=3, max_length=64)
    merchant_id: str = Field(min_length=3, max_length=64)
    amount: float = Field(gt=0)
    currency: str = Field(default="USD", min_length=3, max_length=8)
    status: DisputeStatus = "open"
    attributes: dict[str, object] = Field(default_factory=dict)
