from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Any
from uuid import uuid4

import pytest
from app.api.deps import get_db_session
from app.db.models import AuditArtifactRecord, AuditRecord, Base, DisputeRecord, InvestigationRecord
from app.main import app
from app.security import Principal, Role
from app.services.audit import (
    compute_row_hash,
    record_audit_event,
    verify_audit_integrity,
)
from cryptography.fernet import Fernet
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool


@pytest.fixture
async def real_db_engine():
    test_engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(test_engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection: Any, _connection_record: Any) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    try:
        yield test_engine
    finally:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await test_engine.dispose()


@pytest.fixture
async def real_db_session_factory(real_db_engine: Any) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(real_db_engine, expire_on_commit=False, class_=AsyncSession)


@pytest.fixture
async def real_db_session(
    real_db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with real_db_session_factory() as session:
        yield session


@pytest.fixture
async def integration_client(
    real_db_session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncClient]:
    async def override_get_db_session() -> AsyncIterator[AsyncSession]:
        async with real_db_session_factory() as session:
            yield session

    app.dependency_overrides[get_db_session] = override_get_db_session
    try:
        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://testserver",
        ) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Test 1: Real Database Schema & Foreign Key Constraints
# ---------------------------------------------------------------------------
async def test_schema_creation_and_foreign_key_enforcement(
    real_db_session: AsyncSession,
) -> None:
    # 1. Attempting to insert an investigation with an invalid dispute foreign key must fail
    invalid_investigation = InvestigationRecord(
        id=str(uuid4()),
        dispute_id="nonexistent_dispute_uuid",
        thread_id="thread_fk_test",
        status="pending",
        created_by="tester",
    )
    real_db_session.add(invalid_investigation)
    with pytest.raises(IntegrityError):
        await real_db_session.commit()
    await real_db_session.rollback()

    # 2. Insert valid dispute first
    dispute = DisputeRecord(
        id=str(uuid4()),
        case_code="FK-TEST-001",
        title="Valid Dispute for FK Test",
        narrative="Checking foreign key constraints with SQLite",
        customer_id="cust_fk",
        merchant_id="merch_fk",
        amount=120.50,
        currency="USD",
        status="open",
        attributes={"channel": "web"},
    )
    real_db_session.add(dispute)
    await real_db_session.commit()

    # 3. Investigation referencing valid dispute succeeds
    valid_investigation = InvestigationRecord(
        id=str(uuid4()),
        dispute_id=dispute.id,
        thread_id="thread_fk_test_success",
        status="pending",
        created_by="tester",
    )
    real_db_session.add(valid_investigation)
    await real_db_session.commit()

    # 4. Attempting to insert an audit artifact with invalid audit_record foreign key must fail
    invalid_artifact = AuditArtifactRecord(
        id=str(uuid4()),
        audit_record_id="nonexistent_audit_record_uuid",
        investigation_id=valid_investigation.id,
        dispute_id=dispute.id,
        key_id="v1",
        ciphertext="mock_ciphertext",
    )
    real_db_session.add(invalid_artifact)
    with pytest.raises(IntegrityError):
        await real_db_session.commit()
    await real_db_session.rollback()


# ---------------------------------------------------------------------------
# Test 2: Dispute REST API Lifecycle & Unique Constraint in Real DB
# ---------------------------------------------------------------------------
async def test_dispute_lifecycle_and_uniqueness_constraint_real_db(
    integration_client: AsyncClient,
    real_db_session: AsyncSession,
) -> None:
    # Create dispute via API
    create_payload = {
        "case_code": "DISP-INTEG-100",
        "title": "Unauthorized Online Subscription",
        "narrative": "Customer claims card was charged without consent for streaming service.",
        "customer_id": "cust_int_100",
        "merchant_id": "merch_stream_99",
        "amount": 29.99,
        "currency": "USD",
        "status": "open",
        "attributes": {"ip": "198.51.100.12", "tags": ["subscription", "recurring"]},
    }
    response = await integration_client.post(
        "/api/v1/disputes",
        headers={"Authorization": "Bearer dev-reviewer"},
        json=create_payload,
    )
    assert response.status_code == 200
    created_data = response.json()
    assert created_data["case_code"] == "DISP-INTEG-100"
    assert created_data["amount"] == 29.99
    dispute_id = created_data["id"]

    # Verify directly in SQLite tables
    persisted = await real_db_session.get(DisputeRecord, dispute_id)
    assert persisted is not None
    assert persisted.case_code == "DISP-INTEG-100"
    assert persisted.customer_id == "cust_int_100"
    assert persisted.attributes["tags"] == ["subscription", "recurring"]

    # Verify duplicate case_code triggers 409 DUPLICATE_CASE_CODE
    dup_response = await integration_client.post(
        "/api/v1/disputes",
        headers={"Authorization": "Bearer dev-reviewer"},
        json=create_payload,
    )
    assert dup_response.status_code == 409
    assert dup_response.json()["error"]["code"] == "DUPLICATE_CASE_CODE"

    # Verify listing disputes returns the new dispute
    list_response = await integration_client.get(
        "/api/v1/disputes",
        headers={"Authorization": "Bearer dev-investigator"},
    )
    assert list_response.status_code == 200
    items = list_response.json()
    assert any(item["id"] == dispute_id for item in items)


