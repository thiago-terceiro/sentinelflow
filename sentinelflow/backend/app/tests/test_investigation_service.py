from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

from app.db.models import InvestigationRecord
from app.schemas.investigation import (
    ComplianceFinding,
    Evidence,
    InvestigationHypothesis,
    InvestigationReport,
    RiskAssessment,
    RiskFactor,
)
from app.services.investigations import (
    PrincipalContext,
    initial_state,
    persist_graph_state,
    replay_events,
    run_investigation_job,
    run_resume_investigation_job,
    schedule_investigation,
    schedule_resume,
    stream_graph_events,
    to_run,
)
from sqlalchemy.ext.asyncio import AsyncSession


def test_initial_state_contains_required_defaults() -> None:
    record = cast(
        InvestigationRecord,
        SimpleNamespace(
            id="inv_123",
            dispute_id="disp_123",
            thread_id="thread_123",
        ),
    )

    state = initial_state(
        record,
        PrincipalContext(user_id="user_123", roles=["investigator"]),
    )

    assert state["status"] == "running"
    assert state["failed_tools"] == []
    assert state["failed_analyzers"] == []
    assert len(state["timeline_events"]) == 1
    assert state["timeline_events"][0]["type"] == "run_started"


def test_replay_events_includes_failed_terminal_event() -> None:
    record = cast(
        InvestigationRecord,
        SimpleNamespace(
            id="inv_123",
            thread_id="thread_123",
            status="failed",
            report=None,
            risk_assessment=None,
            evidence=[],
        ),
    )

    events = list(replay_events(record))

    assert [event["type"] for event in events] == ["run_started", "run_failed"]


def test_to_run_maps_budget_and_record_fields() -> None:
    record = cast(
        InvestigationRecord,
        SimpleNamespace(
            id="inv_123",
            dispute_id="disp_123",
            thread_id="thread_123",
            status="running",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            risk_assessment=None,
            compliance_findings=[],
            report=None,
        ),
    )

    run = to_run(record)

    assert run.id == record.id
    assert run.status == "running"
    assert run.budget.max_iterations > 0


class _FakeSnapshot:
    def __init__(self, values: dict[str, Any], *, has_pending_next: bool) -> None:
        self.values = values
        self.next = ("approval",) if has_pending_next else ()
        self.config = {"configurable": {"checkpoint_id": "chk_999"}}


class _FakeGraph:
    def __init__(self, snapshot: _FakeSnapshot) -> None:
        self._snapshot = snapshot

    async def aget_state(self, _config: dict[str, dict[str, str]]) -> _FakeSnapshot:
        return self._snapshot


class _FakeSession:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed = False

    async def commit(self) -> None:
        self.committed = True

    async def refresh(self, _record: InvestigationRecord) -> None:
        self.refreshed = True


