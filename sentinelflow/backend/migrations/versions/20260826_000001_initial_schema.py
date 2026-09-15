"""Initial SentinelFlow schema.

Revision ID: 20260826_000001
Revises:
Create Date: 2026-08-26 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260826_000001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_records",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
        sa.Column("dispute_id", sa.String(length=36), nullable=True),
        sa.Column("actor_id", sa.String(length=64), nullable=False),
        sa.Column("actor_role", sa.String(length=64), nullable=False),
        sa.Column("event_name", sa.String(length=128), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_audit_records_dispute_id"), "audit_records", ["dispute_id"], unique=False)
    op.create_index(op.f("ix_audit_records_event_name"), "audit_records", ["event_name"], unique=False)
    op.create_index(
        op.f("ix_audit_records_investigation_id"),
        "audit_records",
        ["investigation_id"],
        unique=False,
    )

    op.create_table(
        "disputes",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("case_code", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("narrative", sa.Text(), nullable=False),
        sa.Column("customer_id", sa.String(length=64), nullable=False),
        sa.Column("merchant_id", sa.String(length=64), nullable=False),
        sa.Column("amount", sa.Float(), nullable=False),
        sa.Column("currency", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("attributes", sa.JSON(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_disputes_case_code"), "disputes", ["case_code"], unique=True)
    op.create_index(op.f("ix_disputes_customer_id"), "disputes", ["customer_id"], unique=False)
    op.create_index(op.f("ix_disputes_merchant_id"), "disputes", ["merchant_id"], unique=False)

    op.create_table(
        "investigations",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("dispute_id", sa.String(length=36), nullable=False),
        sa.Column("thread_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("evidence", sa.JSON(), nullable=False),
        sa.Column("analyzer_summaries", sa.JSON(), nullable=False),
        sa.Column("hypotheses", sa.JSON(), nullable=False),
        sa.Column("unresolved_questions", sa.JSON(), nullable=False),
        sa.Column("risk_assessment", sa.JSON(), nullable=True),
        sa.Column("compliance_findings", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=True),
        sa.Column("iteration_count", sa.Integer(), nullable=False),
        sa.Column("tool_call_count", sa.Integer(), nullable=False),
        sa.Column("analyzer_call_count", sa.Integer(), nullable=False),
        sa.Column("checkpoint_id", sa.String(length=128), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["dispute_id"], ["disputes.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_investigations_dispute_id"), "investigations", ["dispute_id"], unique=False)
    op.create_index(op.f("ix_investigations_thread_id"), "investigations", ["thread_id"], unique=True)


def downgrade() -> None:
    op.drop_index(op.f("ix_investigations_thread_id"), table_name="investigations")
    op.drop_index(op.f("ix_investigations_dispute_id"), table_name="investigations")
    op.drop_table("investigations")

    op.drop_index(op.f("ix_disputes_merchant_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_customer_id"), table_name="disputes")
    op.drop_index(op.f("ix_disputes_case_code"), table_name="disputes")
    op.drop_table("disputes")

    op.drop_index(op.f("ix_audit_records_investigation_id"), table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_event_name"), table_name="audit_records")
    op.drop_index(op.f("ix_audit_records_dispute_id"), table_name="audit_records")
    op.drop_table("audit_records")