"""Factor intelligence Batch 1 tables.

Revision ID: 20260721_0007
Revises: 20260721_0006
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0007"
down_revision: str | None = "20260721_0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "factor_definitions",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("code", name="uq_factor_definitions_code"),
    )
    op.create_table(
        "factor_model_versions",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("effective_date", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("id"),
    )
    op.create_table(
        "security_factor_exposures",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=160), nullable=False),
        sa.Column("model_version_id", sa.String(length=64), nullable=False),
        sa.Column("symbol", sa.String(length=32), nullable=False),
        sa.Column("factor_code", sa.String(length=64), nullable=False),
        sa.Column("effective_date", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_sec_factor_exp_lookup",
        "security_factor_exposures",
        ["model_version_id", "symbol", "effective_date"],
    )
    op.create_table(
        "portfolio_factor_exposures",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=220), nullable=False),
        sa.Column("workspace_id", sa.String(length=64), nullable=False),
        sa.Column("portfolio_id", sa.String(length=64), nullable=False),
        sa.Column("model_version_id", sa.String(length=64), nullable=False),
        sa.Column("factor_code", sa.String(length=64), nullable=False),
        sa.Column("effective_date", sa.String(length=16), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["workspace_id"], ["workspaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("id"),
    )
    op.create_index(
        "ix_pf_factor_exp_lookup",
        "portfolio_factor_exposures",
        ["workspace_id", "portfolio_id", "effective_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_pf_factor_exp_lookup", table_name="portfolio_factor_exposures")
    op.drop_table("portfolio_factor_exposures")
    op.drop_index("ix_sec_factor_exp_lookup", table_name="security_factor_exposures")
    op.drop_table("security_factor_exposures")
    op.drop_table("factor_model_versions")
    op.drop_table("factor_definitions")