async def test_persist_graph_state_sets_awaiting_approval_when_snapshot_has_next() -> None:
    now = datetime.now(UTC)
    record = cast(
        InvestigationRecord,
        SimpleNamespace(
            id="inv_123",
            dispute_id="disp_123",
            thread_id="thread_123",
            status="running",
            created_at=now,
            updated_at=now,
            evidence=[],
            analyzer_summaries=[],
            hypotheses=[],
            unresolved_questions=[],
            risk_assessment=None,
            compliance_findings=[],
            report=None,
            iteration_count=0,
            tool_call_count=0,
            analyzer_call_count=0,
            timeline_events=[],
            checkpoint_id=None,
        ),
    )
    values: dict[str, Any] = {
        "status": "completed",
        "evidence": [
            Evidence(
                id="ev_1",
                source="transaction",
                category="transaction",
                summary="ok",
                facts={},
                confidence=0.8,
                collected_at=now,
                provenance="test",
            )
        ],
        "analyzer_summaries": [],
        "hypotheses": [
            InvestigationHypothesis(
                statement="test",
                confidence=0.7,
                supporting_evidence_ids=["ev_1"],
                contradicting_evidence_ids=[],
            )
        ],
        "unresolved_questions": [],
        "risk_assessment": RiskAssessment(
            score=0.81,
            level="high",
            factors=[
                RiskFactor(
                    name="velocity",
                    score=0.81,
                    weight=1.0,
                    explanation="test",
                    evidence_ids=["ev_1"],
                )
            ],
            threshold_triggered=True,
            explanation="test",
        ),
        "compliance_findings": [
            ComplianceFinding(
                framework="PCI",
                rule_id="PCI-1",
                passed=False,
                requires_review=True,
                explanation="test",
                evidence_ids=["ev_1"],
                policy_version="v1",
            )
        ],
        "investigation_report": InvestigationReport(
            conclusion="test",
            recommendation="escalate",
            confidence=0.8,
            hypotheses=[],
            risk_factors=[],
            evidence_ids=["ev_1"],
            unresolved_questions=[],
            compliance_findings=["PCI-1"],
        ),
        "iteration_count": 1,
        "tool_call_count": 1,
        "analyzer_call_count": 0,
        "timeline_events": [
            {
                "id": "evt_1",
                "type": "approval_required",
                "timestamp": now.isoformat(),
                "data": {"investigation_id": "inv_123"},
            }
        ],
    }
    graph = _FakeGraph(_FakeSnapshot(values, has_pending_next=True))
    fake_session = _FakeSession()

    updated = await persist_graph_state(
        cast(AsyncSession, fake_session),
        record,
        cast(Any, graph),
        {"configurable": {"thread_id": "thread_123"}},
    )

    assert updated.status == "awaiting_approval"
    assert updated.checkpoint_id == "chk_999"
    assert fake_session.committed is True
    assert fake_session.refreshed is True


