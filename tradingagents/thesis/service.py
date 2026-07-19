"""Workspace-scoped thesis workflows (DB-backed Phase 6 product path).

Mirrors :mod:`tradingagents.thesis.workflow` but persists through
``ThesisRepository`` instead of the local JSON file store. AI cannot apply a
revision without an explicit accept (optionally with user edits).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from tradingagents.persistence.repositories.runs import AnalysisRunRepository
from tradingagents.persistence.repositories.theses import ThesisRepository
from tradingagents.thesis.diff import ThesisDiff, diff_snapshots
from tradingagents.thesis.schemas import (
    ConfidencePoint,
    LivingThesis,
    ThesisSnapshot,
    build_thesis_update,
)
from tradingagents.thesis.workflow import (
    ProposedRevision,
    RevisionStatus,
    decision_from_run,
)


class ThesisWorkflowService:
    def __init__(self, session: Session, *, workspace_id: str):
        self._session = session
        self._workspace_id = workspace_id
        self._theses = ThesisRepository(session)
        self._runs = AnalysisRunRepository(session)

    def list_snapshots(self, symbol: str) -> list[ThesisSnapshot]:
        return self._theses.list_snapshots(self._workspace_id, symbol)

    def compare(
        self,
        symbol: str,
        *,
        prior_snapshot_id: str,
        current_snapshot_id: str,
    ) -> ThesisDiff:
        prior = self._theses.get_snapshot(self._workspace_id, prior_snapshot_id)
        current = self._theses.get_snapshot(self._workspace_id, current_snapshot_id)
        if prior is None or current is None:
            raise KeyError("snapshot not found")
        if prior.symbol != symbol.upper() or current.symbol != symbol.upper():
            raise ValueError("snapshot symbol mismatch")
        return diff_snapshots(prior, current)

    def propose(
        self,
        snapshot: ThesisSnapshot,
        *,
        reason: str,
        author: str = "ai",
    ) -> ProposedRevision:
        proposal = ProposedRevision(
            symbol=snapshot.symbol,
            author=author,
            reason=reason,
            snapshot=snapshot,
        )
        return self._theses.save_proposal(proposal, workspace_id=self._workspace_id)

    def list_proposals(
        self,
        symbol: str,
        *,
        status: RevisionStatus | None = None,
    ) -> list[ProposedRevision]:
        return self._theses.list_proposals(
            self._workspace_id, symbol, status=status
        )

    def get_proposal(self, proposal_id: str) -> ProposedRevision | None:
        return self._theses.get_proposal(self._workspace_id, proposal_id)

    def review(
        self,
        proposal_id: str,
        *,
        accept: bool,
        edited_snapshot: ThesisSnapshot | None = None,
        note: str = "",
    ) -> ProposedRevision:
        proposal = self._theses.get_proposal(self._workspace_id, proposal_id)
        if proposal is None:
            raise KeyError("proposal not found")
        if proposal.status is not RevisionStatus.PROPOSED:
            raise ValueError(f"proposal {proposal.id} was already reviewed")

        reviewed = proposal.model_copy(
            update={
                "status": RevisionStatus.ACCEPTED if accept else RevisionStatus.REJECTED,
                "snapshot": (
                    edited_snapshot
                    if (accept and edited_snapshot is not None)
                    else proposal.snapshot
                ),
                "review_note": note,
                "reviewed_at": datetime.now(timezone.utc),
            }
        )
        # User edits on accept are authored by the user.
        if accept and edited_snapshot is not None:
            reviewed = reviewed.model_copy(
                update={
                    "snapshot": reviewed.snapshot.model_copy(update={"author": "user"})
                }
            )
        self._theses.save_proposal(reviewed, workspace_id=self._workspace_id)
        if accept:
            self._apply_snapshot(reviewed.snapshot)
        return reviewed

    def create_from_run(
        self,
        run_id: str,
        *,
        stance: str = "",
        as_proposal: bool = True,
        reason: str = "Created from completed research run",
    ) -> ProposedRevision | tuple[ThesisSnapshot, LivingThesis]:
        run = self._runs.get(self._workspace_id, run_id)
        if run is None:
            raise KeyError("run not found")
        if run.status.value not in {"completed", "partially_completed"}:
            raise ValueError("run must be completed before creating a thesis")

        payload = run.model_dump(mode="json")
        # decision_from_run expects graph-style keys.
        payload["company_of_interest"] = run.symbol
        snapshot, _thesis = self._build_from_run_payload(payload, stance=stance)
        snapshot = snapshot.model_copy(update={"analysis_run_id": run.id, "author": "ai"})
        if as_proposal:
            return self.propose(snapshot, reason=reason, author="ai")
        thesis = self._apply_snapshot(snapshot)
        return snapshot, thesis

    def propose_from_run(
        self,
        run_id: str,
        *,
        stance: str = "",
        reason: str = "AI proposal from research run",
    ) -> ProposedRevision:
        run = self._runs.get(self._workspace_id, run_id)
        if run is None:
            raise KeyError("run not found")
        resolved_stance = stance.strip()
        if not resolved_stance:
            resolved_stance = self._infer_stance(run.symbol)
        result = self.create_from_run(
            run_id, stance=resolved_stance, as_proposal=True, reason=reason
        )
        assert isinstance(result, ProposedRevision)
        return result

    def _infer_stance(self, symbol: str) -> str:
        """Held names manage; everything else initiate."""
        from tradingagents.persistence.repositories.portfolios import PortfolioRepository
        from tradingagents.persistence.repositories.state import PortfolioStateRepository
        from tradingagents.portfolio.service import CURRENT_SNAPSHOT_ID

        controls = PortfolioStateRepository(self._session).get_controls(
            self._workspace_id
        )
        snapshot_id = controls.current_snapshot_id or CURRENT_SNAPSHOT_ID
        book = PortfolioRepository(self._session).get(
            self._workspace_id, snapshot_id
        )
        if book is None and snapshot_id != CURRENT_SNAPSHOT_ID:
            book = PortfolioRepository(self._session).get(
                self._workspace_id, CURRENT_SNAPSHOT_ID
            )
        if book is not None and book.holds(symbol):
            return "manage"
        return "initiate"

    def edit_current(
        self,
        symbol: str,
        snapshot: ThesisSnapshot,
        *,
        reason: str = "User edit",
        as_proposal: bool = False,
    ) -> ProposedRevision | LivingThesis:
        """Human-editable path: user-authored snapshot, never silent AI overwrite."""
        edited = snapshot.model_copy(
            update={"symbol": symbol.strip().upper(), "author": "user"}
        )
        if as_proposal:
            return self.propose(edited, reason=reason, author="user")
        return self._apply_snapshot(edited)

    def select_evidence(
        self,
        symbol: str,
        evidence_ids: list[str],
        *,
        reason: str = "Evidence selection update",
    ) -> ProposedRevision:
        thesis = self._theses.get(self._workspace_id, symbol)
        if thesis is None:
            raise KeyError("thesis not found")
        snapshot = thesis.current.model_copy(
            update={
                "evidence_ids": sorted(set(evidence_ids)),
                "author": "user",
                "prior_snapshot_id": thesis.current_snapshot_id,
                "snapshot_id": f"th_{symbol.strip().upper()}_{thesis.current.as_of}_ev",
            }
        )
        return self.propose(snapshot, reason=reason, author="user")

    def _build_from_run_payload(
        self,
        run: dict[str, Any],
        *,
        stance: str,
    ) -> tuple[ThesisSnapshot, LivingThesis | None]:
        symbol = (run.get("company_of_interest") or run.get("symbol") or "").upper()
        trade_date = run.get("trade_date", "")
        if not symbol or not trade_date:
            raise ValueError("run must carry symbol/company_of_interest and trade_date")
        decision = decision_from_run(run)
        evidence_ids = run.get("evidence_ids") or [
            item.get("id")
            for item in run.get("evidence", [])
            if isinstance(item, dict)
        ]
        prior = self._theses.get(self._workspace_id, symbol)
        snapshot, thesis = build_thesis_update(
            symbol=symbol,
            trade_date=trade_date,
            stance=stance,
            decision=decision,
            evidence_ids=[item for item in evidence_ids if item],
            prior=prior,
            catalysts=decision.catalysts,
            invalidation_conditions=decision.invalidation_conditions,
            invalidation_triggered=decision.invalidation_triggered,
            bull_case=run.get("bull_case") or "",
            bear_case=run.get("bear_case") or "",
            risks=list(run.get("risks") or []),
            analysis_run_id=run.get("id"),
            author="ai",
        )
        return snapshot, thesis

    def _apply_snapshot(self, snapshot: ThesisSnapshot) -> LivingThesis:
        prior = self._theses.get(self._workspace_id, snapshot.symbol)
        applied = snapshot
        if prior is None or prior.current_snapshot_id != snapshot.prior_snapshot_id:
            applied = snapshot.model_copy(
                update={
                    "prior_snapshot_id": prior.current_snapshot_id if prior else None,
                }
            )
        point = ConfidencePoint(as_of=applied.as_of, rating=applied.rating)
        if prior is None:
            thesis = LivingThesis(
                symbol=applied.symbol,
                status=applied.status,
                current_snapshot_id=applied.snapshot_id,
                opened_at=applied.as_of,
                updated_at=applied.as_of,
                snapshot_ids=[applied.snapshot_id],
                confidence_history=[point],
                current=applied,
            )
        else:
            # Preserve history; replace snapshot id if colliding by appending suffix.
            snapshot_ids = list(prior.snapshot_ids)
            if applied.snapshot_id in snapshot_ids:
                applied = applied.model_copy(
                    update={
                        "snapshot_id": f"{applied.snapshot_id}_{len(snapshot_ids)}"
                    }
                )
            thesis = prior.model_copy(
                update={
                    "status": applied.status,
                    "current_snapshot_id": applied.snapshot_id,
                    "updated_at": applied.as_of,
                    "snapshot_ids": [*snapshot_ids, applied.snapshot_id],
                    "confidence_history": [*prior.confidence_history, point],
                    "current": applied,
                }
            )
        return self._theses.upsert(thesis, applied, workspace_id=self._workspace_id)
