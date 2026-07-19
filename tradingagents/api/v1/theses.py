"""Thesis product endpoints (Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.persistence.repositories import ThesisRepository
from tradingagents.thesis.diff import ThesisDiff
from tradingagents.thesis.schemas import LivingThesis, ThesisSnapshot
from tradingagents.thesis.service import ThesisWorkflowService
from tradingagents.thesis.workflow import ProposedRevision, RevisionStatus

router = APIRouter(prefix="/theses")


class UpsertThesisRequest(BaseModel):
    thesis: LivingThesis
    snapshot: ThesisSnapshot | None = None


class FromRunRequest(BaseModel):
    run_id: str = Field(min_length=1)
    stance: str = ""
    reason: str = "Created from completed research run"
    accept: bool = Field(
        default=True,
        description=(
            "When true (default), apply the thesis immediately. "
            "The Create thesis button is an explicit user action. "
            "Set false to leave a pending proposal only."
        ),
    )


class ProposeRequest(BaseModel):
    snapshot: ThesisSnapshot
    reason: str = Field(min_length=1)
    author: str = "ai"


class ReviewRequest(BaseModel):
    accept: bool
    edited_snapshot: ThesisSnapshot | None = None
    note: str = ""


class EditThesisRequest(BaseModel):
    snapshot: ThesisSnapshot
    reason: str = "User edit"
    as_proposal: bool = False


class EvidenceSelectionRequest(BaseModel):
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str = "Evidence selection update"


@router.post("/from-run", response_model=ProposedRevision, status_code=201)
def create_thesis_from_run(
    body: FromRunRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> ProposedRevision:
    service = ThesisWorkflowService(session, workspace_id=workspace_id)
    try:
        proposal = service.propose_from_run(
            body.run_id, stance=body.stance, reason=body.reason
        )
        if body.accept:
            return service.review(
                proposal.id,
                accept=True,
                note="Accepted via create-from-run",
            )
        return proposal
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/{symbol}", response_model=LivingThesis)
def upsert_thesis(
    symbol: str,
    body: UpsertThesisRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> LivingThesis:
    """Bootstrap / test helper. Product AI changes must use proposals."""
    if body.thesis.symbol.upper() != symbol.strip().upper():
        raise HTTPException(status_code=400, detail="symbol path mismatch")
    if body.thesis.current.author == "ai" and body.snapshot is None:
        # Allow explicit user bootstrap; discourage silent AI head replacement.
        pass
    return ThesisRepository(session).upsert(
        body.thesis, body.snapshot, workspace_id=workspace_id
    )


@router.get("", response_model=list[LivingThesis])
def list_theses(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=100, ge=1, le=500),
) -> list[LivingThesis]:
    return ThesisRepository(session).list(workspace_id, limit=limit)


@router.get("/{symbol}", response_model=LivingThesis)
def get_thesis(
    symbol: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> LivingThesis:
    thesis = ThesisRepository(session).get(workspace_id, symbol)
    if thesis is None:
        raise HTTPException(status_code=404, detail="thesis not found")
    return thesis


@router.get("/{symbol}/snapshots", response_model=list[ThesisSnapshot])
def list_snapshots(
    symbol: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[ThesisSnapshot]:
    return ThesisWorkflowService(session, workspace_id=workspace_id).list_snapshots(
        symbol
    )


@router.get("/{symbol}/diff", response_model=ThesisDiff)
def compare_snapshots(
    symbol: str,
    prior: str = Query(..., description="Prior snapshot id"),
    current: str = Query(..., description="Current snapshot id"),
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> ThesisDiff:
    try:
        return ThesisWorkflowService(session, workspace_id=workspace_id).compare(
            symbol, prior_snapshot_id=prior, current_snapshot_id=current
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{symbol}/proposals", response_model=ProposedRevision, status_code=201)
def propose_revision(
    symbol: str,
    body: ProposeRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> ProposedRevision:
    if body.snapshot.symbol.upper() != symbol.strip().upper():
        raise HTTPException(status_code=400, detail="symbol path mismatch")
    return ThesisWorkflowService(session, workspace_id=workspace_id).propose(
        body.snapshot, reason=body.reason, author=body.author
    )


@router.get("/{symbol}/proposals", response_model=list[ProposedRevision])
def list_proposals(
    symbol: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    status: RevisionStatus | None = None,
) -> list[ProposedRevision]:
    return ThesisWorkflowService(session, workspace_id=workspace_id).list_proposals(
        symbol, status=status
    )


@router.post(
    "/{symbol}/proposals/{proposal_id}/review",
    response_model=ProposedRevision,
)
def review_proposal(
    symbol: str,
    proposal_id: str,
    body: ReviewRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> ProposedRevision:
    service = ThesisWorkflowService(session, workspace_id=workspace_id)
    proposal = service.get_proposal(proposal_id)
    if proposal is None or proposal.symbol.upper() != symbol.strip().upper():
        raise HTTPException(status_code=404, detail="proposal not found")
    try:
        return service.review(
            proposal_id,
            accept=body.accept,
            edited_snapshot=body.edited_snapshot,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{symbol}/edit")
def edit_thesis(
    symbol: str,
    body: EditThesisRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
):
    service = ThesisWorkflowService(session, workspace_id=workspace_id)
    try:
        return service.edit_current(
            symbol,
            body.snapshot,
            reason=body.reason,
            as_proposal=body.as_proposal,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/{symbol}/evidence", response_model=ProposedRevision, status_code=201)
def select_evidence(
    symbol: str,
    body: EvidenceSelectionRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> ProposedRevision:
    try:
        return ThesisWorkflowService(session, workspace_id=workspace_id).select_evidence(
            symbol, body.evidence_ids, reason=body.reason
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
