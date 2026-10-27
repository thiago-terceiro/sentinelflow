from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

from app.db.models import DisputeRecord, InvestigationRecord
from app.db.session import SessionLocal
from app.security import Principal, Role
from app.services.audit import record_audit_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

CASES: list[dict[str, Any]] = [
    {
        "case_code": "SF-10001",
        "title": "High-value electronics charge after SIM swap signal",
        "narrative": (
            "Customer reports an unauthorized $4,899.00 electronics purchase from an "
            "unrecognized device 6,800km away immediately following an OTP bypass alert."
        ),
        "customer_id": "cust-001",
        "merchant_id": "merch-001",
        "amount": 4899.0,
        "status": "open",
        "attributes": {
            "tags": ["fraud", "high_value", "account_takeover"],
            "transaction": {
                "velocity_24h": 9,
                "geo_anomaly": True,
                "authorization_events": ["otp_bypass"],
            },
            "customer": {"prior_disputes": 1, "prior_fraud_signals": 2, "tenure_years": 1},
            "device": {"recognized_device": False, "ip_velocity": 14, "geo_distance_km": 6800},
            "merchant": {"merchant_risk": 0.61, "chargeback_rate": 0.08},
        },
    },
    {
        "case_code": "SF-10002",
        "title": "High-value luxury travel booking on unrecognized IP",
        "narrative": (
            "Customer disputes a $2,200.00 international travel booking. Account has an "
            "8-year tenure, but transaction exceeded $2,000 compliance review threshold."
        ),
        "customer_id": "cust-002",
        "merchant_id": "merch-002",
        "amount": 2200.0,
        "status": "open",
        "attributes": {
            "tags": ["travel", "compliance_review"],
            "transaction": {
                "velocity_24h": 2,
                "geo_anomaly": True,
                "authorization_events": ["3ds_challenge"],
            },
            "customer": {"prior_disputes": 0, "prior_fraud_signals": 0, "tenure_years": 8},
            "device": {"recognized_device": False, "ip_velocity": 3, "geo_distance_km": 420},
            "merchant": {"merchant_risk": 0.28, "chargeback_rate": 0.03},
        },
    },
    {
        "case_code": "SF-10003",
        "title": "Ambiguous digital goods purchase",
        "narrative": (
            "Conflicting telemetry leaves the recurring digital subscription claim unresolved."
        ),
        "customer_id": "cust-003",
        "merchant_id": "merch-003",
        "amount": 799.0,
        "status": "open",
        "attributes": {
            "tags": ["ambiguous"],
            "transaction": {
                "velocity_24h": 3,
                "geo_anomaly": True,
                "authorization_events": ["avs_match"],
            },
            "customer": {"prior_disputes": 1, "prior_fraud_signals": 0, "tenure_years": 4},
            "device": {"recognized_device": False, "ip_velocity": 2, "geo_distance_km": 140},
            "merchant": {"merchant_risk": 0.25, "chargeback_rate": 0.03},
        },
    },
    {
        "case_code": "SF-10004",
        "title": "Analyzer failure resilience case",
        "narrative": "Case used to verify investigation continues when an analyzer is unavailable.",
        "customer_id": "cust-004",
        "merchant_id": "merch-004",
        "amount": 1600.0,
        "status": "open",
        "attributes": {
            "tags": ["analyzer_failure"],
            "transaction": {
                "velocity_24h": 4,
                "geo_anomaly": False,
                "authorization_events": ["3ds_challenge"],
            },
            "customer": {"prior_disputes": 0, "prior_fraud_signals": 1, "tenure_years": 2},
            "device": {"recognized_device": True, "ip_velocity": 6, "geo_distance_km": 45},
            "merchant": {"merchant_risk": 0.44, "chargeback_rate": 0.06},
        },
    },
    {
        "case_code": "SF-10005",
        "title": "Contradictory analyzer signals",
        "narrative": (
            "Two analyzers disagree on the likelihood of account compromise vs friendly fraud."
        ),
        "customer_id": "cust-005",
        "merchant_id": "merch-005",
        "amount": 1299.0,
        "status": "open",
        "attributes": {
            "tags": ["contradiction"],
            "transaction": {
                "velocity_24h": 5,
                "geo_anomaly": True,
                "authorization_events": ["manual_keyed"],
            },
            "customer": {"prior_disputes": 2, "prior_fraud_signals": 0, "tenure_years": 6},
            "device": {"recognized_device": True, "ip_velocity": 8, "geo_distance_km": 2100},
            "merchant": {"merchant_risk": 0.31, "chargeback_rate": 0.04},
        },
    },
]


