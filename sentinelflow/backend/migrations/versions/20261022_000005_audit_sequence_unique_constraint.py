"""Add unique constraint to audit_records (investigation_id, sequence_no).

Revision ID: 20261022_000005
Revises: 20260902_000004
Create Date: 2026-10-22 00:00:05
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261022_000005"
down_revision = "20260902_000004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_unique_constraint(
        "uq_audit_records_investigation_sequence",
        "audit_records",
        ["investigation_id", "sequence_no"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "uq_audit_records_investigation_sequence",
        "audit_records",
        type_="unique",
    )
