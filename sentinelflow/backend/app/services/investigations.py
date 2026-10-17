from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import uuid4

from app.config import get_settings
from app.db.models import InvestigationRecord
from app.db.session import SessionLocal
from app.graph.graph import build_graph
from app.schemas.events import StreamEvent, StreamEventType
from app.schemas.investigation import (
    ComplianceFinding,
    InvestigationBudget,
    InvestigationReport,
    InvestigationRun,
    InvestigationStatus,
    RiskAssessment,
)
from app.security import Principal
from arq import create_pool
from arq.connections import RedisSettings
from langgraph.types import Command
from opentelemetry import trace
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)
settings = get_settings()
STREAM_POLL_INTERVAL_SECONDS = 0.25
STREAM_HEARTBEAT_SECONDS = 10.0
TERMINAL_STATUSES = {"awaiting_approval", "completed", "failed"}
RUN_JOB = "run_investigation_job"
RESUME_JOB = "run_resume_investigation_job"
ACTIVE_JOB_ID_TEMPLATE = "investigation:{investigation_id}:active"
VALID_INVESTIGATION_STATUSES = {
    "pending",
    "running",
    "awaiting_approval",
    "completed",
    "failed",
}


STREAM_REDIS_CHANNEL_PREFIX = "sentinelflow:stream:"


def _stream_redis_channel(investigation_id: str) -> str:
    return f"{STREAM_REDIS_CHANNEL_PREFIX}{investigation_id}"


class InvestigationBroadcaster:
    """Event hub for real-time SSE streaming across in-memory queues and Redis Pub/Sub."""

    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any] | None]]] = {}
        self._lock = asyncio.Lock()

    async def subscribe(self, investigation_id: str) -> asyncio.Queue[dict[str, Any] | None]:
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.setdefault(investigation_id, set()).add(queue)
        return queue

    async def unsubscribe(
        self, investigation_id: str, queue: asyncio.Queue[dict[str, Any] | None]
    ) -> None:
        async with self._lock:
            subs = self._subscribers.get(investigation_id)
            if subs is not None:
                subs.discard(queue)
                if not subs:
                    self._subscribers.pop(investigation_id, None)

    async def publish(self, investigation_id: str, event: dict[str, Any]) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(investigation_id, ()))
        for q in subs:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                logger.debug("Dropped live SSE event for full queue: %s", investigation_id)
        if _shared_redis_pool is not None and hasattr(_shared_redis_pool, "publish"):
            try:
                await _shared_redis_pool.publish(
                    _stream_redis_channel(investigation_id),
                    json.dumps(event),
                )
            except Exception as exc:
                logger.debug("Redis stream publish skipped for %s: %s", investigation_id, exc)

    async def publish_terminal(self, investigation_id: str) -> None:
        async with self._lock:
            subs = list(self._subscribers.get(investigation_id, ()))
        for q in subs:
            try:
                q.put_nowait(None)
            except asyncio.QueueFull:
                logger.debug("Dropped terminal SSE signal for full queue: %s", investigation_id)
        if _shared_redis_pool is not None and hasattr(_shared_redis_pool, "publish"):
            try:
                await _shared_redis_pool.publish(
                    _stream_redis_channel(investigation_id),
                    json.dumps({"__terminal__": True}),
                )
            except Exception as exc:
                logger.debug("Redis terminal publish skipped for %s: %s", investigation_id, exc)


investigation_broadcaster = InvestigationBroadcaster()


@dataclass(frozen=True, slots=True)
class PrincipalContext:
    user_id: str
    roles: list[str]

    @classmethod
    def from_principal(cls, principal: Principal) -> PrincipalContext:
        return cls(
            user_id=principal.user_id,
            roles=sorted(role.value for role in principal.roles),
        )


