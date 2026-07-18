"""Durable, evidence-linked investment-thesis models."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating


class ThesisStatus(str, Enum):
    ACTIVE = "active"
    WEAKENED = "weakened"
    INVALIDATED = "invalidated"
    CLOSED = "closed"


class Catalyst(BaseModel):
    description: str
    expected_by: str | None = None


class InvalidationCondition(BaseModel):
    description: str
    triggered: bool = False


class ConfidencePoint(BaseModel):
    as_of: str
    rating: PortfolioRating


class ThesisSnapshot(BaseModel):
    snapshot_id: str
    symbol: str
    as_of: str
    stance: str = ""
    rating: PortfolioRating
    executive_summary: str
    investment_thesis: str
    price_target: float | None = None
    time_horizon: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    catalysts: list[Catalyst] = Field(default_factory=list)
    invalidation_conditions: list[InvalidationCondition] = Field(default_factory=list)
    status: ThesisStatus = ThesisStatus.ACTIVE
    prior_snapshot_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class LivingThesis(BaseModel):
    symbol: str
    status: ThesisStatus
    current_snapshot_id: str
    opened_at: str
    updated_at: str
    snapshot_ids: list[str]
    confidence_history: list[ConfidencePoint]
    current: ThesisSnapshot


def build_thesis_update(
    *,
    symbol: str,
    trade_date: str,
    stance: str,
    decision: PortfolioDecision,
    evidence_ids: list[str],
    prior: LivingThesis | None,
) -> tuple[ThesisSnapshot, LivingThesis]:
    """Build a dated revision and update the per-symbol thesis head."""
    normalized_symbol = symbol.strip().upper()
    status = _status_for(decision.rating, stance, prior)
    snapshot = ThesisSnapshot(
        snapshot_id=f"th_{normalized_symbol}_{trade_date}",
        symbol=normalized_symbol,
        as_of=trade_date,
        stance=stance,
        rating=decision.rating,
        executive_summary=decision.executive_summary,
        investment_thesis=decision.investment_thesis,
        price_target=decision.price_target,
        time_horizon=decision.time_horizon,
        evidence_ids=sorted(set(evidence_ids)),
        status=status,
        prior_snapshot_id=prior.current_snapshot_id if prior else None,
    )
    point = ConfidencePoint(as_of=trade_date, rating=decision.rating)
    if prior is None:
        return snapshot, LivingThesis(
            symbol=normalized_symbol,
            status=status,
            current_snapshot_id=snapshot.snapshot_id,
            opened_at=trade_date,
            updated_at=trade_date,
            snapshot_ids=[snapshot.snapshot_id],
            confidence_history=[point],
            current=snapshot,
        )
    return snapshot, prior.model_copy(update={
        "status": status,
        "current_snapshot_id": snapshot.snapshot_id,
        "updated_at": trade_date,
        "snapshot_ids": [*prior.snapshot_ids, snapshot.snapshot_id],
        "confidence_history": [*prior.confidence_history, point],
        "current": snapshot,
    })


def _status_for(
    rating: PortfolioRating, stance: str, prior: LivingThesis | None
) -> ThesisStatus:
    if stance == "manage" and rating.value in {"Sell", "Underweight"}:
        return ThesisStatus.CLOSED
    if prior and rating.value in {"Hold", "Underweight", "Sell"}:
        return ThesisStatus.WEAKENED
    return ThesisStatus.ACTIVE
