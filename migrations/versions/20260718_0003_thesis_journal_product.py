"""Phase 6 thesis proposals and outcome reviews.

Revision ID: 20260718_0003
Revises: 20260718_0002
Create Date: 2026-07-18
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260718_0003"
down_revision: str | None = "20260718_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "thesis_proposals",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_thesis_proposals_workspace_id"
        ),
    )
    op.create_index(
        "ix_thesis_proposals_symbol_status",
        "thesis_proposals",
        ["workspace_id", "symbol", "status"],
    )
    op.create_table(
        "outcome_reviews",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("journal_entry_id", sa.String(length=64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint(
            "workspace_id", "id", name="uq_outcome_reviews_workspace_id"
        ),
    )
    op.create_index(
        "ix_outcome_reviews_entry",
        "outcome_reviews",
        ["workspace_id", "journal_entry_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_outcome_reviews_entry", table_name="outcome_reviews")
    op.drop_table("outcome_reviews")
    op.drop_index("ix_thesis_proposals_symbol_status", table_name="thesis_proposals")
    op.drop_table("thesis_proposals")
