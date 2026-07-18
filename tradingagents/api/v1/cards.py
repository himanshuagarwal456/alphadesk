"""Intelligence card endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.domain.schemas import IntelligenceCardRecord
from tradingagents.persistence.repositories import IntelligenceCardRepository

router = APIRouter(prefix="/cards")


@router.post("", response_model=IntelligenceCardRecord, status_code=201)
def save_card(
    body: IntelligenceCardRecord,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> IntelligenceCardRecord:
    return IntelligenceCardRepository(session).save(body, workspace_id=workspace_id)


@router.get("", response_model=list[IntelligenceCardRecord])
def list_cards(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    symbol: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[IntelligenceCardRecord]:
    return IntelligenceCardRepository(session).list(
        workspace_id, symbol=symbol, limit=limit
    )


@router.get("/{card_id}", response_model=IntelligenceCardRecord)
def get_card(
    card_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> IntelligenceCardRecord:
    card = IntelligenceCardRepository(session).get(workspace_id, card_id)
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return card
