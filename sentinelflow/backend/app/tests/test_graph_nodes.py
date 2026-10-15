from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import TypedDict, cast

import pytest
from _pytest.monkeypatch import MonkeyPatch
from app.agents.investigator import InvestigatorAgent, InvestigatorIteration
from app.agents.synthesizer import SynthesizerAgent
from app.graph.nodes import InvestigationNodes
from app.graph.state import DisputeState
from app.schemas.disputes import DisputeDetail
from app.schemas.investigation import AnalyzerSummary, Evidence, EvidenceCategory
from app.services.model_gateway import LLMCallResult, ModelGateway
from sqlalchemy.ext.asyncio import AsyncSession


class _AuditCall(TypedDict):
    event_name: str
    payload: dict[str, object]


def _build_state() -> DisputeState:
    state: DisputeState = {
        "dispute_id": "disp_123",
        "investigation_id": "inv_123",
        "thread_id": "thread_123",
        "principal_id": "user_123",
        "principal_roles": ["investigator"],
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
        "status": "pending",
        "pending_tools": [],
        "pending_analyzers": [],
        "failed_tools": [],
        "failed_analyzers": [],
        "timeline_events": [],
        "approval_request": None,
        "approval_decision": None,
        "reviewer_guidance": None,
        "revision_count": 0,
        "checkpoint_ref": None,
    }
    return state


def _build_evidence(category: EvidenceCategory) -> Evidence:
    return Evidence(
        id=f"ev_{category}",
        source=category,
        category=category,
        summary=f"{category} evidence",
        facts={},
        confidence=0.8,
        collected_at=datetime.now(UTC),
        provenance="test",
    )


def _build_analyzer_summary(name: str) -> AnalyzerSummary:
    return AnalyzerSummary(
        analyzer=name,
        summary=f"{name} summary",
        findings=[],
        confidence=0.7,
        evidence_ids=["ev_transaction"],
        contradictions=[],
        recommended_followups=[],
    )


