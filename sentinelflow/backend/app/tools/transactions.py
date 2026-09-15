from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.db.models import DisputeRecord
from app.errors import NotFoundError
from app.schemas.investigation import Evidence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_transaction_history(session: AsyncSession, dispute_id: str) -> Evidence:
    result = await session.execute(select(DisputeRecord).where(DisputeRecord.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if dispute is None:
        raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
    transaction = dispute.attributes.get("transaction", {})
    return Evidence(
        id=f"ev_{uuid4().hex[:10]}",
        source="transactions",
        category="transaction",
        summary="Fetched transaction history from the payments ledger.",
        facts={
            "amount": dispute.amount,
            "currency": dispute.currency,
            "velocity_24h": transaction.get("velocity_24h", 1),
            "geo_anomaly": transaction.get("geo_anomaly", False),
            "authorization_events": transaction.get("authorization_events", []),
        },
        confidence=0.98,
        collected_at=datetime.now(UTC),
        provenance="postgres:disputes.attributes.transaction",
    )
