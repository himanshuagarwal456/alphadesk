"""Decision journal and outcome-review endpoints (Phase 6)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.journal.schemas import DecisionJournalEntry, OutcomeReview
from tradingagents.persistence.repositories import JournalRepository

router = APIRouter(prefix="/journal")


class LessonReuseRequest(BaseModel):
    allow_lesson_reuse: bool


class OutcomeReviewRequest(BaseModel):
    as_of: str = Field(min_length=1)
    outcome_summary: str = Field(min_length=1)
    lesson: str = ""
    allow_lesson_reuse: bool = True
    absolute_return_pct: float | None = None
    benchmark_ticker: str | None = "SPY"
    benchmark_return_pct: float | None = None
    relative_return_pct: float | None = None


@router.post("", response_model=DecisionJournalEntry, status_code=201)
def create_entry(
    body: DecisionJournalEntry,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> DecisionJournalEntry:
    try:
        return JournalRepository(session).save(body, workspace_id=workspace_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get("", response_model=list[DecisionJournalEntry])
def list_entries(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[DecisionJournalEntry]:
    return JournalRepository(session).list(workspace_id, symbol=symbol, limit=limit)


@router.get("/{entry_id}", response_model=DecisionJournalEntry)
def get_entry(
    entry_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> DecisionJournalEntry:
    entry = JournalRepository(session).get(workspace_id, entry_id)
    if entry is None:
        raise HTTPException(status_code=404, detail="journal entry not found")
    return entry


@router.post("/{entry_id}/lesson-reuse", response_model=DecisionJournalEntry)
def set_lesson_reuse(
    entry_id: str,
    body: LessonReuseRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> DecisionJournalEntry:
    entry = JournalRepository(session).set_lesson_reuse(
        workspace_id, entry_id, allow_lesson_reuse=body.allow_lesson_reuse
    )
    if entry is None:
        raise HTTPException(status_code=404, detail="journal entry not found")
    return entry


@router.post(
    "/{entry_id}/outcomes",
    response_model=OutcomeReview,
    status_code=201,
)
def create_outcome_review(
    entry_id: str,
    body: OutcomeReviewRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> OutcomeReview:
    review = OutcomeReview(
        journal_entry_id=entry_id,
        workspace_id=workspace_id,
        as_of=body.as_of,
        outcome_summary=body.outcome_summary,
        lesson=body.lesson,
        allow_lesson_reuse=body.allow_lesson_reuse,
        absolute_return_pct=body.absolute_return_pct,
        benchmark_ticker=body.benchmark_ticker,
        benchmark_return_pct=body.benchmark_return_pct,
        relative_return_pct=body.relative_return_pct,
    )
    try:
        return JournalRepository(session).save_outcome(
            review, workspace_id=workspace_id
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/{entry_id}/outcomes", response_model=list[OutcomeReview])
def list_outcomes(
    entry_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[OutcomeReview]:
    return JournalRepository(session).list_outcomes(
        workspace_id, journal_entry_id=entry_id
    )