async def test_collect_keeps_successful_results_when_a_tool_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def ok_tool(_session: AsyncSession, _dispute_id: str) -> Evidence:
        return _build_evidence("transaction")

    async def failing_tool(_session: AsyncSession, _dispute_id: str) -> Evidence:
        raise RuntimeError("customer service unavailable")

    async def fake_audit_event(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.graph.nodes.record_audit_event", fake_audit_event)
    monkeypatch.setattr(
        "app.graph.nodes.fetch_transaction_history",
        ok_tool,
    )
    monkeypatch.setattr(
        "app.graph.nodes.fetch_customer_profile",
        failing_tool,
    )

    state = _build_state()
    state["pending_tools"] = [{"name": "transactions"}, {"name": "customer"}]
    nodes = InvestigationNodes(
        session=cast(AsyncSession, object()),
        investigator=cast(InvestigatorAgent, SimpleNamespace()),
        synthesizer=cast(SynthesizerAgent, SimpleNamespace()),
    )

    updated = await nodes.collect(state)

    assert updated["tool_call_count"] == 2
    assert [item.category for item in updated["evidence"]] == ["transaction"]
    assert updated["failed_tools"] == [
        {"name": "customer", "error": "customer service unavailable"}
    ]
    assert any(
        event["type"] == "agent_message"
        and event["data"].get("message") == "Calling evidence tools for investigator requests."
        for event in updated["timeline_events"]
    )
    assert any(event["type"] == "run_failed" for event in updated["timeline_events"])
    assert updated["pending_tools"] == []


async def test_collect_keeps_successful_results_when_an_analyzer_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_run_analyzer(name: str, _evidence: list[Evidence]) -> AnalyzerSummary:
        if name == "fraud_pattern":
            raise RuntimeError("analyzer timeout")
        return _build_analyzer_summary(name)

    async def fake_audit_event(*args: object, **kwargs: object) -> None:
        return None

    monkeypatch.setattr("app.graph.nodes.record_audit_event", fake_audit_event)
    monkeypatch.setattr("app.graph.nodes.run_analyzer", fake_run_analyzer)

    state = _build_state()
    state["evidence"] = [_build_evidence("transaction")]
    state["pending_analyzers"] = [
        {"name": "fraud_pattern"},
        {"name": "device_fingerprint"},
    ]
    nodes = InvestigationNodes(
        session=cast(AsyncSession, object()),
        investigator=cast(InvestigatorAgent, SimpleNamespace()),
        synthesizer=cast(SynthesizerAgent, SimpleNamespace()),
    )

    updated = await nodes.collect(state)

    assert updated["analyzer_call_count"] == 2
    assert [item.analyzer for item in updated["analyzer_summaries"]] == ["device_fingerprint"]
    assert updated["failed_analyzers"] == [
        {"name": "fraud_pattern", "error": "analyzer timeout"}
    ]
    assert any(
        event["type"] == "agent_message"
        and event["data"].get("message")
        == "Calling analyzer agents for specialized interpretation."
        for event in updated["timeline_events"]
    )
    assert any(event["type"] == "run_failed" for event in updated["timeline_events"])
    assert updated["pending_analyzers"] == []


class _NoopGateway:
    async def generate_structured(self, **_kwargs: object) -> None:
        return None


async def test_run_iteration_does_not_retry_failed_tools() -> None:
    agent = InvestigatorAgent(gateway=cast(ModelGateway, _NoopGateway()))
    dispute = DisputeDetail(
        id="disp_123",
        case_code="CASE-123",
        title="Card dispute",
        amount=120.0,
        currency="USD",
        status="open",
        created_at=datetime.now(UTC),
        customer_id="cust_123",
        merchant_id="merch_123",
        narrative="Customer denies transaction.",
        tags=[],
    )

    iteration, llm_meta = await agent.run_iteration(
        dispute=dispute,
        evidence=[],
        analyzers=[],
        failed_tools=[{"name": "transactions", "error": "ledger offline"}],
        failed_analyzers=[],
    )

    assert llm_meta is None
    assert all(item.name != "transactions" for item in iteration.tool_requests)
    assert "transactions data is unavailable: ledger offline" in iteration.unresolved_questions


async def test_investigate_writes_llm_iteration_audit_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    audit_calls: list[_AuditCall] = []

    async def fake_run_iteration(
        *,
        dispute: DisputeDetail,
        evidence: list[Evidence],
        analyzers: list[AnalyzerSummary],
        failed_tools: list[dict[str, str]],
        failed_analyzers: list[dict[str, str]],
    ) -> tuple[InvestigatorIteration, LLMCallResult[InvestigatorIteration] | None]:
        _ = (dispute, evidence, analyzers, failed_tools, failed_analyzers)
        iteration = InvestigatorIteration(
            summary="test",
            hypotheses=[],
            unresolved_questions=[],
            tool_requests=[],
            analyzer_requests=[],
            should_finish=True,
        )
        meta = LLMCallResult(
            value=iteration,
            provider="openai_compatible",
            model_used="gpt-4o",
            deployment_id="deploy-test",
            response_id="resp_123",
            prompt_template_id="investigator_iteration",
            prompt_template_version="2026-09-02",
            prompt_template_sha256="abc123",
            input_tokens=100,
            output_tokens=50,
            reasoning_tokens=0,
            latency_ms=123.4,
            prompt_text="prompt",
            output_text="output",
            reasoning_text=None,
        )
        return iteration, meta

    async def fake_record_audit_event(
        session: AsyncSession,
        *,
        actor: object,
        event_name: str,
        payload: dict[str, object],
        dispute_id: str | None = None,
        investigation_id: str | None = None,
    ) -> SimpleNamespace:
        _ = (session, actor, dispute_id, investigation_id)
        audit_calls.append({"event_name": event_name, "payload": payload})
        return SimpleNamespace(id="evt_1")

    monkeypatch.setattr("app.graph.nodes.record_audit_event", fake_record_audit_event)

    nodes = InvestigationNodes(
        session=cast(AsyncSession, object()),
        investigator=cast(InvestigatorAgent, SimpleNamespace(run_iteration=fake_run_iteration)),
        synthesizer=cast(SynthesizerAgent, SimpleNamespace()),
    )
    state = _build_state()
    state["dispute"] = DisputeDetail(
        id="disp_123",
        case_code="CASE-001",
        title="Test dispute",
        amount=100.0,
        currency="USD",
        status="open",
        created_at=datetime.now(UTC),
        customer_id="cust_1",
        merchant_id="merch_1",
        narrative="Test narrative",
        tags=[],
    )

    await nodes.investigate(state)

    assert len(audit_calls) == 1
    assert audit_calls[0]["event_name"] == "investigation.llm_iteration"
    payload = audit_calls[0]["payload"]
    assert payload["model_used"] == "gpt-4o"
    assert payload["input_tokens"] == 100
    assert payload["used_heuristic"] is False


async def test_investigate_records_heuristic_fallback_in_audit(
    monkeypatch: MonkeyPatch,
) -> None:
    audit_calls: list[_AuditCall] = []

    async def fake_run_iteration(
        *,
        dispute: DisputeDetail,
        evidence: list[Evidence],
        analyzers: list[AnalyzerSummary],
        failed_tools: list[dict[str, str]],
        failed_analyzers: list[dict[str, str]],
    ) -> tuple[InvestigatorIteration, LLMCallResult[InvestigatorIteration] | None]:
        _ = (dispute, evidence, analyzers, failed_tools, failed_analyzers)
        iteration = InvestigatorIteration(
            summary="heuristic",
            hypotheses=[],
            unresolved_questions=[],
            tool_requests=[],
            analyzer_requests=[],
            should_finish=True,
        )
        return iteration, None  # None = heuristic path

    async def fake_record_audit_event(
        session: AsyncSession,
        *,
        actor: object,
        event_name: str,
        payload: dict[str, object],
        dispute_id: str | None = None,
        investigation_id: str | None = None,
    ) -> SimpleNamespace:
        _ = (session, actor, dispute_id, investigation_id)
        audit_calls.append({"event_name": event_name, "payload": payload})
        return SimpleNamespace(id="evt_1")

    monkeypatch.setattr("app.graph.nodes.record_audit_event", fake_record_audit_event)

    nodes = InvestigationNodes(
        session=cast(AsyncSession, object()),
        investigator=cast(InvestigatorAgent, SimpleNamespace(run_iteration=fake_run_iteration)),
        synthesizer=cast(SynthesizerAgent, SimpleNamespace()),
    )
    state = _build_state()
    state["dispute"] = DisputeDetail(
        id="disp_123",
        case_code="CASE-001",
        title="Test dispute",
        amount=100.0,
        currency="USD",
        status="open",
        created_at=datetime.now(UTC),
        customer_id="cust_1",
        merchant_id="merch_1",
        narrative="Test narrative",
        tags=[],
    )

    await nodes.investigate(state)

    assert len(audit_calls) == 1
    payload = audit_calls[0]["payload"]
    assert payload["model_used"] == "heuristic"
    assert payload["used_heuristic"] is True
    assert payload["input_tokens"] == 0