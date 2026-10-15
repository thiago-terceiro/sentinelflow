from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from time import monotonic
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
        ComplianceFinding.model_validate(item)
        for item in record.compliance_findings
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
        values["risk_assessment"].model_dump(mode="json")
        if values["risk_assessment"]
        else None
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
    await graph.ainvoke(graph_input, config=config)
    await persist_graph_state(session, record, graph, config)


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
    async with SessionLocal() as session:
        record = await session.get(InvestigationRecord, investigation_id)
        if record is None:
            return
        record.status = "failed"
        record.failure_reason = reason[:512]
        timeline_events = list(record.timeline_events or [])
        if not any(item.get("type") == "run_failed" for item in timeline_events):
            timeline_events.append(
                build_stream_event(
                    "run_failed",
                    {
                        "investigation_id": investigation_id,
                        "message": "Investigation failed. Retry or contact operations.",
                    },
                    event_id=f"run_failed_{investigation_id}",
                )
            )
            record.timeline_events = timeline_events
        await session.commit()


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
    principal = PrincipalContext(
        user_id=str(payload["principal_id"]),
        roles=[str(role) for role in payload.get("principal_roles", [])],
    )
    await _run_new_investigation(str(payload["investigation_id"]), principal)


async def run_resume_investigation_job(_ctx: dict[str, Any], payload: dict[str, Any]) -> None:
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


async def stream_graph_events(investigation_id: str) -> AsyncIterator[str]:
    last_event_count = 0
    emitted_terminal_failure = False
    last_output_at = monotonic()

    while True:
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

            graph = build_graph(session)
            snapshot = await graph.aget_state(thread_config(record.thread_id))
            snapshot_values = _snapshot_values(snapshot) if snapshot is not None else {}
            timeline_events = _as_timeline_events(snapshot_values.get("timeline_events"))

            if len(timeline_events) > last_event_count:
                for event in timeline_events[last_event_count:]:
                    yield serialize_event(event)
                    last_output_at = monotonic()
                last_event_count = len(timeline_events)

            if record.status in TERMINAL_STATUSES:
                if last_event_count == 0:
                    for event in replay_events(record):
                        yield serialize_event(event)
                    return
                already_has_failure = any(
                    e.get("type") == "run_failed" for e in timeline_events
                )
                should_emit_failure = (
                    record.status == "failed"
                    and not emitted_terminal_failure
                    and not already_has_failure
                )
                if should_emit_failure:
                    yield serialize_event(
                        build_stream_event(
                            "run_failed",
                            {
                                "investigation_id": record.id,
                                "message": "Investigation failed. Retry or contact operations.",
                                "failure_reason": record.failure_reason,
                            },
                            event_id=f"run_failed_{record.id}",
                        )
                    )
                    emitted_terminal_failure = True
                return

            if monotonic() - last_output_at >= STREAM_HEARTBEAT_SECONDS:
                yield serialize_event(
                    build_stream_event(
                        "heartbeat",
                        {
                            "investigation_id": investigation_id,
                            "status": record.status,
                        },
                        event_id=f"heartbeat_{investigation_id}_{last_event_count}",
                    )
                )
                last_output_at = monotonic()

        await asyncio.sleep(STREAM_POLL_INTERVAL_SECONDS)
