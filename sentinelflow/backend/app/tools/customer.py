from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.db.models import DisputeRecord
from app.errors import NotFoundError
from app.schemas.investigation import Evidence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_customer_profile(session: AsyncSession, dispute_id: str) -> Evidence:
    result = await session.execute(select(DisputeRecord).where(DisputeRecord.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if dispute is None:
        raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
    customer = dispute.attributes.get("customer", {})
    return Evidence(
        id=f"ev_{uuid4().hex[:10]}",
        source="customer",
        category="customer",
        summary="Loaded customer history and prior dispute behavior.",
        facts={
            "prior_disputes": customer.get("prior_disputes", 0),
            "prior_fraud_signals": customer.get("prior_fraud_signals", 0),
            "tenure_years": customer.get("tenure_years", 0),
        },
        confidence=0.94,
        collected_at=datetime.now(UTC),
        provenance="postgres:disputes.attributes.customer",
    )
