"""Add timeline_events column to investigations.

Revision ID: 20260828_000002
Revises: 20260826_000001
Create Date: 2026-08-28 00:00:02
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260828_000002"
down_revision = "20260826_000001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column("timeline_events", sa.JSON(), nullable=True, server_default="[]"),
    )


def downgrade() -> None:
    op.drop_column("investigations", "timeline_events")