def budget() -> InvestigationBudget:
    return InvestigationBudget(
        max_iterations=settings.INVESTIGATION_MAX_ITERATIONS,
        max_tool_calls=settings.INVESTIGATION_MAX_TOOL_CALLS,
        max_analyzer_calls=settings.INVESTIGATION_MAX_ANALYZER_CALLS,
        max_tokens=settings.INVESTIGATION_MAX_TOKENS,
        max_seconds=settings.INVESTIGATION_MAX_SECONDS,
    )


def _coerce_investigation_status(value: str) -> InvestigationStatus:
    if value in VALID_INVESTIGATION_STATUSES:
        return cast(InvestigationStatus, value)
    return "failed"


def _as_object(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    value_dict = cast(dict[object, object], value)
    return {str(key): item for key, item in value_dict.items()}


def _as_timeline_events(value: object) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    items = cast(list[object], value)
    events: list[dict[str, Any]] = []
    for item in items:
        event = _as_object(item)
        if event:
            events.append(event)
    return events


def _snapshot_values(snapshot: object) -> dict[str, Any]:
    return _as_object(getattr(snapshot, "values", None))


def _snapshot_checkpoint_id(snapshot: object, fallback: str) -> str:
    config = _as_object(getattr(snapshot, "config", None))
    configurable = _as_object(config.get("configurable"))
    checkpoint_id = configurable.get("checkpoint_id")
    if isinstance(checkpoint_id, str) and checkpoint_id:
        return checkpoint_id
    return fallback


def to_run(record: InvestigationRecord) -> InvestigationRun:
    risk_assessment = (
        RiskAssessment.model_validate(record.risk_assessment)
        if isinstance(record.risk_assessment, dict)
        else None
    )
    compliance_findings = [
        ComplianceFinding.model_validate(item) for item in record.compliance_findings
    ]
    report = (
        InvestigationReport.model_validate(record.report)
        if isinstance(record.report, dict)
        else None
    )
    return InvestigationRun(
        id=record.id,
        dispute_id=record.dispute_id,
        thread_id=record.thread_id,
        status=_coerce_investigation_status(record.status),
        created_at=record.created_at,
        updated_at=record.updated_at,
        budget=budget(),
        risk_assessment=risk_assessment,
        compliance_findings=compliance_findings,
        report=report,
    )


def thread_config(thread_id: str) -> dict[str, dict[str, str]]:
    return {"configurable": {"thread_id": thread_id}}


def build_stream_event(
    event_type: StreamEventType,
    data: dict[str, Any],
    *,
    event_id: str | None = None,
) -> dict[str, Any]:
    return StreamEvent(
        id=event_id or f"evt_{uuid4().hex[:10]}",
        type=event_type,
        timestamp=datetime.now(UTC),
        data=data,
    ).model_dump(mode="json")


def serialize_event(event: dict[str, Any]) -> str:
    return f"data: {json.dumps(event)}\n\n"


def initial_state(record: InvestigationRecord, principal: PrincipalContext) -> dict[str, Any]:
    return {
        "dispute_id": record.dispute_id,
        "investigation_id": record.id,
        "thread_id": record.thread_id,
        "principal_id": principal.user_id,
        "principal_roles": principal.roles,
        "dispute": None,
        "messages": [],
        "evidence": [],
        "analyzer_summaries": [],
        "hypotheses": [],
        "unresolved_questions": [],
        "risk_assessment": None,
        "compliance_findings": [],
        "investigation_report": None,
        "iteration_count": 0,
        "tool_call_count": 0,
        "analyzer_call_count": 0,
        "status": "running",
        "pending_tools": [],
        "pending_analyzers": [],
        "failed_tools": [],
        "failed_analyzers": [],
        "timeline_events": [
            build_stream_event(
                "run_started",
                {"investigation_id": record.id, "thread_id": record.thread_id},
                event_id=f"run_started_{record.id}",
            )
        ],
        "approval_request": None,
        "approval_decision": None,
        "reviewer_guidance": None,
        "revision_count": 0,
        "checkpoint_ref": None,
    }


def extract_timeline_events(update: dict[str, Any]) -> list[dict[str, Any]]:
    for value in update.values():
        value_obj = _as_object(value)
        timeline_events = _as_timeline_events(value_obj.get("timeline_events"))
        if timeline_events:
            return timeline_events
    return []


def replay_events(record: InvestigationRecord) -> Iterable[dict[str, Any]]:
    saved = _as_timeline_events(getattr(record, "timeline_events", None))
    if saved:
        yield from saved
        return
    # Fallback for records persisted before the timeline_events column was added.
    yield build_stream_event(
        "run_started",
        {"investigation_id": record.id, "thread_id": record.thread_id},
        event_id=f"run_started_{record.id}",
    )
    for item in record.evidence:
        evidence_id = item.get("id") if isinstance(item.get("id"), str) else "unknown"
        yield build_stream_event(
            "evidence_added",
            item,
            event_id=f"evidence_{evidence_id}",
        )
    if record.risk_assessment:
        yield build_stream_event(
            "risk_updated",
            record.risk_assessment,
            event_id=f"risk_{record.id}",
        )
    if record.report:
        yield build_stream_event(
            "final_report_ready",
            record.report,
            event_id=f"report_{record.id}",
        )
    if record.status == "awaiting_approval":
        yield build_stream_event(
            "approval_required",
            {"investigation_id": record.id, "report": record.report},
            event_id=f"approval_{record.id}",
        )
    elif record.status == "failed":
        yield build_stream_event(
            "run_failed",
            {
                "investigation_id": record.id,
                "message": "Investigation failed. Retry or contact operations.",
                "failure_reason": getattr(record, "failure_reason", None),
            },
            event_id=f"run_failed_{record.id}",
        )
    elif record.status == "completed":
        yield build_stream_event(
            "run_completed",
            {"investigation_id": record.id, "report": record.report},
            event_id=f"run_completed_{record.id}",
        )


async def persist_graph_state(
    session: AsyncSession,
    record: InvestigationRecord,
    graph: Any,
    config: dict[str, Any],
) -> InvestigationRecord:
    snapshot = await graph.aget_state(config)
    values = _snapshot_values(snapshot)
    has_pending_next = bool(getattr(snapshot, "next", None))
    state_status = values.get("status")
    fallback_status = _coerce_investigation_status(record.status)
    resolved_status = (
        _coerce_investigation_status(state_status)
        if isinstance(state_status, str)
        else fallback_status
    )
    record.status = "awaiting_approval" if has_pending_next else resolved_status
    record.evidence = [item.model_dump(mode="json") for item in values["evidence"]]
    record.analyzer_summaries = [
        item.model_dump(mode="json") for item in values["analyzer_summaries"]
    ]
    record.hypotheses = [item.model_dump(mode="json") for item in values["hypotheses"]]
    record.unresolved_questions = values["unresolved_questions"]
    record.risk_assessment = (
        values["risk_assessment"].model_dump(mode="json") if values["risk_assessment"] else None
    )
    record.compliance_findings = [
        item.model_dump(mode="json") for item in values["compliance_findings"]
    ]
    record.report = (
        values["investigation_report"].model_dump(mode="json")
        if values["investigation_report"]
        else None
    )
    record.iteration_count = values["iteration_count"]
    record.tool_call_count = values["tool_call_count"]
    record.analyzer_call_count = values["analyzer_call_count"]
    record.timeline_events = _as_timeline_events(values.get("timeline_events"))
    record.checkpoint_id = _snapshot_checkpoint_id(snapshot, record.thread_id)
    await session.commit()
    await session.refresh(record)
    return record


async def _run_graph(
    session: AsyncSession,
    record: InvestigationRecord,
    graph_input: dict[str, Any] | Command[tuple[()]] | None,
) -> None:
    graph = build_graph(session)
    config = thread_config(record.thread_id)
    seen_ids: set[str] = set()
    accumulated_events: list[dict[str, Any]] = []
    if record.timeline_events:
        for ev in record.timeline_events:
            accumulated_events.append(ev)
            eid = ev.get("id")
            if eid:
                seen_ids.add(eid)

    if hasattr(graph, "astream"):
        async for chunk in graph.astream(graph_input, config=config, stream_mode="updates"):
            if isinstance(chunk, dict):
                new_events = extract_timeline_events(chunk)
                chunk_added = False
                for event in new_events:
                    eid = event.get("id")
                    if eid and eid in seen_ids:
                        continue
                    if eid:
                        seen_ids.add(eid)
                    accumulated_events.append(event)
                    chunk_added = True
                    await investigation_broadcaster.publish(record.id, event)
                if chunk_added:
                    record.timeline_events = list(accumulated_events)
                    await session.commit()
    elif hasattr(graph, "ainvoke"):
        await graph.ainvoke(graph_input, config=config)

    await persist_graph_state(session, record, graph, config)
    for event in replay_events(record):
        eid = event.get("id")
        if eid and eid not in seen_ids:
            seen_ids.add(eid)
            await investigation_broadcaster.publish(record.id, event)
    await investigation_broadcaster.publish_terminal(record.id)


def _redis_settings() -> RedisSettings:
    return RedisSettings.from_dsn(settings.QUEUE_REDIS_URL)


_shared_redis_pool: Any = None
_redis_pool_lock: asyncio.Lock | None = None


def _get_redis_pool_lock() -> asyncio.Lock:
    global _redis_pool_lock
    if _redis_pool_lock is None:
        _redis_pool_lock = asyncio.Lock()
    return _redis_pool_lock


async def get_redis_pool() -> Any:
    global _shared_redis_pool
    if _shared_redis_pool is not None:
        return _shared_redis_pool
    async with _get_redis_pool_lock():
        if _shared_redis_pool is None:
            _shared_redis_pool = await create_pool(_redis_settings())
        return _shared_redis_pool


async def close_redis_pool() -> None:
    global _shared_redis_pool
    async with _get_redis_pool_lock():
        if _shared_redis_pool is not None:
            await _shared_redis_pool.aclose()
            _shared_redis_pool = None


def _active_job_id(investigation_id: str) -> str:
    return ACTIVE_JOB_ID_TEMPLATE.format(investigation_id=investigation_id)


async def _enqueue_job(
    job_name: str,
    *,
    job_id: str,
    payload: dict[str, Any],
) -> bool:
    pool = await get_redis_pool()
    job = await pool.enqueue_job(job_name, payload, _job_id=job_id)
    return job is not None


async def _mark_failed_with_reason(investigation_id: str, reason: str) -> None:
    failure_event: dict[str, Any] | None = None
    async with SessionLocal() as session:
        record = await session.get(InvestigationRecord, investigation_id)
        if record is None:
            return
        record.status = "failed"
        record.failure_reason = reason[:512]
        timeline_events = list(record.timeline_events or [])
        if not any(item.get("type") == "run_failed" for item in timeline_events):
            failure_event = build_stream_event(
                "run_failed",
                {
                    "investigation_id": investigation_id,
                    "message": "Investigation failed. Retry or contact operations.",
                    "failure_reason": record.failure_reason,
                },
                event_id=f"run_failed_{investigation_id}",
            )
            timeline_events.append(failure_event)
            record.timeline_events = timeline_events
        await session.commit()
    if failure_event is not None:
        await investigation_broadcaster.publish(investigation_id, failure_event)
    await investigation_broadcaster.publish_terminal(investigation_id)


async def _run_new_investigation(
    investigation_id: str,
    principal: PrincipalContext,
) -> None:
    tracer = trace.get_tracer("sentinelflow.investigations")
    with tracer.start_as_current_span(
        "investigation.workflow",
        attributes={
            "investigation.id": investigation_id,
            "principal.id": principal.user_id,
        },
    ) as span:
        try:
            async with SessionLocal() as session:
                record = await session.get(InvestigationRecord, investigation_id)
                if record is None or record.status in TERMINAL_STATUSES:
                    return
                span.set_attribute("dispute.id", record.dispute_id)
                span.set_attribute("thread.id", record.thread_id)
                record.status = "running"
                await session.commit()
                await session.refresh(record)

                graph = build_graph(session)
                config = thread_config(record.thread_id)
                snapshot = await graph.aget_state(config)
                snapshot_values = _snapshot_values(snapshot) if snapshot is not None else {}
                graph_input = None if snapshot_values else initial_state(record, principal)
                await _run_graph(session, record, graph_input)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            await _mark_failed_with_reason(investigation_id, "Investigation execution failed.")
            raise


async def _run_resume_investigation(
    investigation_id: str,
    decision: dict[str, Any],
) -> None:
    tracer = trace.get_tracer("sentinelflow.investigations")
    with tracer.start_as_current_span(
        "investigation.resume_workflow",
        attributes={
            "investigation.id": investigation_id,
            "decision.action": str(decision.get("decision", "unknown")),
        },
    ) as span:
        try:
            async with SessionLocal() as session:
                record = await session.get(InvestigationRecord, investigation_id)
                if record is None:
                    return
                span.set_attribute("dispute.id", record.dispute_id)
                span.set_attribute("thread.id", record.thread_id)
                record.status = "running"
                await session.commit()
                await session.refresh(record)
                resume_command: Command[tuple[()]] = Command(resume=decision)
                await _run_graph(session, record, resume_command)
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc))
            await _mark_failed_with_reason(investigation_id, "Investigation resume failed.")
            raise


