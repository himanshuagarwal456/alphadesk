"""Intelligence card endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.domain.schemas import IntelligenceCardRecord
from tradingagents.monitoring.schemas import CardStatus
from tradingagents.monitoring.service import MonitoringService
from tradingagents.persistence.repositories import IntelligenceCardRepository

router = APIRouter(prefix="/cards")


class CardStatusUpdateRequest(BaseModel):
    status: CardStatus


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
    status: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[IntelligenceCardRecord]:
    cards = IntelligenceCardRepository(session).list(
        workspace_id, symbol=symbol, limit=limit
    )
    if status:
        cards = [c for c in cards if (c.status or "new") == status]
    return cards


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


@router.post("/{card_id}/status", response_model=IntelligenceCardRecord)
def update_card_status(
    card_id: str,
    body: CardStatusUpdateRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> IntelligenceCardRecord:
    card = MonitoringService(session, workspace_id=workspace_id).update_card_status(
        card_id, status=body.status
    )
    if card is None:
        raise HTTPException(status_code=404, detail="card not found")
    return card
