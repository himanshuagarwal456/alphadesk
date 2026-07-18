"""Deterministic comparison of consecutive thesis snapshots."""

from __future__ import annotations

from pydantic import BaseModel

from .schemas import ThesisSnapshot

_RATINGS = {"Sell": 0, "Underweight": 1, "Hold": 2, "Overweight": 3, "Buy": 4}


class ThesisDiff(BaseModel):
    symbol: str
    prior_snapshot_id: str
    current_snapshot_id: str
    rating_delta: int
    rating_downgraded: bool
    evidence_added: list[str]
    evidence_removed: list[str]
    headline: str
    materiality_score: float


def diff_or_none(prior: ThesisSnapshot | None, current: ThesisSnapshot) -> ThesisDiff | None:
    return diff_snapshots(prior, current) if prior else None


def diff_snapshots(prior: ThesisSnapshot, current: ThesisSnapshot) -> ThesisDiff:
    """Produce a stable diff suitable for display and trigger evaluation."""
    delta = _RATINGS[current.rating.value] - _RATINGS[prior.rating.value]
    added = sorted(set(current.evidence_ids) - set(prior.evidence_ids))
    removed = sorted(set(prior.evidence_ids) - set(current.evidence_ids))
    if delta < 0:
        headline = f"Rating downgraded: {prior.rating.value} → {current.rating.value}"
    elif delta > 0:
        headline = f"Rating upgraded: {prior.rating.value} → {current.rating.value}"
    elif current.price_target != prior.price_target:
        headline = f"Price target changed: {prior.price_target} → {current.price_target}"
    else:
        headline = f"Thesis updated; {len(added)} new evidence items"
    materiality = min(1.0, 0.35 * abs(delta) + 0.1 * (len(added) + len(removed)))
    return ThesisDiff(
        symbol=current.symbol,
        prior_snapshot_id=prior.snapshot_id,
        current_snapshot_id=current.snapshot_id,
        rating_delta=delta,
        rating_downgraded=delta < 0,
        evidence_added=added,
        evidence_removed=removed,
        headline=headline,
        materiality_score=round(materiality, 4),
    )