async def run_investigation_job(_ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    global _shared_redis_pool
    if _shared_redis_pool is None and _ctx.get("redis") is not None:
        _shared_redis_pool = _ctx["redis"]
    principal = PrincipalContext(
        user_id=str(payload["principal_id"]),
        roles=[str(role) for role in payload.get("principal_roles", [])],
    )
    await _run_new_investigation(str(payload["investigation_id"]), principal)


async def run_resume_investigation_job(_ctx: dict[str, Any], payload: dict[str, Any]) -> None:
    global _shared_redis_pool
    if _shared_redis_pool is None and _ctx.get("redis") is not None:
        _shared_redis_pool = _ctx["redis"]
    await _run_resume_investigation(
        str(payload["investigation_id"]),
        payload.get("decision", {}),
    )


async def schedule_investigation(
    investigation_id: str,
    principal: PrincipalContext,
) -> bool:
    return await _enqueue_job(
        RUN_JOB,
        job_id=_active_job_id(investigation_id),
        payload={
            "investigation_id": investigation_id,
            "principal_id": principal.user_id,
            "principal_roles": principal.roles,
        },
    )


async def schedule_resume(
    investigation_id: str,
    decision: dict[str, Any],
) -> bool:
    return await _enqueue_job(
        RESUME_JOB,
        job_id=_active_job_id(investigation_id),
        payload={
            "investigation_id": investigation_id,
            "decision": decision,
        },
    )


async def _forward_redis_pubsub(
    investigation_id: str,
    queue: asyncio.Queue[dict[str, Any] | None],
) -> None:
    if _shared_redis_pool is None or not hasattr(_shared_redis_pool, "pubsub"):
        return
    channel = _stream_redis_channel(investigation_id)
    try:
        async with _shared_redis_pool.pubsub() as pubsub:
            await pubsub.subscribe(channel)
            async for message in pubsub.listen():
                if not isinstance(message, dict) or message.get("type") != "message":
                    continue
                raw_data = message.get("data")
                if isinstance(raw_data, bytes):
                    raw_data = raw_data.decode("utf-8")
                if not isinstance(raw_data, str):
                    continue
                parsed = json.loads(raw_data)
                if isinstance(parsed, dict):
                    if parsed.get("__terminal__") is True:
                        try:
                            queue.put_nowait(None)
                        except asyncio.QueueFull:
                            pass
                        break
                    try:
                        queue.put_nowait(parsed)
                    except asyncio.QueueFull:
                        pass
    except (asyncio.CancelledError, Exception):
        return


async def stream_graph_events(investigation_id: str) -> AsyncIterator[str]:
    queue = await investigation_broadcaster.subscribe(investigation_id)
    redis_listener_task = asyncio.create_task(_forward_redis_pubsub(investigation_id, queue))
    emitted_ids: set[str] = set()

    try:
        async with SessionLocal() as session:
            record = await session.get(InvestigationRecord, investigation_id)
            if record is None:
                yield serialize_event(
                    build_stream_event(
                        "run_failed",
                        {
                            "investigation_id": investigation_id,
                            "message": "Investigation was not found.",
                        },
                        event_id=f"run_failed_{investigation_id}",
                    )
                )
                return

            timeline_events = _as_timeline_events(getattr(record, "timeline_events", None))
            if not timeline_events:
                graph = build_graph(session)
                snapshot = await graph.aget_state(thread_config(record.thread_id))
                snapshot_values = _snapshot_values(snapshot) if snapshot is not None else {}
                timeline_events = _as_timeline_events(snapshot_values.get("timeline_events"))

            for event in timeline_events:
                eid = event.get("id")
                if eid:
                    emitted_ids.add(eid)
                yield serialize_event(event)

            if record.status in TERMINAL_STATUSES:
                if not timeline_events:
                    for event in replay_events(record):
                        eid = event.get("id")
                        if eid:
                            emitted_ids.add(eid)
                        yield serialize_event(event)

                has_failure = any(e.get("type") == "run_failed" for e in timeline_events)
                if record.status == "failed" and not has_failure:
                    yield serialize_event(
                        build_stream_event(
                            "run_failed",
                            {
                                "investigation_id": record.id,
                                "message": "Investigation failed. Retry or contact operations.",
                                "failure_reason": getattr(record, "failure_reason", None),
                            },
                            event_id=f"run_failed_{record.id}",
                        )
                    )
                return

        while True:
            try:
                stream_item = await asyncio.wait_for(queue.get(), timeout=STREAM_HEARTBEAT_SECONDS)
                if stream_item is None:
                    break
                event = stream_item
                eid = event.get("id")
                if eid and eid in emitted_ids:
                    continue
                if eid:
                    emitted_ids.add(eid)
                yield serialize_event(event)
                if event.get("type") in {"run_completed", "run_failed", "approval_required"}:
                    break
            except TimeoutError:
                yield serialize_event(
                    build_stream_event(
                        "heartbeat",
                        {"investigation_id": investigation_id, "status": "running"},
                        event_id=f"heartbeat_{investigation_id}_{len(emitted_ids)}",
                    )
                )
                async with SessionLocal() as session:
                    rec = await session.get(InvestigationRecord, investigation_id)
                    if rec is not None:
                        for ev in _as_timeline_events(getattr(rec, "timeline_events", None)):
                            ev_id = ev.get("id")
                            if ev_id and ev_id not in emitted_ids:
                                emitted_ids.add(ev_id)
                                yield serialize_event(ev)
                        if rec.status in TERMINAL_STATUSES:
                            for ev in replay_events(rec):
                                ev_id = ev.get("id")
                                if ev_id and ev_id not in emitted_ids:
                                    emitted_ids.add(ev_id)
                                    yield serialize_event(ev)
                            break
    finally:
        redis_listener_task.cancel()
        await asyncio.gather(redis_listener_task, return_exceptions=True)
        await investigation_broadcaster.unsubscribe(investigation_id, queue)
