from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.db.models import DisputeRecord
from app.errors import NotFoundError
from app.schemas.investigation import Evidence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_merchant_profile(session: AsyncSession, dispute_id: str) -> Evidence:
    result = await session.execute(select(DisputeRecord).where(DisputeRecord.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if dispute is None:
        raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
    merchant = dispute.attributes.get("merchant", {})
    return Evidence(
        id=f"ev_{uuid4().hex[:10]}",
        source="merchant",
        category="merchant",
        summary="Fetched merchant profile and historical risk posture.",
        facts={
            "merchant_risk": merchant.get("merchant_risk", 0.2),
            "chargeback_rate": merchant.get("chargeback_rate", 0.0),
        },
        confidence=0.91,
        collected_at=datetime.now(UTC),
        provenance="postgres:disputes.attributes.merchant",
    )