# ---------------------------------------------------------------------------
# Test 3: Investigation Start and Initial Audit Record in Real DB
# ---------------------------------------------------------------------------
async def test_investigation_creation_and_audit_event_logged_real_db(
    integration_client: AsyncClient,
    real_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Mock redis job scheduling to prevent redis requirement during db tests
    async def mock_schedule(*_args: Any, **_kwargs: Any) -> bool:
        return True

    monkeypatch.setattr("app.api.disputes.schedule_investigation", mock_schedule)

    # 1. Create dispute
    dispute = DisputeRecord(
        id=str(uuid4()),
        case_code="INV-AUDIT-001",
        title="Stolen Card Investigation",
        narrative="Multiple high-value charges in quick succession.",
        customer_id="cust_audit_1",
        merchant_id="merch_apple_1",
        amount=1499.00,
        currency="USD",
        status="open",
        attributes={},
    )
    real_db_session.add(dispute)
    await real_db_session.commit()

    # 2. Start investigation
    response = await integration_client.post(
        f"/api/v1/disputes/{dispute.id}/investigations",
        headers={"Authorization": "Bearer dev-investigator"},
    )
    assert response.status_code == 200
    run_data = response.json()
    investigation_id = run_data["id"]
    assert run_data["status"] == "running"

    # 3. Assert audit record was written to the database with sequence 1 and None prev_hash
    audit_rows = (
        (
            await real_db_session.execute(
                select(AuditRecord)
                .where(AuditRecord.investigation_id == investigation_id)
                .order_by(AuditRecord.sequence_no.asc())
            )
        )
        .scalars()
        .all()
    )

    assert len(audit_rows) == 1
    start_event = audit_rows[0]
    assert start_event.event_name == "investigation.started"
    assert start_event.sequence_no == 1
    assert start_event.prev_hash is None
    assert start_event.row_hash is not None

    # Verify SHA-256 integrity of the row
    expected_hash = compute_row_hash(
        investigation_id=investigation_id,
        dispute_id=dispute.id,
        sequence_no=1,
        prev_hash=None,
        actor_id=start_event.actor_id,
        actor_role=start_event.actor_role,
        event_name="investigation.started",
        payload=start_event.payload,
    )
    assert start_event.row_hash == expected_hash


# ---------------------------------------------------------------------------
# Test 4: Multi-Step Audit Chaining & Integrity Verification in Real DB
# ---------------------------------------------------------------------------
async def test_audit_chain_monotonicity_and_integrity_verification_real_db(
    integration_client: AsyncClient,
    real_db_session: AsyncSession,
) -> None:
    investigation_id = str(uuid4())
    dispute_id = str(uuid4())
    actor = Principal(user_id="agent-007", roles={Role.INVESTIGATOR})

    events_to_record: list[tuple[str, dict[str, Any]]] = [
        ("investigation.evidence_collected", {"evidence_id": "ev_1", "category": "device"}),
        (
            "investigation.hypothesis_updated",
            {"hypothesis": "Device fingerprint mismatch", "confidence": 0.85},
        ),
        ("investigation.risk_evaluated", {"score": 0.88, "level": "high"}),
        ("investigation.completed", {"recommendation": "deny", "approved": False}),
    ]

    for event_name, payload in events_to_record:
        await record_audit_event(
            real_db_session,
            actor=actor,
            event_name=event_name,
            payload=payload,
            investigation_id=investigation_id,
            dispute_id=dispute_id,
        )

    # Fetch rows from real SQLite
    rows = (
        (
            await real_db_session.execute(
                select(AuditRecord)
                .where(AuditRecord.investigation_id == investigation_id)
                .order_by(AuditRecord.sequence_no.asc())
            )
        )
        .scalars()
        .all()
    )

    assert len(rows) == 4
    # Check sequence monotonicity and cryptographic chaining
    for i, row in enumerate(rows):
        assert row.sequence_no == i + 1
        if i == 0:
            assert row.prev_hash is None
        else:
            assert row.prev_hash == rows[i - 1].row_hash

    # Verify via service function
    service_result = await verify_audit_integrity(real_db_session, investigation_id)
    assert service_result.valid is True
    assert service_result.checked_records == 4
    assert service_result.broken_sequence is None

    # Also verify via API endpoint as Auditor
    # Insert investigation record so get_investigation check succeeds
    inv_rec = InvestigationRecord(
        id=investigation_id,
        dispute_id=dispute_id,
        thread_id=f"thread_{investigation_id[:8]}",
        status="completed",
        created_by="agent-007",
    )
    # Also need dispute for FK
    disp_rec = DisputeRecord(
        id=dispute_id,
        case_code="CHAIN-DISP-1",
        title="Chain Test Dispute",
        narrative="Test chain",
        customer_id="c1",
        merchant_id="m1",
        amount=10.0,
    )
    real_db_session.add(disp_rec)
    real_db_session.add(inv_rec)
    await real_db_session.commit()

    api_response = await integration_client.get(
        f"/api/v1/investigations/{investigation_id}/audit/integrity",
        headers={"Authorization": "Bearer dev-auditor"},
    )
    assert api_response.status_code == 200
    integrity_data = api_response.json()
    assert integrity_data["valid"] is True
    assert integrity_data["checked_records"] == 4


# ---------------------------------------------------------------------------
# Test 5: Real Database Tamper Detection (Row Mutation & Sequence Gaps)
# ---------------------------------------------------------------------------
async def test_tamper_detection_on_mutated_payload_and_sequence_gap_real_db(
    real_db_session: AsyncSession,
) -> None:
    investigation_id = str(uuid4())
    dispute_id = str(uuid4())
    actor = Principal(user_id="agent-007", roles={Role.INVESTIGATOR})

    # Record 3 events
    for i in range(1, 4):
        await record_audit_event(
            real_db_session,
            actor=actor,
            event_name=f"event_{i}",
            payload={"step": i, "score": 10 * i},
            investigation_id=investigation_id,
            dispute_id=dispute_id,
        )

    # 1. Tamper: mutate payload in row 2 directly in SQLite without updating row_hash
    row_2 = (
        await real_db_session.execute(
            select(AuditRecord).where(
                AuditRecord.investigation_id == investigation_id,
                AuditRecord.sequence_no == 2,
            )
        )
    ).scalar_one()

    # Mutate payload
    tampered_payload = dict(row_2.payload)
    tampered_payload["score"] = 999999  # Tampered value!
    row_2.payload = tampered_payload
    await real_db_session.commit()

    # Verify detection
    tamper_result = await verify_audit_integrity(real_db_session, investigation_id)
    assert tamper_result.valid is False
    assert tamper_result.issue_code == "ROW_HASH_MISMATCH"
    assert tamper_result.broken_sequence == 2

    # 2. Tamper: delete row 2, creating a sequence gap between 1 and 3
    await real_db_session.delete(row_2)
    await real_db_session.commit()

    gap_result = await verify_audit_integrity(real_db_session, investigation_id)
    assert gap_result.valid is False
    assert gap_result.issue_code == "SEQUENCE_GAP"
    assert gap_result.broken_sequence == 2


# ---------------------------------------------------------------------------
# Test 6: Append-Only Auditor Correction Workflow
# ---------------------------------------------------------------------------
async def test_auditor_correction_append_only_real_db(
    integration_client: AsyncClient,
    real_db_session: AsyncSession,
) -> None:
    investigation_id = str(uuid4())
    dispute_id = str(uuid4())

    disp_rec = DisputeRecord(
        id=dispute_id,
        case_code="CORRECT-001",
        title="Correction Test Dispute",
        narrative="Test corrections",
        customer_id="c1",
        merchant_id="m1",
        amount=50.0,
    )
    inv_rec = InvestigationRecord(
        id=investigation_id,
        dispute_id=dispute_id,
        thread_id=f"thread_{investigation_id[:8]}",
        status="running",
        created_by="investigator-001",
    )
    real_db_session.add(disp_rec)
    real_db_session.add(inv_rec)
    await real_db_session.commit()

    # Record 2 initial events
    actor = Principal(user_id="investigator-001", roles={Role.INVESTIGATOR})
    await record_audit_event(
        real_db_session,
        actor=actor,
        event_name="investigation.started",
        payload={"notes": "initial run"},
        investigation_id=investigation_id,
        dispute_id=dispute_id,
    )
    evt2 = await record_audit_event(
        real_db_session,
        actor=actor,
        event_name="investigation.risk_evaluated",
        payload={"score": 0.35, "level": "low"},
        investigation_id=investigation_id,
        dispute_id=dispute_id,
    )
    initial_evt2_hash = evt2.row_hash
    initial_evt2_payload = dict(evt2.payload)

    # Post correction as Auditor via API
    correction_payload = {
        "supersedes_event_id": evt2.id,
        "reason_code": "DATA_REASSESSMENT",
        "note": "Device logs indicated proxy use; risk reassessed to high.",
    }
    response = await integration_client.post(
        f"/api/v1/investigations/{investigation_id}/audit/corrections",
        headers={"Authorization": "Bearer dev-auditor"},
        json=correction_payload,
    )
    assert response.status_code == 200
    correction_data = response.json()
    assert correction_data["event_name"] == "investigation.audit_correction"

    # Verify in SQLite:
    # 1. evt2 was NOT mutated (true immutability)
    persisted_evt2 = await real_db_session.get(AuditRecord, evt2.id)
    assert persisted_evt2 is not None
    assert persisted_evt2.row_hash == initial_evt2_hash
    assert persisted_evt2.payload == initial_evt2_payload

    # 2. A new record with sequence_no 3 was appended
    persisted_correction = (
        await real_db_session.execute(
            select(AuditRecord).where(
                AuditRecord.investigation_id == investigation_id,
                AuditRecord.sequence_no == 3,
            )
        )
    ).scalar_one()
    assert persisted_correction.event_name == "investigation.audit_correction"
    assert persisted_correction.prev_hash == initial_evt2_hash
    assert persisted_correction.payload["supersedes_event_id"] == evt2.id
    assert persisted_correction.payload["reason_code"] == "DATA_REASSESSMENT"

    # 3. Overall chain integrity remains 100% valid
    integrity = await verify_audit_integrity(real_db_session, investigation_id)
    assert integrity.valid is True
    assert integrity.checked_records == 3


# ---------------------------------------------------------------------------
# Test 7: Concurrent Audit Writes Safety (No Sequence or Hash Clashes)
# ---------------------------------------------------------------------------
async def test_concurrent_audit_writes_sequence_consistency(
    real_db_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    investigation_id = str(uuid4())
    dispute_id = str(uuid4())
    actor = Principal(user_id="concurrent-agent", roles={Role.INVESTIGATOR})

    # Execute 8 concurrent audit write operations
    async def write_event(idx: int) -> AuditRecord:
        async with real_db_session_factory() as session:
            return await record_audit_event(
                session,
                actor=actor,
                event_name="investigation.parallel_step",
                payload={"worker_id": idx, "timestamp_ms": idx * 100},
                investigation_id=investigation_id,
                dispute_id=dispute_id,
            )

    results = await asyncio.gather(*(write_event(i) for i in range(8)))
    assert len(results) == 8

    # Query all records
    async with real_db_session_factory() as verify_session:
        rows = (
            (
                await verify_session.execute(
                    select(AuditRecord)
                    .where(AuditRecord.investigation_id == investigation_id)
                    .order_by(AuditRecord.sequence_no.asc())
                )
            )
            .scalars()
            .all()
        )

        assert len(rows) == 8
        sequences = [row.sequence_no for row in rows]
        assert sequences == [1, 2, 3, 4, 5, 6, 7, 8]

        # Verify cryptographic chain integrity
        integrity = await verify_audit_integrity(verify_session, investigation_id)
        assert integrity.valid is True
        assert integrity.checked_records == 8


# ---------------------------------------------------------------------------
# Test 8: Encrypted Audit Artifacts in Real DB
# ---------------------------------------------------------------------------
async def test_encrypted_audit_artifacts_real_db(
    integration_client: AsyncClient,
    real_db_session: AsyncSession,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    encryption_key = Fernet.generate_key().decode("utf-8")
    monkeypatch.setenv("AUDIT_ARTIFACT_ENCRYPTION_KEY", encryption_key)

    # Reload settings mock
    from app.config import get_settings

    get_settings.cache_clear()

    investigation_id = str(uuid4())
    dispute_id = str(uuid4())

    # Add dispute & investigation records for foreign key & route lookup
    disp_rec = DisputeRecord(
        id=dispute_id,
        case_code="CIPHER-001",
        title="Encryption Test Dispute",
        narrative="Test encryption",
        customer_id="c1",
        merchant_id="m1",
        amount=100.0,
    )
    inv_rec = InvestigationRecord(
        id=investigation_id,
        dispute_id=dispute_id,
        thread_id=f"thread_{investigation_id[:8]}",
        status="running",
        created_by="agent-007",
    )
    real_db_session.add(disp_rec)
    real_db_session.add(inv_rec)
    await real_db_session.commit()

    actor = Principal(user_id="agent-007", roles={Role.AUDITOR})

    # Record audit event containing raw LLM prompt and output
    record = await record_audit_event(
        real_db_session,
        actor=actor,
        event_name="investigation.llm_reasoning",
        payload={
            "model": "gpt-4.1-mini",
            "raw_artifact": {
                "prompt": (
                    "Evaluate cardholder 4111-XXXX-XXXX-1111 dispute for customer john@example.com"
                ),
                "output": "High likelihood of friendly fraud based on previous matching orders.",
                "reasoning": "Device IP matches cardholder home address.",
            },
        },
        investigation_id=investigation_id,
        dispute_id=dispute_id,
    )

    artifact_id = record.payload.get("raw_artifact_id")
    assert artifact_id is not None
    assert record.payload.get("raw_artifact_encrypted") is True

    # 1. Inspect real SQLite table: plaintext must NOT exist in ciphertext column
    artifact_row = await real_db_session.get(AuditArtifactRecord, artifact_id)
    assert artifact_row is not None
    assert "4111-XXXX-XXXX-1111" not in artifact_row.ciphertext
    assert "john@example.com" not in artifact_row.ciphertext

    # 2. Retrieve via API endpoint as Auditor
    response = await integration_client.get(
        f"/api/v1/investigations/{investigation_id}/audit/artifacts/{artifact_id}",
        headers={"Authorization": "Bearer dev-auditor"},
    )
    assert response.status_code == 200
    retrieved_data = response.json()
    assert retrieved_data["artifact_id"] == artifact_id
    assert "4111-XXXX-XXXX-1111" in retrieved_data["payload"]["prompt"]
    assert "friendly fraud" in retrieved_data["payload"]["output"]

    # 3. Verify access was automatically audited in the ledger
    audit_rows = (
        (
            await real_db_session.execute(
                select(AuditRecord).where(
                    AuditRecord.investigation_id == investigation_id,
                    AuditRecord.event_name == "investigation.audit_artifact_read",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(audit_rows) == 1
    assert audit_rows[0].payload["artifact_id"] == artifact_id

    # Clean up settings cache
    get_settings.cache_clear()


# ---------------------------------------------------------------------------
# Test 9: Showcase Seeding & Cryptographic Audit Chain Integrity
# ---------------------------------------------------------------------------
async def test_seed_session_creates_showcase_investigations_and_verified_audit_chains(
    real_db_session: AsyncSession,
) -> None:
    from app.db.seed import seed_session

    await seed_session(real_db_session)
    # Idempotency check: calling seed_session a second time must not duplicate records
    await seed_session(real_db_session)

    inv1 = await real_db_session.get(InvestigationRecord, "inv_seed_sf_10001")
    assert inv1 is not None
    assert inv1.status == "completed"
    assert inv1.iteration_count == 2
    assert len(inv1.evidence) == 4
    assert any(ev.get("type") == "run_completed" for ev in inv1.timeline_events)

    inv2 = await real_db_session.get(InvestigationRecord, "inv_seed_sf_10002")
    assert inv2 is not None
    assert inv2.status == "awaiting_approval"
    assert inv2.timeline_events[-1]["type"] == "approval_required"

    integrity1 = await verify_audit_integrity(real_db_session, "inv_seed_sf_10001")
    assert integrity1.valid is True
    assert integrity1.checked_records == 5

    integrity2 = await verify_audit_integrity(real_db_session, "inv_seed_sf_10002")
    assert integrity2.valid is True
    assert integrity2.checked_records == 3
