"""Knowledge catalog tables for Learn More.

Revision ID: 20260721_0005
Revises: 20260718_0004
Create Date: 2026-07-21
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260721_0005"
down_revision: str | None = "20260718_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_concepts",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("slug", sa.String(length=128), nullable=False),
        sa.Column("title", sa.String(length=256), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_knowledge_concepts_slug"),
    )
    op.create_table(
        "knowledge_resources",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("id", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("provider", sa.String(length=128), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint("id"),
    )
    op.create_table(
        "knowledge_concept_resources",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("concept_id", sa.String(length=64), nullable=False),
        sa.Column("resource_id", sa.String(length=64), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint(
            "concept_id", "resource_id", name="uq_knowledge_concept_resources"
        ),
    )
    op.create_table(
        "intelligence_card_concepts",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("intelligence_card_id", sa.String(length=64), nullable=False),
        sa.Column("concept_id", sa.String(length=64), nullable=False),
        sa.Column("relevance_score", sa.Float(), nullable=False),
        sa.Column("context_reason", sa.Text(), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint(
            "intelligence_card_id",
            "concept_id",
            name="uq_intelligence_card_concepts",
        ),
    )
    op.create_index(
        "ix_card_concepts_card",
        "intelligence_card_concepts",
        ["intelligence_card_id"],
    )
    op.create_table(
        "user_concept_progress",
        sa.Column("pk", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.String(length=64), nullable=False),
        sa.Column("concept_id", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("saved", sa.String(length=8), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("pk"),
        sa.UniqueConstraint(
            "user_id", "concept_id", name="uq_user_concept_progress"
        ),
    )


def downgrade() -> None:
    op.drop_table("user_concept_progress")
    op.drop_index("ix_card_concepts_card", table_name="intelligence_card_concepts")
    op.drop_table("intelligence_card_concepts")
    op.drop_table("knowledge_concept_resources")
    op.drop_table("knowledge_resources")
    op.drop_table("knowledge_concepts")
