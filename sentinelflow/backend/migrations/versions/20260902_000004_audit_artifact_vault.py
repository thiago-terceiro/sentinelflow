"""Add encrypted audit artifact vault table.

Revision ID: 20260902_000004
Revises: 20260902_000003
Create Date: 2026-09-02 00:00:04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260902_000004"
down_revision = "20260902_000003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_artifacts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("audit_record_id", sa.String(length=36), nullable=False),
        sa.Column("investigation_id", sa.String(length=36), nullable=True),
        sa.Column("dispute_id", sa.String(length=36), nullable=True),
        sa.Column("key_id", sa.String(length=64), nullable=False),
        sa.Column("ciphertext", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["audit_record_id"], ["audit_records.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("audit_record_id"),
    )
    op.create_index("ix_audit_artifacts_audit_record_id", "audit_artifacts", ["audit_record_id"], unique=True)
    op.create_index("ix_audit_artifacts_investigation_id", "audit_artifacts", ["investigation_id"], unique=False)
    op.create_index("ix_audit_artifacts_dispute_id", "audit_artifacts", ["dispute_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_audit_artifacts_dispute_id", table_name="audit_artifacts")
    op.drop_index("ix_audit_artifacts_investigation_id", table_name="audit_artifacts")
    op.drop_index("ix_audit_artifacts_audit_record_id", table_name="audit_artifacts")
    op.drop_table("audit_artifacts")
