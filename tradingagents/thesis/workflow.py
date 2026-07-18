"""Thesis workflows: create from a saved run, and human-reviewed revisions.

Two product rules from the alpha brief (Journey 3) are enforced here:

1. **A thesis can be created from an existing completed research run** without
   re-running the graph, using the run's canonical structured decision when
   present and degrading to the rendered markdown only for legacy runs.
2. **No thesis is silently overwritten.** A change arrives as a
   ``ProposedRevision`` (authored by AI or the user); it only becomes the
   current thesis when accepted, optionally after edits. Rejected proposals
   stay in the audit history.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256
from typing import Any

from pydantic import BaseModel, Field

from tradingagents.agents.schemas import PortfolioDecision
from tradingagents.agents.utils.rating import parse_rating

from .schemas import LivingThesis, ThesisSnapshot, build_thesis_update
from .store import LivingThesisStore


def decision_from_run(run: dict[str, Any]) -> PortfolioDecision:
    """Recover the Portfolio Manager decision from a saved run.

    Prefers the canonical ``portfolio_decision_struct``; for legacy runs the
    rating is parsed from the rendered markdown and the prose becomes the
    thesis text.
    """
    structured = run.get("portfolio_decision_struct")
    if structured:
        return PortfolioDecision.model_validate(structured)
    verdict = run.get("final_trade_decision", "") or ""
    if not verdict:
        raise ValueError("run has no final trade decision to build a thesis from")
    return PortfolioDecision(
        rating=parse_rating(verdict),
        executive_summary=verdict.split("\n", 1)[0][:500],
        investment_thesis=verdict,
    )


def create_thesis_from_run(
    run: dict[str, Any],
    store: LivingThesisStore,
    *,
    stance: str = "",
) -> tuple[ThesisSnapshot, LivingThesis]:
    """Create or extend a symbol's living thesis from one saved run."""
    symbol = (run.get("company_of_interest") or "").upper()
    trade_date = run.get("trade_date", "")
    if not symbol or not trade_date:
        raise ValueError("run must carry company_of_interest and trade_date")
    decision = decision_from_run(run)
    evidence_ids = run.get("evidence_ids") or [
        item.get("id") for item in run.get("evidence", []) if isinstance(item, dict)
    ]
    snapshot, thesis = build_thesis_update(
        symbol=symbol,
        trade_date=trade_date,
        stance=stance,
        decision=decision,
        evidence_ids=[item for item in evidence_ids if item],
        prior=store.load(symbol),
        catalysts=decision.catalysts,
        invalidation_conditions=decision.invalidation_conditions,
        invalidation_triggered=decision.invalidation_triggered,
    )
    store.upsert_run(thesis, snapshot)
    return snapshot, thesis


class RevisionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ProposedRevision(BaseModel):
    """A thesis change awaiting human review; immutable once reviewed."""

    id: str | None = None
    symbol: str
    author: str = Field(default="ai", description="'ai' or 'user'.")
    reason: str
    snapshot: ThesisSnapshot
    status: RevisionStatus = RevisionStatus.PROPOSED
    review_note: str = ""
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    reviewed_at: datetime | None = None

    def model_post_init(self, __context) -> None:
        if self.id is None:
            digest = sha256(
                f"{self.symbol}|{self.snapshot.snapshot_id}|{self.created_at.isoformat()}".encode()
            ).hexdigest()[:20]
            self.id = f"pr_{digest}"


def propose_revision(
    store: LivingThesisStore,
    snapshot: ThesisSnapshot,
    *,
    reason: str,
    author: str = "ai",
) -> ProposedRevision:
    """Record a proposed thesis change without touching the current thesis."""
    proposal = ProposedRevision(
        symbol=snapshot.symbol, author=author, reason=reason, snapshot=snapshot
    )
    store.save_proposal(proposal)
    return proposal


def review_revision(
    store: LivingThesisStore,
    proposal: ProposedRevision,
    *,
    accept: bool,
    edited_snapshot: ThesisSnapshot | None = None,
    note: str = "",
) -> ProposedRevision:
    """Accept (optionally with user edits) or reject a proposed revision.

    Acceptance applies the snapshot to the living thesis via the normal
    revision chain; rejection changes nothing but is kept for audit.
    """
    if proposal.status is not RevisionStatus.PROPOSED:
        raise ValueError(f"proposal {proposal.id} was already reviewed")
    reviewed = proposal.model_copy(update={
        "status": RevisionStatus.ACCEPTED if accept else RevisionStatus.REJECTED,
        "snapshot": edited_snapshot if (accept and edited_snapshot) else proposal.snapshot,
        "review_note": note,
        "reviewed_at": datetime.now(timezone.utc),
    })
    store.save_proposal(reviewed)
    if accept:
        snapshot = reviewed.snapshot
        prior = store.load(snapshot.symbol)
        if prior is None or prior.current_snapshot_id != snapshot.prior_snapshot_id:
            # Rebase onto the actual current head so an out-of-date proposal
            # cannot silently drop intervening revisions.
            snapshot = snapshot.model_copy(update={
                "prior_snapshot_id": prior.current_snapshot_id if prior else None,
            })
        from .schemas import ConfidencePoint  # local to avoid cycle at import

        point = ConfidencePoint(as_of=snapshot.as_of, rating=snapshot.rating)
        if prior is None:
            thesis = LivingThesis(
                symbol=snapshot.symbol,
                status=snapshot.status,
                current_snapshot_id=snapshot.snapshot_id,
                opened_at=snapshot.as_of,
                updated_at=snapshot.as_of,
                snapshot_ids=[snapshot.snapshot_id],
                confidence_history=[point],
                current=snapshot,
            )
        else:
            thesis = prior.model_copy(update={
                "status": snapshot.status,
                "current_snapshot_id": snapshot.snapshot_id,
                "updated_at": snapshot.as_of,
                "snapshot_ids": [*prior.snapshot_ids, snapshot.snapshot_id],
                "confidence_history": [*prior.confidence_history, point],
                "current": snapshot,
            })
        store.upsert_run(thesis, snapshot)
    return reviewed
