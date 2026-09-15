"""Add audit integrity columns and investigation failure reason.

Revision ID: 20260902_000003
Revises: 20260828_000002
Create Date: 2026-09-02 00:00:03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "20260902_000003"
down_revision = "20260828_000002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column("failure_reason", sa.String(length=512), nullable=True),
    )
    op.add_column(
        "audit_records",
        sa.Column("sequence_no", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "audit_records",
        sa.Column("prev_hash", sa.String(length=64), nullable=True),
    )
    op.add_column(
        "audit_records",
        sa.Column("row_hash", sa.String(length=64), nullable=True),
    )
    op.create_index(
        "ix_audit_records_investigation_sequence",
        "audit_records",
        ["investigation_id", "sequence_no"],
        unique=False,
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sentinelflow_app') THEN
                EXECUTE 'GRANT SELECT, INSERT ON TABLE audit_records TO sentinelflow_app';
                EXECUTE 'REVOKE UPDATE, DELETE ON TABLE audit_records FROM sentinelflow_app';
            END IF;
        END $$;
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'sentinelflow_app') THEN
                EXECUTE 'GRANT UPDATE, DELETE ON TABLE audit_records TO sentinelflow_app';
            END IF;
        END $$;
        """
    )
    op.drop_index("ix_audit_records_investigation_sequence", table_name="audit_records")
    op.drop_column("audit_records", "row_hash")
    op.drop_column("audit_records", "prev_hash")
    op.drop_column("audit_records", "sequence_no")
    op.drop_column("investigations", "failure_reason")