async def test_schedule_investigation_uses_active_job_id_and_payload(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_enqueue_job(
        job_name: str,
        *,
        job_id: str,
        payload: dict[str, Any],
    ) -> bool:
        captured["job_name"] = job_name
        captured["job_id"] = job_id
        captured["payload"] = payload
        return True

    monkeypatch.setattr("app.services.investigations._enqueue_job", _fake_enqueue_job)

    scheduled = await schedule_investigation(
        "inv_123",
        PrincipalContext(user_id="user_123", roles=["investigator"]),
    )

    assert scheduled is True
    assert captured["job_name"] == "run_investigation_job"
    assert captured["job_id"] == "investigation:inv_123:active"
    assert captured["payload"] == {
        "investigation_id": "inv_123",
        "principal_id": "user_123",
        "principal_roles": ["investigator"],
    }


async def test_schedule_resume_uses_same_active_job_id_as_run(
    monkeypatch: Any,
) -> None:
    captured: list[dict[str, Any]] = []

    async def _fake_enqueue_job(
        job_name: str,
        *,
        job_id: str,
        payload: dict[str, Any],
    ) -> bool:
        captured.append(
            {
                "job_name": job_name,
                "job_id": job_id,
                "payload": payload,
            }
        )
        return True

    monkeypatch.setattr("app.services.investigations._enqueue_job", _fake_enqueue_job)

    run_scheduled = await schedule_investigation(
        "inv_123",
        PrincipalContext(user_id="user_123", roles=["investigator"]),
    )
    resume_scheduled = await schedule_resume(
        "inv_123",
        {"decision": "approve", "comment": "ok"},
    )

    assert run_scheduled is True
    assert resume_scheduled is True
    assert len(captured) == 2
    assert captured[0]["job_name"] == "run_investigation_job"
    assert captured[1]["job_name"] == "run_resume_investigation_job"
    assert captured[0]["job_id"] == "investigation:inv_123:active"
    assert captured[1]["job_id"] == "investigation:inv_123:active"


# ---------------------------------------------------------------------------
# PROD-022 – worker wrapper contract tests
# ---------------------------------------------------------------------------


async def test_run_investigation_job_parses_payload_and_delegates(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run(investigation_id: str, principal: PrincipalContext) -> None:
        captured["investigation_id"] = investigation_id
        captured["principal"] = principal

    monkeypatch.setattr("app.services.investigations._run_new_investigation", _fake_run)

    await run_investigation_job(
        {},
        {
            "investigation_id": "inv_abc",
            "principal_id": "user_1",
            "principal_roles": ["investigator", "senior_investigator"],
        },
    )

    assert captured["investigation_id"] == "inv_abc"
    assert captured["principal"].user_id == "user_1"
    assert captured["principal"].roles == ["investigator", "senior_investigator"]


async def test_run_investigation_job_defaults_roles_to_empty(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_run(investigation_id: str, principal: PrincipalContext) -> None:
        captured["principal"] = principal

    monkeypatch.setattr("app.services.investigations._run_new_investigation", _fake_run)

    await run_investigation_job({}, {"investigation_id": "inv_xyz", "principal_id": "user_2"})

    assert captured["principal"].roles == []


async def test_run_resume_investigation_job_parses_payload_and_delegates(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_resume(investigation_id: str, decision: dict[str, Any]) -> None:
        captured["investigation_id"] = investigation_id
        captured["decision"] = decision

    monkeypatch.setattr("app.services.investigations._run_resume_investigation", _fake_resume)

    await run_resume_investigation_job(
        {},
        {
            "investigation_id": "inv_resume",
            "decision": {"decision": "approve", "comment": "ok"},
        },
    )

    assert captured["investigation_id"] == "inv_resume"
    assert captured["decision"] == {"decision": "approve", "comment": "ok"}


async def test_run_resume_investigation_job_defaults_decision_to_empty(
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    async def _fake_resume(investigation_id: str, decision: dict[str, Any]) -> None:
        captured["decision"] = decision

    monkeypatch.setattr("app.services.investigations._run_resume_investigation", _fake_resume)

    await run_resume_investigation_job({}, {"investigation_id": "inv_no_decision"})

    assert captured["decision"] == {}


async def test_enqueue_job_uses_shared_pool(monkeypatch: Any) -> None:
    from app.services.investigations import _enqueue_job, close_redis_pool

    await close_redis_pool()

    created_pools: list[Any] = []

    class _FakeJob:
        pass

    class _FakePool:
        async def enqueue_job(self, name: str, payload: object, *, _job_id: str) -> _FakeJob:
            return _FakeJob()

        async def aclose(self) -> None:
            pass

    async def _fake_create_pool(_settings: object) -> _FakePool:
        pool = _FakePool()
        created_pools.append(pool)
        return pool

    monkeypatch.setattr("app.services.investigations.create_pool", _fake_create_pool)

    result1 = await _enqueue_job("some_job", job_id="jid_1", payload={"k": "v"})
    result2 = await _enqueue_job("some_job", job_id="jid_2", payload={"k": "v"})

    assert result1 is True
    assert result2 is True
    assert len(created_pools) == 1
    await close_redis_pool()


async def test_close_redis_pool_closes_active_pool(monkeypatch: Any) -> None:
    from app.services.investigations import _enqueue_job, close_redis_pool

    await close_redis_pool()

    pool_closed = {"value": False}

    class _FakeJob:
        pass

    class _FakePool:
        async def enqueue_job(self, name: str, payload: object, *, _job_id: str) -> _FakeJob:
            return _FakeJob()

        async def aclose(self) -> None:
            pool_closed["value"] = True

    async def _fake_create_pool(_settings: object) -> _FakePool:
        return _FakePool()

    monkeypatch.setattr("app.services.investigations.create_pool", _fake_create_pool)

    await _enqueue_job("some_job", job_id="jid_1", payload={})
    assert pool_closed["value"] is False

    await close_redis_pool()
    assert pool_closed["value"] is True


# ---------------------------------------------------------------------------
# PROD-021 – stream observer branch tests
# ---------------------------------------------------------------------------


def _stream_record(
    *,
    status: str,
    timeline_events: list[dict[str, Any]] | None = None,
    failure_reason: str | None = None,
    investigation_id: str = "inv_stream",
    thread_id: str = "thread_stream",
) -> InvestigationRecord:
    return cast(
        InvestigationRecord,
        SimpleNamespace(
            id=investigation_id,
            thread_id=thread_id,
            status=status,
            report=None,
            risk_assessment=None,
            evidence=[],
            timeline_events=timeline_events or [],
            failure_reason=failure_reason,
        ),
    )


class _FakeStreamGraph:
    def __init__(self, timeline_events: list[dict[str, Any]]) -> None:
        self._events = timeline_events

    async def aget_state(self, _config: object) -> SimpleNamespace:
        return SimpleNamespace(
            values={"timeline_events": self._events},
            next=(),
            config={"configurable": {"checkpoint_id": "chk_1"}},
        )


class _FakeStreamSession:
    def __init__(self, record: InvestigationRecord | None) -> None:
        self._record = record

    async def get(self, _model: object, _id: str) -> InvestigationRecord | None:
        return self._record

    async def __aenter__(self) -> _FakeStreamSession:
        return self

    async def __aexit__(self, *_: object) -> None:
        pass


async def _collect_stream(
    monkeypatch: Any,
    record: InvestigationRecord | None,
    snapshot_events: list[dict[str, Any]],
    *,
    investigation_id: str = "inv_stream",
) -> list[dict[str, Any]]:
    import json as _json
    from contextlib import asynccontextmanager

    @asynccontextmanager
    async def _fake_session_local() -> Any:  # type: ignore[misc]
        yield _FakeStreamSession(record)

    monkeypatch.setattr("app.services.investigations.SessionLocal", _fake_session_local)

    graph = _FakeStreamGraph(snapshot_events)

    def _fake_build_graph(_session: object) -> _FakeStreamGraph:
        return graph

    monkeypatch.setattr("app.services.investigations.build_graph", _fake_build_graph)

    events: list[dict[str, Any]] = []
    async for chunk in stream_graph_events(investigation_id):
        raw = chunk.removeprefix("data: ").strip()
        if raw:
            events.append(_json.loads(raw))
    return events


async def test_stream_emits_run_failed_immediately_for_missing_investigation(
    monkeypatch: Any,
) -> None:
    events = await _collect_stream(monkeypatch, None, [], investigation_id="inv_missing")

    assert len(events) == 1
    assert events[0]["type"] == "run_failed"
    assert events[0]["data"]["investigation_id"] == "inv_missing"


async def test_stream_replays_saved_timeline_for_completed_investigation(
    monkeypatch: Any,
) -> None:
    saved = [
        {"id": "e1", "type": "run_started", "timestamp": "2026-01-01T00:00:00Z", "data": {}},
        {"id": "e2", "type": "run_completed", "timestamp": "2026-01-01T00:01:00Z", "data": {}},
    ]
    record = _stream_record(status="completed", timeline_events=saved)
    # snapshot has no events — record carries the canonical timeline
    events = await _collect_stream(monkeypatch, record, [])

    types = [e["type"] for e in events]
    assert types == ["run_started", "run_completed"]


async def test_stream_emits_run_failed_for_failed_investigation_with_no_snapshot_events(
    monkeypatch: Any,
) -> None:
    record = _stream_record(status="failed", failure_reason="graph error")
    events = await _collect_stream(monkeypatch, record, [])

    types = [e["type"] for e in events]
    assert "run_failed" in types


async def test_stream_does_not_duplicate_run_failed_when_already_in_timeline(
    monkeypatch: Any,
) -> None:
    failure_event = {
        "id": "run_failed_inv_stream",
        "type": "run_failed",
        "timestamp": "2026-01-01T00:00:00Z",
        "data": {"investigation_id": "inv_stream"},
    }
    snapshot_events = [failure_event]
    record = _stream_record(status="failed", timeline_events=snapshot_events)
    events = await _collect_stream(monkeypatch, record, snapshot_events)

    run_failed_events = [e for e in events if e["type"] == "run_failed"]
    assert len(run_failed_events) == 1


async def test_stream_emits_snapshot_events_before_checking_terminal_status(
    monkeypatch: Any,
) -> None:
    snapshot_events = [
        {"id": "e1", "type": "evidence_added", "timestamp": "2026-01-01T00:00:00Z", "data": {}},
        {"id": "e2", "type": "run_completed", "timestamp": "2026-01-01T00:01:00Z", "data": {}},
    ]
    record = _stream_record(status="completed", timeline_events=snapshot_events)
    events = await _collect_stream(monkeypatch, record, snapshot_events)

    types = [e["type"] for e in events]
    assert "evidence_added" in types
    assert "run_completed" in types


# ---------------------------------------------------------------------------
# PROD-030 – event broadcaster tests
# ---------------------------------------------------------------------------


async def test_investigation_broadcaster_publishes_to_all_subscribers() -> None:
    from app.services.investigations import InvestigationBroadcaster

    broadcaster = InvestigationBroadcaster()
    q1 = await broadcaster.subscribe("inv_test_pub")
    q2 = await broadcaster.subscribe("inv_test_pub")

    event = {"id": "ev_1", "type": "evidence_added", "data": {"key": "value"}}
    await broadcaster.publish("inv_test_pub", event)

    received_1 = await q1.get()
    received_2 = await q2.get()

    assert received_1 == event
    assert received_2 == event

    await broadcaster.publish_terminal("inv_test_pub")
    assert await q1.get() is None
    assert await q2.get() is None

    await broadcaster.unsubscribe("inv_test_pub", q1)
    await broadcaster.unsubscribe("inv_test_pub", q2)
    assert "inv_test_pub" not in broadcaster._subscribers


async def test_investigation_broadcaster_unsubscribes_cleanly() -> None:
    from app.services.investigations import InvestigationBroadcaster

    broadcaster = InvestigationBroadcaster()
    q = await broadcaster.subscribe("inv_unsub")
    assert "inv_unsub" in broadcaster._subscribers

    await broadcaster.unsubscribe("inv_unsub", q)
    assert "inv_unsub" not in broadcaster._subscribers


async def test_stream_graph_events_receives_live_broadcaster_events(monkeypatch: Any) -> None:
    import json as _json
    from contextlib import asynccontextmanager

    from app.services.investigations import investigation_broadcaster

    inv_id = "inv_live_test"
    record = _stream_record(status="running", timeline_events=[], investigation_id=inv_id)

    @asynccontextmanager
    async def _fake_session() -> Any:
        yield _FakeStreamSession(record)

    monkeypatch.setattr("app.services.investigations.SessionLocal", _fake_session)
    monkeypatch.setattr("app.services.investigations.build_graph", lambda _s: _FakeStreamGraph([]))

    collected: list[dict[str, Any]] = []

    async def consume_stream() -> None:
        async for chunk in stream_graph_events(inv_id):
            raw = chunk.removeprefix("data: ").strip()
            if raw:
                collected.append(_json.loads(raw))

    consumer_task = asyncio.create_task(consume_stream())

    # Allow consumer to subscribe and complete initial DB read
    await asyncio.sleep(0.05)

    # Publish live event
    live_event = {
        "id": "live_ev_1",
        "type": "evidence_added",
        "timestamp": "2026-01-01T00:00:00Z",
        "data": {"source": "live_test"},
    }
    await investigation_broadcaster.publish(inv_id, live_event)

    # Publish terminal event
    terminal_event = {
        "id": "live_ev_2",
        "type": "run_completed",
        "timestamp": "2026-01-01T00:01:00Z",
        "data": {},
    }
    await investigation_broadcaster.publish(inv_id, terminal_event)

    await asyncio.wait_for(consumer_task, timeout=2.0)

    types = [e["type"] for e in collected]
    assert "evidence_added" in types
    assert "run_completed" in types


async def test_cross_process_redis_pubsub_bridge_delivers_events_to_stream(
    monkeypatch: Any,
) -> None:
    import json as _json
    from contextlib import asynccontextmanager

    from app.services.investigations import InvestigationBroadcaster

    inv_id = "inv_redis_bridge"
    record = _stream_record(status="running", timeline_events=[], investigation_id=inv_id)

    @asynccontextmanager
    async def _fake_session() -> Any:
        yield _FakeStreamSession(record)

    class _FakePubSub:
        def __init__(self, channel_queues: dict[str, list[asyncio.Queue[str]]]) -> None:
            self._channel_queues = channel_queues
            self._queue: asyncio.Queue[str] = asyncio.Queue()
            self._subscribed_channel: str | None = None

        async def __aenter__(self) -> _FakePubSub:
            return self

        async def __aexit__(self, *_: object) -> None:
            if self._subscribed_channel and self._subscribed_channel in self._channel_queues:
                self._channel_queues[self._subscribed_channel].remove(self._queue)

        async def subscribe(self, channel: str) -> None:
            self._subscribed_channel = channel
            self._channel_queues.setdefault(channel, []).append(self._queue)

        async def listen(self) -> Any:
            while True:
                data = await self._queue.get()
                yield {"type": "message", "data": data.encode("utf-8")}

    class _FakeRedisBroker:
        def __init__(self) -> None:
            self.channels: dict[str, list[asyncio.Queue[str]]] = {}

        async def publish(self, channel: str, payload: str) -> None:
            for q in list(self.channels.get(channel, [])):
                q.put_nowait(payload)

        def pubsub(self) -> _FakePubSub:
            return _FakePubSub(self.channels)

    fake_redis = _FakeRedisBroker()
    monkeypatch.setattr("app.services.investigations.SessionLocal", _fake_session)
    monkeypatch.setattr("app.services.investigations.build_graph", lambda _s: _FakeStreamGraph([]))
    monkeypatch.setattr("app.services.investigations._shared_redis_pool", fake_redis)

    collected: list[dict[str, Any]] = []

    async def consume_stream() -> None:
        async for chunk in stream_graph_events(inv_id):
            raw = chunk.removeprefix("data: ").strip()
            if raw:
                collected.append(_json.loads(raw))

    consumer_task = asyncio.create_task(consume_stream())
    await asyncio.sleep(0.05)

    # Simulate an isolated worker process with its own separate InvestigationBroadcaster instance
    worker_broadcaster = InvestigationBroadcaster()
    await worker_broadcaster.publish(
        inv_id,
        {
            "id": "redis_ev_1",
            "type": "hypothesis_updated",
            "timestamp": "2026-01-01T00:00:00Z",
            "data": {"iteration": 1},
        },
    )
    await worker_broadcaster.publish_terminal(inv_id)

    await asyncio.wait_for(consumer_task, timeout=2.0)

    assert len(collected) == 1
    assert collected[0]["id"] == "redis_ev_1"
    assert len(collected) == 1
    assert collected[0]["id"] == "redis_ev_1"
    assert collected[0]["type"] == "hypothesis_updated"


def test_to_run_hydrates_timeline_evidence_analyzers_and_hypotheses() -> None:
    now = datetime.now(UTC)
    record = cast(
        InvestigationRecord,
        SimpleNamespace(
            id="inv_hydrated",
            dispute_id="disp_hydrated",
            thread_id="thread_hydrated",
            status="completed",
            created_at=now,
            updated_at=now,
            risk_assessment=None,
            compliance_findings=[],
            report=None,
            evidence=[
                {
                    "id": "ev_tx_1",
                    "source": "transactions",
                    "category": "transaction",
                    "origin": "observed_fact",
                    "summary": "Tx history",
                    "facts": {"amount": 420.0},
                    "confidence": 0.98,
                    "collected_at": now.isoformat(),
                    "provenance": "postgres",
                }
            ],
            analyzer_summaries=[
                {
                    "analyzer": "fraud_pattern",
                    "origin": "analyzer_interpretation",
                    "summary": "Pattern summary",
                    "findings": ["High velocity"],
                    "confidence": 0.85,
                    "evidence_ids": ["ev_tx_1"],
                    "contradictions": [],
                    "recommended_followups": [],
                }
            ],
            hypotheses=[
                {
                    "statement": "Account takeover suspected.",
                    "confidence": 0.78,
                    "supporting_evidence_ids": ["ev_tx_1"],
                    "contradicting_evidence_ids": [],
                }
            ],
            timeline_events=[
                {
                    "id": "evt_1",
                    "type": "run_started",
                    "timestamp": now.isoformat(),
                    "data": {"investigation_id": "inv_hydrated"},
                }
            ],
        ),
    )

    run = to_run(record)

    assert len(run.evidence) == 1
    assert run.evidence[0].id == "ev_tx_1"
    assert len(run.analyzer_summaries) == 1
    assert run.analyzer_summaries[0].analyzer == "fraud_pattern"
    assert len(run.hypotheses) == 1
    assert run.hypotheses[0].statement == "Account takeover suspected."
    assert len(run.timeline_events) == 1
    assert run.timeline_events[0]["id"] == "evt_1"


async def test_enqueue_job_injects_w3c_trace_carrier(monkeypatch: Any) -> None:
    from app.services.investigations import _enqueue_job

    captured_kwargs: dict[str, Any] = {}

    class _FakeRedisPool:
        async def enqueue_job(self, job_name: str, *args: Any, **kwargs: Any) -> object:
            captured_kwargs["job_name"] = job_name
            captured_kwargs["args"] = args
            captured_kwargs["kwargs"] = kwargs
            return SimpleNamespace(job_id="job_1")

    async def _fake_get_redis_pool() -> _FakeRedisPool:
        return _FakeRedisPool()

    monkeypatch.setattr("app.services.investigations.get_redis_pool", _fake_get_redis_pool)
    monkeypatch.setattr(
        "opentelemetry.propagate.inject",
        lambda carrier: carrier.__setitem__(
            "traceparent",
            "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01",
        ),
    )

    enqueued = await _enqueue_job(
        "run_investigation_job",
        job_id="investigation:inv_trace_1:active",
        payload={"investigation_id": "inv_trace_1", "principal_id": "actor_1"},
    )

    assert enqueued is True
    assert captured_kwargs["job_name"] == "run_investigation_job"
    enriched_payload = captured_kwargs["args"][0]
    assert "_trace_carrier" in enriched_payload
    assert (
        enriched_payload["_trace_carrier"]["traceparent"]
        == "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    )


async def test_persist_graph_state_appends_approval_required_on_interrupt() -> None:
    record = cast(
        InvestigationRecord,
        SimpleNamespace(
            id="inv_interrupt_1",
            dispute_id="disp_interrupt_1",
            thread_id="thread_interrupt_1",
            status="running",
            evidence=[],
            analyzer_summaries=[],
            hypotheses=[],
            unresolved_questions=[],
            risk_assessment=None,
            compliance_findings=[],
            report=None,
            iteration_count=0,
            tool_call_count=0,
            analyzer_call_count=0,
            timeline_events=[],
            checkpoint_id=None,
        ),
    )

    class _FakeGraph:
        async def aget_state(self, _config: dict[str, Any]) -> object:
            return SimpleNamespace(
                next=("approval",),
                config={"configurable": {"checkpoint_id": "chk_interrupt_1"}},
                values={
                    "status": "running",
                    "evidence": [],
                    "analyzer_summaries": [],
                    "hypotheses": [],
                    "unresolved_questions": [],
                    "risk_assessment": None,
                    "compliance_findings": [],
                    "investigation_report": InvestigationReport(
                        conclusion="Awaiting human decision",
                        recommendation="escalate",
                        confidence=0.81,
                        hypotheses=[],
                        risk_factors=[],
                        evidence_ids=[],
                        unresolved_questions=[],
                        compliance_findings=[],
                    ),
                    "iteration_count": 1,
                    "tool_call_count": 2,
                    "analyzer_call_count": 1,
                    "timeline_events": [
                        {
                            "id": "run_started_inv_interrupt_1",
                            "type": "run_started",
                            "timestamp": "2026-09-03T00:00:00Z",
                            "data": {"investigation_id": "inv_interrupt_1"},
                        }
                    ],
                },
            )

    class _FakeSession:
        async def commit(self) -> None:
            return None

        async def refresh(self, _obj: object) -> None:
            return None

    updated = await persist_graph_state(
        cast(AsyncSession, _FakeSession()),
        record,
        _FakeGraph(),
        {"configurable": {"thread_id": "thread_interrupt_1"}},
    )

    assert updated.status == "awaiting_approval"
    assert len(updated.timeline_events) == 2
    assert updated.timeline_events[-1]["type"] == "approval_required"
    assert updated.timeline_events[-1]["id"] == "approval_inv_interrupt_1"


async def test_publish_terminal_evicts_oldest_item_when_subscriber_queue_is_full(
    monkeypatch: Any,
) -> None:
    from app.services.investigations import InvestigationBroadcaster

    async def _no_redis() -> None:
        return None

    monkeypatch.setattr("app.services.investigations.get_redis_pool", _no_redis)

    broadcaster = InvestigationBroadcaster()
    inv_id = "inv_full_queue"
    queue = await broadcaster.subscribe(inv_id)

    for idx in range(200):
        queue.put_nowait({"id": f"ev_{idx}", "type": "heartbeat"})

    assert queue.full() is True

    await broadcaster.publish_terminal(inv_id)

    drained: list[dict[str, Any] | None] = []
    while not queue.empty():
        drained.append(queue.get_nowait())

    assert len(drained) == 200
    assert drained[-1] is None


async def test_model_gateway_astream_coerces_dict_chunks_to_schema_and_serializes_output(
    monkeypatch: Any,
) -> None:
    from app.agents.synthesizer import SynthesisOutput
    from app.config import Settings
    from app.services.model_gateway import ModelGateway

    class _FakeStructured:
        async def astream(self, _messages: object) -> Any:
            yield {
                "conclusion": "Streaming partial conclusion...",
                "recommendation": "escalate",
                "confidence": 0.77,
            }

        async def ainvoke(self, _messages: object) -> object:
            raise AssertionError("ainvoke should not be called when astream yields valid schema")

    class _FakeChatOpenAI:
        def __init__(self, **_kwargs: Any) -> None:
            pass

        def with_structured_output(self, _schema: Any, **_kwargs: Any) -> _FakeStructured:
            return _FakeStructured()

    monkeypatch.setattr("app.services.model_gateway.ChatOpenAI", _FakeChatOpenAI)

    settings = Settings(OPENAI_API_KEY="sk-test-key", MODEL_MAX_RETRIES=0)
    gateway = ModelGateway(settings)
    deltas: list[str] = []

    async def _on_delta(text: str) -> None:
        deltas.append(text)

    result = await gateway.generate_structured(
        system_prompt="sys",
        user_prompt="usr",
        schema=SynthesisOutput,
        prompt_template_id="tpl_1",
        prompt_template_version="v1",
        prompt_template_sha256="sha_1",
        on_delta=_on_delta,
    )

    assert result is not None
    assert isinstance(result.value, SynthesisOutput)
    assert result.value.conclusion == "Streaming partial conclusion..."
    assert result.value.recommendation == "escalate"
    assert result.output_text != ""
    assert '"recommendation":"escalate"' in result.output_text.replace(" ", "")
    assert any("Streaming partial conclusion..." in d for d in deltas)
