"""Add composite index ix_investigations_dispute_created_at on investigations.

Revision ID: 20261022_000006
Revises: 20261022_000005
Create Date: 2026-10-22 00:00:06
"""

from __future__ import annotations

from alembic import op

# revision identifiers, used by Alembic.
revision = "20261022_000006"
down_revision = "20261022_000005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_investigations_dispute_created_at",
        "investigations",
        ["dispute_id", "created_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_investigations_dispute_created_at", table_name="investigations")
