"""Decision journal endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.journal.schemas import DecisionJournalEntry
from tradingagents.persistence.repositories import JournalRepository

router = APIRouter(prefix="/journal")


@router.post("", response_model=DecisionJournalEntry, status_code=201)
def create_entry(
    body: DecisionJournalEntry,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> DecisionJournalEntry:
    return JournalRepository(session).save(body, workspace_id=workspace_id)


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
