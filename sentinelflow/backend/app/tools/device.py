from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

from app.db.models import DisputeRecord
from app.errors import NotFoundError
from app.schemas.investigation import Evidence
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession


async def fetch_device_context(session: AsyncSession, dispute_id: str) -> Evidence:
    result = await session.execute(select(DisputeRecord).where(DisputeRecord.id == dispute_id))
    dispute = result.scalar_one_or_none()
    if dispute is None:
        raise NotFoundError("DISPUTE_NOT_FOUND", "Dispute was not found.")
    device = dispute.attributes.get("device", {})
    return Evidence(
        id=f"ev_{uuid4().hex[:10]}",
        source="device",
        category="device",
        summary="Loaded device fingerprint and network context.",
        facts={
            "recognized_device": device.get("recognized_device", False),
            "ip_velocity": device.get("ip_velocity", 0),
            "geo_distance_km": device.get("geo_distance_km", 0),
        },
        confidence=0.93,
        collected_at=datetime.now(UTC),
        provenance="postgres:disputes.attributes.device",
    )
