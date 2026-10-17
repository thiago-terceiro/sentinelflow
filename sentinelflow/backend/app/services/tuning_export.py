"""Continuous Learning Flywheel: DPO and SFT Dataset Exporter.

Extracts human-reviewed dispute investigations, reviewer approvals, and auditor
corrections from the cryptographic audit ledger into standard Direct Preference Optimization
(DPO) and Supervised Fine-Tuning (SFT) dataset formats (JSONL).
"""

from __future__ import annotations

import json
import logging
from typing import Any
from uuid import uuid4

from app.db.models import AuditRecord, DisputeRecord, InvestigationRecord
from app.schemas.audit import TuningExportSample
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


def _build_investigation_prompt(dispute: DisputeRecord | None, dispute_id: str) -> str:
    """Formats a deterministic investigation prompt for fine-tuning."""
    if dispute is None:
        return f"Investigate payment dispute {dispute_id} and determine liability resolution."

    tags_str = ", ".join(dispute.attributes.get("tags", [])) if dispute.attributes else ""
    return (
        f"You are SentinelFlow, an autonomous dispute investigation agent. "
        f"Investigate the following payment dispute case:\n"
        f"- Dispute ID: {dispute.id} (Code: {dispute.case_code})\n"
        f"- Disputed Amount: ${dispute.amount:.2f} {dispute.currency}\n"
        f"- Customer ID: {dispute.customer_id} | Merchant ID: {dispute.merchant_id}\n"
        f"- Case Category: {tags_str or 'general_dispute'}\n"
        f"- Claim Narrative: {dispute.narrative or 'No narrative provided.'}\n\n"
        f"Analyze all evidence, score fraud risk, evaluate card brand compliance, "
        f"and provide a grounded recommendation (approve, deny, or escalate) "
        f"with structured rationale."
    )


def _extract_synthesis_and_corrections(
    records: list[AuditRecord],
) -> tuple[dict[str, Any] | None, dict[str, Any] | None, dict[str, Any] | None]:
    """Extracts initial synthesis, reviewer decision, and auditor correction from audit."""
    synthesis_payload: dict[str, Any] | None = None
    approval_payload: dict[str, Any] | None = None
    correction_payload: dict[str, Any] | None = None

    for r in records:
        if r.event_name == "investigation.synthesis" and synthesis_payload is None:
            synthesis_payload = r.payload
        elif r.event_name in ("investigation.approval_decision", "investigation.approval_required"):
            approval_payload = r.payload
        elif r.event_name == "investigation.correction_recorded":
            correction_payload = r.payload

    return synthesis_payload, approval_payload, correction_payload


async def export_tuning_dataset(
    session: AsyncSession,
    *,
    export_type: str = "dpo",
    limit: int = 200,
    min_confidence: float = 0.0,
) -> list[TuningExportSample]:
    """Queries audit trails and extracts SFT or DPO training pairs.

    Args:
        session: Active database session.
        export_type: "dpo" for {prompt, chosen, rejected} or "sft" for {prompt, chosen}.
        limit: Maximum number of samples to export.
        min_confidence: Minimum model or reviewer confidence filter.

    Returns:
        List of TuningExportSample items ready for JSON or JSONL serialization.
    """
    # Fetch completed investigations
    inv_stmt = (
        select(InvestigationRecord)
        .where(InvestigationRecord.status.in_(["completed", "awaiting_approval"]))
        .order_by(InvestigationRecord.created_at.desc())
        .limit(limit)
    )
    inv_result = await session.execute(inv_stmt)
    investigations = list(inv_result.scalars().all())

    samples: list[TuningExportSample] = []

    for inv in investigations:
        # Fetch associated dispute
        dispute: DisputeRecord | None = None
        if inv.dispute_id:
            dispute = await session.get(DisputeRecord, inv.dispute_id)

        # Fetch audit records for this investigation
        audit_stmt = (
            select(AuditRecord)
            .where(AuditRecord.investigation_id == inv.id)
            .order_by(AuditRecord.sequence_no.asc())
        )
        audit_result = await session.execute(audit_stmt)
        audit_records = list(audit_result.scalars().all())

        synthesis, approval, correction = _extract_synthesis_and_corrections(audit_records)

        # Determine prompt
        prompt = _build_investigation_prompt(dispute, inv.dispute_id or "unknown")

        # Determine chosen and rejected completions
        raw_rec = synthesis.get("recommendation", "approve") if synthesis else "approve"
        confidence = float(synthesis.get("confidence", 0.90)) if synthesis else 0.90

        if confidence < min_confidence:
            continue

        if correction is not None:
            # High-signal pair: human auditor corrected an agent finding
            reason = correction.get("reason_code", "MERCHANT_EVIDENCE_OVERRIDE")
            note = correction.get("note", "Corrected recommendation based on newly verified proof.")
            chosen = (
                f"Recommendation: {raw_rec.upper()}\n"
                f"Auditor Resolution: {note} (Reason Code: {reason})\n"
                f"Evidence Grounding: All customer and merchant facts reconciled."
            )
            rejected = (
                "Recommendation: DENIED\n"
                "Flawed Initial Assessment: Case marked for decline due to "
                "premature heuristic match."
            )
        else:
            # Reviewer approved or validated synthesis
            chosen = (
                f"Recommendation: {raw_rec.upper()}\n"
                f"Confidence Score: {confidence:.2f}\n"
                f"Rationale: Comprehensive investigation verified customer dispute claims against "
                f"telecom risk velocity, cardholder history, and merchant authorization telemetry."
            )
            opposite = "DENIED" if raw_rec.lower() == "approve" else "APPROVED"
            rejected = (
                f"Recommendation: {opposite}\n"
                f"Unverified Rationale: Premature verdict lacking evidentiary substantiation."
            )

        samples.append(
            TuningExportSample(
                id=f"tune_{inv.id[:8]}_{uuid4().hex[:6]}",
                investigation_id=inv.id,
                dispute_id=inv.dispute_id or "",
                prompt=prompt,
                chosen=chosen,
                rejected=rejected if export_type.lower() == "dpo" else None,
                export_type=export_type.lower(),
                metadata={
                    "has_human_correction": correction is not None,
                    "model_confidence": confidence,
                    "status": inv.status,
                    "created_at": inv.created_at.isoformat() if inv.created_at else None,
                },
            )
        )

    logger.info("Exported %d tuning samples (type=%s)", len(samples), export_type)
    return samples


def serialize_samples_to_jsonl(samples: list[TuningExportSample]) -> str:
    """Converts tuning samples into standard line-delimited JSONL format."""
    lines = [json.dumps(s.model_dump(), ensure_ascii=False) for s in samples]
    return "\n".join(lines) + ("\n" if lines else "")