def _iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()


async def _seed_showcase_investigations(
    session: AsyncSession,
    disputes_by_code: dict[str, DisputeRecord],
) -> None:
    existing_inv = (
        await session.execute(select(InvestigationRecord.id).limit(1))
    ).scalar_one_or_none()
    if existing_inv is not None:
        return

    now = datetime.now(UTC)
    investigator_actor = Principal(user_id="seed-investigator", roles={Role.INVESTIGATOR})
    reviewer_actor = Principal(user_id="seed-reviewer", roles={Role.REVIEWER})

    # -------------------------------------------------------------------------
    # Showcase 1: SF-10001 — Completed 2-Iteration Human-Steered Investigation
    # -------------------------------------------------------------------------
    sf1 = disputes_by_code.get("SF-10001") or disputes_by_code.get("SF-A")
    if sf1 is not None:
        inv1_id = "inv_seed_sf_10001"
        t0 = now - timedelta(minutes=12)
        ev_tx = {
            "id": "ev_tx_10001",
            "source": "transactions",
            "category": "transaction",
            "origin": "observed_fact",
            "summary": "High-velocity electronics purchase ($4,899.00) with OTP bypass signal.",
            "facts": {
                "transaction_id": "txn_sf_10001",
                "amount": 4899.0,
                "velocity_24h": 9,
                "geo_anomaly": True,
                "authorization_events": ["otp_bypass"],
                "card_last4": "4821",
            },
            "confidence": 0.96,
            "collected_at": _iso(t0 + timedelta(seconds=2)),
            "provenance": "postgres://disputes/SF-10001/transactions",
        }
        ev_cust = {
            "id": "ev_cust_10001",
            "source": "customer",
            "category": "customer",
            "origin": "observed_fact",
            "summary": "Customer tenure 1 year with 2 prior SIM-swap fraud signals.",
            "facts": {"prior_disputes": 1, "prior_fraud_signals": 2, "tenure_years": 1},
            "confidence": 0.92,
            "collected_at": _iso(t0 + timedelta(seconds=3)),
            "provenance": "postgres://disputes/SF-10001/customer",
        }
        ev_dev = {
            "id": "ev_dev_10001",
            "source": "device",
            "category": "device",
            "origin": "observed_fact",
            "summary": (
                "Unrecognized device fingerprint 6,800km from home region (IP velocity: 14)."
            ),
            "facts": {"recognized_device": False, "ip_velocity": 14, "geo_distance_km": 6800},
            "confidence": 0.97,
            "collected_at": _iso(t0 + timedelta(seconds=4)),
            "provenance": "postgres://disputes/SF-10001/device",
        }
        ev_merch = {
            "id": "ev_merch_10001",
            "source": "merchant",
            "category": "merchant",
            "origin": "observed_fact",
            "summary": "Elevated merchant risk tier (0.61) with 8.0% rolling chargeback rate.",
            "facts": {"merchant_risk": 0.61, "chargeback_rate": 0.08},
            "confidence": 0.91,
            "collected_at": _iso(t0 + timedelta(seconds=5)),
            "provenance": "postgres://disputes/SF-10001/merchant",
        }

        an_fraud = {
            "analyzer": "fraud_pattern",
            "origin": "analyzer_interpretation",
            "summary": "High-confidence ATO pattern combining OTP bypass and 24h velocity spike.",
            "findings": [
                "9 transactions in 24h window with OTP bypass event",
                "Merchant chargeback rate (8%) exceeds 5% network threshold",
            ],
            "confidence": 0.93,
            "evidence_ids": ["ev_tx_10001", "ev_merch_10001"],
            "contradictions": [],
            "recommended_followups": ["Correlate SIM swap timestamp with IP velocity burst"],
        }
        an_device = {
            "analyzer": "device_fingerprint",
            "origin": "analyzer_interpretation",
            "summary": "Unrecognized device at 6,800km distance indicates remote session hijack.",
            "findings": [
                "Unrecognized hardware fingerprint on high-value checkout",
                "14 distinct IP addresses observed in 60-minute window",
            ],
            "confidence": 0.95,
            "evidence_ids": ["ev_dev_10001", "ev_cust_10001"],
            "contradictions": [],
            "recommended_followups": [],
        }

        iter1_hypotheses = [
            {
                "statement": "Account takeover via foreign device and OTP bypass",
                "confidence": 0.78,
                "supporting_evidence_ids": ["ev_tx_10001", "ev_dev_10001"],
                "contradicting_evidence_ids": [],
                "thought_process": (
                    "Initial telemetry shows OTP bypass in [cite: ev_tx_10001] and unrecognized "
                    "device in [cite: ev_dev_10001], though merchant exposure needs deeper review."
                ),
            },
            {
                "statement": "Potential unannounced international cardholder travel",
                "confidence": 0.34,
                "supporting_evidence_ids": ["ev_cust_10001"],
                "contradicting_evidence_ids": ["ev_dev_10001"],
                "thought_process": (
                    "Checking whether customer travel could explain the 6,800km shift."
                ),
            },
        ]

        iter2_hypotheses = [
            {
                "statement": "Account takeover via foreign device and OTP bypass",
                "confidence": 0.94,
                "supporting_evidence_ids": ["ev_tx_10001", "ev_dev_10001", "ev_cust_10001"],
                "contradicting_evidence_ids": [],
                "thought_process": (
                    "Following reviewer steering, cross-referencing [cite: ev_tx_10001] and "
                    "[cite: ev_dev_10001] confirms SIM-swap OTP interception from 6,800km away."
                ),
            },
            {
                "statement": "Collusive high-risk electronics merchant ring exposure",
                "confidence": 0.89,
                "supporting_evidence_ids": ["ev_merch_10001", "ev_tx_10001"],
                "contradicting_evidence_ids": [],
                "thought_process": (
                    "Merchant chargeback rate of 8.0% in [cite: ev_merch_10001] combined with "
                    "rapid gift/electronics liquidation confirms high-risk merchant exposure."
                ),
            },
        ]

        risk_iter1 = {
            "score": 0.76,
            "level": "high",
            "explanation": (
                "Initial high risk driven by transaction amount ($4,899) and device distance."
            ),
            "factors": [
                {
                    "name": "transaction_amount",
                    "weight": 0.22,
                    "value": 0.85,
                    "rationale": "Disputed amount $4,899.00 exceeds high-value threshold.",
                },
                {
                    "name": "device_trust",
                    "weight": 0.18,
                    "value": 0.82,
                    "rationale": "Unrecognized device 6,800km from baseline.",
                },
            ],
        }

        risk_iter2 = {
            "score": 0.91,
            "level": "critical",
            "explanation": (
                "Critical composite fraud risk (0.91) after incorporating merchant chargeback "
                "rate (8.0%) and confirmed SIM-swap OTP bypass."
            ),
            "factors": [
                {
                    "name": "transaction_amount",
                    "weight": 0.22,
                    "value": 0.95,
                    "rationale": "High-value $4,899.00 electronics checkout during velocity burst.",
                },
                {
                    "name": "device_trust",
                    "weight": 0.18,
                    "value": 0.96,
                    "rationale": "Unrecognized device fingerprint with 14 IPs at 6,800km distance.",
                },
                {
                    "name": "merchant_risk",
                    "weight": 0.12,
                    "value": 0.88,
                    "rationale": "Merchant risk 0.61 with 8.0% chargeback rate.",
                },
            ],
        }

        compliance_findings = [
            {
                "code": "CN-001",
                "severity": "warning",
                "message": (
                    "Dispute amount ($4,899.00) exceeds $2,500.00 mandatory review threshold."
                ),
                "requires_review": True,
            }
        ]

        final_report = {
            "conclusion": (
                "Confirmed third-party account takeover following SIM-swap OTP bypass "
                "([cite: ev_tx_10001], [cite: ev_dev_10001]) and high-risk merchant liquidation "
                "([cite: ev_merch_10001]). Recommend denying merchant representment and "
                "refunding cardholder."
            ),
            "recommendation": "deny",
            "confidence": 0.94,
            "hypotheses": iter2_hypotheses,
            "risk_factors": [
                "Unrecognized device 6,800km away with IP velocity 14",
                "OTP bypass during 9-transaction 24h velocity spike",
                "Merchant chargeback rate at 8.0% (risk score 0.61)",
            ],
            "evidence_ids": ["ev_tx_10001", "ev_cust_10001", "ev_dev_10001", "ev_merch_10001"],
            "unresolved_questions": [],
            "compliance_findings": ["CN-001: Mandatory human review completed"],
        }

        steering_guidance = (
            "Cross-reference merchant chargeback rate (8.0%) with the 6,800km device anomaly "
            "and rule out legitimate travel before finalizing."
        )

        timeline_sf1: list[dict[str, Any]] = [
            {
                "id": "evt_sf1_01_start",
                "type": "run_started",
                "timestamp": _iso(t0),
                "data": {"investigation_id": inv1_id, "dispute_id": sf1.id},
            },
            {
                "id": "evt_sf1_02_tool_tx",
                "type": "evidence_added",
                "timestamp": _iso(t0 + timedelta(seconds=2)),
                "data": ev_tx,
            },
            {
                "id": "evt_sf1_03_tool_cust",
                "type": "evidence_added",
                "timestamp": _iso(t0 + timedelta(seconds=3)),
                "data": ev_cust,
            },
            {
                "id": "evt_sf1_04_tool_dev",
                "type": "evidence_added",
                "timestamp": _iso(t0 + timedelta(seconds=4)),
                "data": ev_dev,
            },
            {
                "id": "evt_sf1_05_tool_merch",
                "type": "evidence_added",
                "timestamp": _iso(t0 + timedelta(seconds=5)),
                "data": ev_merch,
            },
            {
                "id": "evt_sf1_06_an_fraud",
                "type": "analyzer_completed",
                "timestamp": _iso(t0 + timedelta(seconds=6)),
                "data": {
                    **an_fraud,
                    "analyzer_id": "an_fraud_10001",
                    "analyzer_name": "fraud_pattern",
                },
            },
            {
                "id": "evt_sf1_07_an_dev",
                "type": "analyzer_completed",
                "timestamp": _iso(t0 + timedelta(seconds=7)),
                "data": {
                    **an_device,
                    "analyzer_id": "an_dev_10001",
                    "analyzer_name": "device_fingerprint",
                },
            },
            {
                "id": "evt_sf1_08_hyp_iter1",
                "type": "hypothesis_updated",
                "timestamp": _iso(t0 + timedelta(seconds=9)),
                "data": {
                    "iteration": 1,
                    "hypotheses": iter1_hypotheses,
                    "unresolved_questions": [
                        (
                            "Could the 6,800km IP distance be explained by legitimate "
                            "cardholder travel?"
                        ),
                        "Does the merchant's 8.0% chargeback rate indicate collusive liquidation?",
                    ],
                    "thought_process": (
                        "Evaluated initial telemetry in [cite: ev_tx_10001] and "
                        "[cite: ev_dev_10001]. Velocity (9 tx/24h) and OTP bypass strongly "
                        "suggest ATO, but merchant risk in [cite: ev_merch_10001] needs "
                        "human reviewer confirmation."
                    ),
                    "reasoning_steps": [
                        (
                            "Inspected transaction telemetry [cite: ev_tx_10001]: "
                            "$4,899.00 with OTP bypass."
                        ),
                        (
                            "Verified device context [cite: ev_dev_10001]: unrecognized "
                            "hardware 6,800km away."
                        ),
                        "Flagged unresolved travel vs. collusive merchant question for reviewer.",
                    ],
                },
            },
            {
                "id": "evt_sf1_09_risk_iter1",
                "type": "risk_updated",
                "timestamp": _iso(t0 + timedelta(seconds=11)),
                "data": risk_iter1,
            },
            {
                "id": "evt_sf1_10_steering_msg",
                "type": "agent_message",
                "timestamp": _iso(t0 + timedelta(seconds=15)),
                "data": {
                    "actor": "reviewer",
                    "stage": "investigate",
                    "message": (
                        "Reviewer requested re-investigation with targeted merchant & geo steering."
                    ),
                    "guidance": steering_guidance,
                },
            },
            {
                "id": "evt_sf1_11_hyp_iter2",
                "type": "hypothesis_updated",
                "timestamp": _iso(t0 + timedelta(seconds=19)),
                "data": {
                    "iteration": 2,
                    "hypotheses": iter2_hypotheses,
                    "unresolved_questions": [],
                    "thought_process": (
                        "Incorporated human reviewer steering: cross-referenced merchant 8.0% "
                        "chargeback rate in [cite: ev_merch_10001] with the 6,800km proxy burst "
                        "in [cite: ev_dev_10001] and prior SIM-swap alerts in "
                        "[cite: ev_cust_10001]. Ruled out legitimate travel and elevated ATO "
                        "confidence from 78% to 94%."
                    ),
                    "reasoning_steps": [
                        (
                            "Applied reviewer steering to correlate [cite: ev_merch_10001] "
                            "(8.0% chargeback rate) with [cite: ev_tx_10001]."
                        ),
                        (
                            "Ruled out cardholder travel hypothesis based on 14-IP proxy "
                            "rotation in [cite: ev_dev_10001]."
                        ),
                        (
                            "Upgraded ATO confidence to 0.94 and added collusive merchant "
                            "exposure hypothesis (0.89)."
                        ),
                    ],
                },
            },
            {
                "id": "evt_sf1_12_risk_iter2",
                "type": "risk_updated",
                "timestamp": _iso(t0 + timedelta(seconds=21)),
                "data": risk_iter2,
            },
            {
                "id": "evt_sf1_13_report",
                "type": "final_report_ready",
                "timestamp": _iso(t0 + timedelta(seconds=23)),
                "data": final_report,
            },
            {
                "id": "evt_sf1_14_completed",
                "type": "run_completed",
                "timestamp": _iso(t0 + timedelta(seconds=25)),
                "data": {"investigation_id": inv1_id, "report": final_report},
            },
        ]

        inv1 = InvestigationRecord(
            id=inv1_id,
            dispute_id=sf1.id,
            thread_id="thread_seed_sf_10001",
            status="completed",
            created_by=investigator_actor.user_id,
            checkpoint_id="ckpt_seed_sf_10001_v2",
            evidence=[ev_tx, ev_cust, ev_dev, ev_merch],
            analyzer_summaries=[an_fraud, an_device],
            hypotheses=iter2_hypotheses,
            unresolved_questions=[],
            risk_assessment=risk_iter2,
            compliance_findings=compliance_findings,
            report=final_report,
            timeline_events=timeline_sf1,
            iteration_count=2,
            tool_call_count=4,
            analyzer_call_count=2,
            created_at=t0,
            updated_at=t0 + timedelta(seconds=25),
        )
        sf1.status = "completed"
        session.add(inv1)
        await session.commit()

        sf1_audit_events: list[tuple[Principal, str, dict[str, Any]]] = [
            (
                investigator_actor,
                "investigation.started",
                {"investigation_id": inv1_id, "case_code": sf1.case_code, "status": "running"},
            ),
            (
                investigator_actor,
                "investigation.llm_iteration",
                {
                    "iteration": 1,
                    "hypothesis_count": 2,
                    "tool_requests": 4,
                    "analyzer_requests": 2,
                    "used_heuristic": False,
                    "model_used": "gpt-4.1-mini",
                },
            ),
            (
                reviewer_actor,
                "investigation.approval_recorded",
                {
                    "decision": "request_revision",
                    "comment": "Verify merchant chargeback velocity and rule out travel.",
                    "guidance": steering_guidance,
                    "risk_score": 0.76,
                },
            ),
            (
                investigator_actor,
                "investigation.llm_iteration",
                {
                    "iteration": 2,
                    "hypothesis_count": 2,
                    "tool_requests": 0,
                    "analyzer_requests": 0,
                    "used_heuristic": False,
                    "model_used": "gpt-4.1-mini",
                },
            ),
            (
                investigator_actor,
                "investigation.synthesis",
                {
                    "recommendation": "deny",
                    "confidence": 0.94,
                    "risk_score": 0.91,
                    "used_heuristic": False,
                    "model_used": "gpt-4.1-mini",
                },
            ),
        ]
        for actor, ev_name, payload in sf1_audit_events:
            await record_audit_event(
                session,
                actor=actor,
                event_name=ev_name,
                payload=payload,
                dispute_id=sf1.id,
                investigation_id=inv1_id,
            )

    # -------------------------------------------------------------------------
    # Showcase 2: SF-10002 — Paused Awaiting Human Approval Investigation
    # -------------------------------------------------------------------------
    sf2 = disputes_by_code.get("SF-10002") or disputes_by_code.get("SF-B")
    if sf2 is not None:
        inv2_id = "inv_seed_sf_10002"
        t2 = now - timedelta(minutes=6)
        ev2_tx = {
            "id": "ev_tx_10002",
            "source": "transactions",
            "category": "transaction",
            "origin": "observed_fact",
            "summary": "International airline & hotel booking ($2,200.00) with 3DS challenge pass.",
            "facts": {
                "transaction_id": "txn_sf_10002",
                "amount": 2200.0,
                "velocity_24h": 2,
                "geo_anomaly": True,
                "authorization_events": ["3ds_challenge"],
                "card_last4": "9014",
            },
            "confidence": 0.94,
            "collected_at": _iso(t2 + timedelta(seconds=2)),
            "provenance": "postgres://disputes/SF-10002/transactions",
        }
        ev2_cust = {
            "id": "ev_cust_10002",
            "source": "customer",
            "category": "customer",
            "origin": "observed_fact",
            "summary": "8-year loyal customer with zero prior disputes or fraud alerts.",
            "facts": {"prior_disputes": 0, "prior_fraud_signals": 0, "tenure_years": 8},
            "confidence": 0.96,
            "collected_at": _iso(t2 + timedelta(seconds=3)),
            "provenance": "postgres://disputes/SF-10002/customer",
        }
        ev2_dev = {
            "id": "ev_dev_10002",
            "source": "device",
            "category": "device",
            "origin": "observed_fact",
            "summary": "Unrecognized browser session 420km from home address (IP velocity: 3).",
            "facts": {"recognized_device": False, "ip_velocity": 3, "geo_distance_km": 420},
            "confidence": 0.89,
            "collected_at": _iso(t2 + timedelta(seconds=4)),
            "provenance": "postgres://disputes/SF-10002/device",
        }

        an2_fraud = {
            "analyzer": "fraud_pattern",
            "origin": "analyzer_interpretation",
            "summary": (
                "Borderline travel anomaly: strong 8-year tenure conflicts with unrecognized IP."
            ),
            "findings": [
                "3DS challenge succeeded during checkout",
                "Unrecognized browser session 420km away warrants human review",
            ],
            "confidence": 0.79,
            "evidence_ids": ["ev_tx_10002", "ev_cust_10002", "ev_dev_10002"],
            "contradictions": ["8-year clean customer history vs. unrecognized session IP"],
            "recommended_followups": ["Request human reviewer approval or steering guidance"],
        }

        hyp2 = [
            {
                "statement": (
                    "Ambiguous high-value travel booking requiring human reviewer sign-off"
                ),
                "confidence": 0.74,
                "supporting_evidence_ids": ["ev_tx_10002", "ev_dev_10002"],
                "contradicting_evidence_ids": ["ev_cust_10002"],
                "thought_process": (
                    "Transaction [cite: ev_tx_10002] passed 3DS challenge and customer profile "
                    "[cite: ev_cust_10002] shows 8 years of clean history, but unrecognized device "
                    "in [cite: ev_dev_10002] requires human-in-the-loop review before resolution."
                ),
            }
        ]

        risk2 = {
            "score": 0.58,
            "level": "medium",
            "explanation": (
                "Moderate risk (0.58): unrecognized session offset by 8-year customer tenure."
            ),
            "factors": [
                {
                    "name": "device_trust",
                    "weight": 0.18,
                    "value": 0.68,
                    "rationale": "Unrecognized browser session 420km from home region.",
                },
                {
                    "name": "customer_history",
                    "weight": 0.16,
                    "value": 0.15,
                    "rationale": "8-year tenure with 0 prior disputes lowers baseline risk.",
                },
            ],
        }

        report2 = {
            "conclusion": (
                "Conflicting signals between 8-year clean customer tenure ([cite: ev_cust_10002]) "
                "and unrecognized session 420km away ([cite: ev_dev_10002]) on a $2,200.00 booking "
                "([cite: ev_tx_10002]). Escalating for human reviewer decision."
            ),
            "recommendation": "escalate",
            "confidence": 0.74,
            "hypotheses": hyp2,
            "risk_factors": [
                "Unrecognized session at 420km distance",
                "High-value $2,200 travel booking",
            ],
            "evidence_ids": ["ev_tx_10002", "ev_cust_10002", "ev_dev_10002"],
            "unresolved_questions": ["Did cardholder authorize travel from secondary device?"],
            "compliance_findings": [],
        }

        timeline_sf2: list[dict[str, Any]] = [
            {
                "id": "evt_sf2_01_start",
                "type": "run_started",
                "timestamp": _iso(t2),
                "data": {"investigation_id": inv2_id, "dispute_id": sf2.id},
            },
            {
                "id": "evt_sf2_02_ev_tx",
                "type": "evidence_added",
                "timestamp": _iso(t2 + timedelta(seconds=2)),
                "data": ev2_tx,
            },
            {
                "id": "evt_sf2_03_ev_cust",
                "type": "evidence_added",
                "timestamp": _iso(t2 + timedelta(seconds=3)),
                "data": ev2_cust,
            },
            {
                "id": "evt_sf2_04_ev_dev",
                "type": "evidence_added",
                "timestamp": _iso(t2 + timedelta(seconds=4)),
                "data": ev2_dev,
            },
            {
                "id": "evt_sf2_05_an_fraud",
                "type": "analyzer_completed",
                "timestamp": _iso(t2 + timedelta(seconds=5)),
                "data": {
                    **an2_fraud,
                    "analyzer_id": "an_fraud_10002",
                    "analyzer_name": "fraud_pattern",
                },
            },
            {
                "id": "evt_sf2_06_hyp",
                "type": "hypothesis_updated",
                "timestamp": _iso(t2 + timedelta(seconds=7)),
                "data": {
                    "iteration": 1,
                    "hypotheses": hyp2,
                    "unresolved_questions": [
                        "Did cardholder authorize travel from secondary device?"
                    ],
                    "thought_process": (
                        "Evaluating [cite: ev_tx_10002], [cite: ev_cust_10002], and "
                        "[cite: ev_dev_10002]. Recommending human review due to conflicting "
                        "tenure vs. device signals."
                    ),
                    "reasoning_steps": [
                        (
                            "Checked transaction [cite: ev_tx_10002]: $2,200.00 booking "
                            "with 3DS challenge."
                        ),
                        (
                            "Compared customer tenure [cite: ev_cust_10002] (8 yrs) against "
                            "[cite: ev_dev_10002] (420km)."
                        ),
                        "Paused at LangGraph interrupt() for human reviewer decision.",
                    ],
                },
            },
            {
                "id": "evt_sf2_07_risk",
                "type": "risk_updated",
                "timestamp": _iso(t2 + timedelta(seconds=8)),
                "data": risk2,
            },
            {
                "id": "evt_sf2_08_report",
                "type": "final_report_ready",
                "timestamp": _iso(t2 + timedelta(seconds=9)),
                "data": report2,
            },
            {
                "id": f"approval_{inv2_id}",
                "type": "approval_required",
                "timestamp": _iso(t2 + timedelta(seconds=10)),
                "data": {
                    "investigation_id": inv2_id,
                    "report": report2,
                    "risk": risk2,
                    "evidence": [ev2_tx, ev2_cust, ev2_dev],
                    "analyzer_summaries": [an2_fraud],
                    "hypotheses": hyp2,
                },
            },
        ]

        inv2 = InvestigationRecord(
            id=inv2_id,
            dispute_id=sf2.id,
            thread_id="thread_seed_sf_10002",
            status="awaiting_approval",
            created_by=investigator_actor.user_id,
            checkpoint_id="ckpt_seed_sf_10002_v1",
            evidence=[ev2_tx, ev2_cust, ev2_dev],
            analyzer_summaries=[an2_fraud],
            hypotheses=hyp2,
            unresolved_questions=["Did cardholder authorize travel from secondary device?"],
            risk_assessment=risk2,
            compliance_findings=[],
            report=report2,
            timeline_events=timeline_sf2,
            iteration_count=1,
            tool_call_count=3,
            analyzer_call_count=1,
            created_at=t2,
            updated_at=t2 + timedelta(seconds=10),
        )
        sf2.status = "under_review"
        session.add(inv2)
        await session.commit()

        sf2_audit_events: list[tuple[Principal, str, dict[str, Any]]] = [
            (
                investigator_actor,
                "investigation.started",
                {"investigation_id": inv2_id, "case_code": sf2.case_code, "status": "running"},
            ),
            (
                investigator_actor,
                "investigation.llm_iteration",
                {
                    "iteration": 1,
                    "hypothesis_count": 1,
                    "tool_requests": 3,
                    "analyzer_requests": 1,
                    "used_heuristic": False,
                    "model_used": "gpt-4.1-mini",
                },
            ),
            (
                investigator_actor,
                "investigation.synthesis",
                {
                    "recommendation": "escalate",
                    "confidence": 0.74,
                    "risk_score": 0.58,
                    "used_heuristic": False,
                    "model_used": "gpt-4.1-mini",
                },
            ),
        ]
        for actor, ev_name, payload in sf2_audit_events:
            await record_audit_event(
                session,
                actor=actor,
                event_name=ev_name,
                payload=payload,
                dispute_id=sf2.id,
                investigation_id=inv2_id,
            )


async def seed_session(session: AsyncSession) -> None:
    existing = await session.execute(select(DisputeRecord))
    existing_records = list(existing.scalars())
    disputes_by_code: dict[str, DisputeRecord] = {r.case_code: r for r in existing_records}

    base_time = datetime.now(UTC)
    for idx, case in enumerate(CASES):
        if case["case_code"] in disputes_by_code:
            continue
        record = DisputeRecord(
            id=str(uuid4()),
            case_code=case["case_code"],
            title=case["title"],
            narrative=case["narrative"],
            customer_id=case["customer_id"],
            merchant_id=case["merchant_id"],
            amount=case["amount"],
            currency="USD",
            status=case["status"],
            attributes=case["attributes"],
            created_at=base_time - timedelta(minutes=idx + 1),
        )
        session.add(record)
        disputes_by_code[case["case_code"]] = record

    await session.commit()
    await _seed_showcase_investigations(session, disputes_by_code)


async def seed() -> None:
    async with SessionLocal() as session:
        await seed_session(session)


if __name__ == "__main__":
    asyncio.run(seed())
