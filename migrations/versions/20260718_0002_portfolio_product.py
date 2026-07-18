"""Phase 5 portfolio product tables: current-book state and watchlists.

Revision ID: 20260718_0002
Revises: 20260718_0001
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0002"
down_revision: str | None = "20260718_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "workspace_portfolio_state",
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("current_snapshot_id", sa.String(length=64), nullable=True),
        sa.Column("monitoring_enabled", sa.String(length=8), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("workspace_id"),
    )
    op.create_table(
        "watchlists",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("workspace_id", "id", name="uq_watchlists_workspace_id"),
    )
    op.create_index(
        "ix_watchlists_workspace_name",
        "watchlists",
        ["workspace_id", "name"],
    )


def downgrade() -> None:
    op.drop_index("ix_watchlists_workspace_name", table_name="watchlists")
    op.drop_table("watchlists")
    op.drop_table("workspace_portfolio_state")
