"""Unit tests for Continuous Learning Flywheel (DPO / SFT Dataset Exporter)."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import httpx
import pytest
from app.api.deps import get_db_session
from app.db.models import AuditRecord, Base, DisputeRecord, InvestigationRecord
from app.main import app
from app.services.tuning_export import export_tuning_dataset, serialize_samples_to_jsonl
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def test_db_session_factory():
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    try:
        yield session_factory
    finally:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()


@pytest.fixture
async def test_session(test_db_session_factory) -> AsyncIterator[AsyncSession]:
    async with test_db_session_factory() as session:
        yield session


@pytest.fixture
async def test_client(test_db_session_factory) -> AsyncIterator[httpx.AsyncClient]:
    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with test_db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db_session, None)


@pytest.mark.asyncio
async def test_tuning_dataset_export_service(test_session: AsyncSession) -> None:
    """Tests programmatic export of DPO pairs from audit records."""
    # Seed test dispute and investigation
    dsp = DisputeRecord(
        id=f"dsp_test_{uuid4().hex[:8]}",
        case_code=f"CASE-{uuid4().hex[:4]}",
        title="Unauthorized card charge",
        amount=199.99,
        currency="USD",
        customer_id="cust_8201",
        merchant_id="merch_4920",
        narrative="Customer noticed unverified subscription fee.",
        attributes={"tags": ["subscription", "chargeback"]},
    )
    test_session.add(dsp)
    await test_session.flush()

    inv = InvestigationRecord(
        id=f"inv_test_{uuid4().hex[:8]}",
        dispute_id=dsp.id,
        thread_id=f"th_{uuid4().hex[:8]}",
        status="completed",
        created_by="system",
    )
    test_session.add(inv)
    await test_session.flush()

    # Seed audit records: synthesis + human correction
    rec_synthesis = AuditRecord(
        id=str(uuid4()),
        investigation_id=inv.id,
        dispute_id=dsp.id,
        actor_id="system",
        actor_role="agent",
        event_name="investigation.synthesis",
        payload={"recommendation": "deny", "confidence": 0.88},
        sequence_no=1,
    )
    rec_correction = AuditRecord(
        id=str(uuid4()),
        investigation_id=inv.id,
        dispute_id=dsp.id,
        actor_id="auditor_jane",
        actor_role="auditor",
        event_name="investigation.correction_recorded",
        payload={
            "reason_code": "CUSTOMER_CANCELLATION_VERIFIED",
            "note": "Customer proved timely subscription cancellation via email logs.",
        },
        sequence_no=2,
    )
    test_session.add_all([rec_synthesis, rec_correction])
    await test_session.commit()

    # 1. Test DPO export
    dpo_samples = await export_tuning_dataset(test_session, export_type="dpo", limit=10)
    target = next((s for s in dpo_samples if s.investigation_id == inv.id), None)
    assert target is not None
    assert target.export_type == "dpo"
    assert "Disputed Amount: $199.99" in target.prompt
    assert "CUSTOMER_CANCELLATION_VERIFIED" in target.chosen
    assert target.rejected is not None
    assert "DENIED" in target.rejected
    assert target.metadata["has_human_correction"] is True

    # 2. Test SFT export
    sft_samples = await export_tuning_dataset(test_session, export_type="sft", limit=10)
    sft_target = next((s for s in sft_samples if s.investigation_id == inv.id), None)
    assert sft_target is not None
    assert sft_target.export_type == "sft"
    assert sft_target.rejected is None

    # 3. Test JSONL serialization
    jsonl = serialize_samples_to_jsonl([target])
    assert jsonl.endswith("\n")
    parsed = json.loads(jsonl.strip())
    assert parsed["id"] == target.id
    assert parsed["prompt"] == target.prompt


@pytest.mark.asyncio
async def test_tuning_export_endpoint_rbac_and_formats(test_client: httpx.AsyncClient) -> None:
    """Verifies RBAC access controls and JSONL / JSON download formats on endpoint."""
    # 1. Unauthorized access (investigator role lacks export permissions)
    unauth_resp = await test_client.get(
        "/api/v1/audit/export/tuning",
        headers={"Authorization": "Bearer dev-investigator"},
    )
    assert unauth_resp.status_code == 403

    # 2. Auditor access (default JSONL format)
    auth_resp = await test_client.get(
        "/api/v1/audit/export/tuning?export_type=dpo&format=jsonl",
        headers={"Authorization": "Bearer dev-auditor"},
    )
    assert auth_resp.status_code == 200
    assert auth_resp.headers["content-type"].startswith("application/x-ndjson")
    assert (
        "attachment; filename=sentinelflow_dpo_dataset.jsonl"
        in auth_resp.headers["content-disposition"]
    )

    # 3. Auditor access (JSON format)
    json_resp = await test_client.get(
        "/api/v1/audit/export/tuning?export_type=sft&format=json",
        headers={"Authorization": "Bearer dev-auditor"},
    )
    assert json_resp.status_code == 200
    assert json_resp.headers["content-type"].startswith("application/json")
    data = json_resp.json()
    assert "total_samples" in data
    assert data["export_type"] == "sft"
    assert isinstance(data["samples"], list)
