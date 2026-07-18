"""Thesis endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.persistence.repositories import ThesisRepository
from tradingagents.thesis.schemas import LivingThesis, ThesisSnapshot

router = APIRouter(prefix="/theses")


class UpsertThesisRequest(BaseModel):
    thesis: LivingThesis
    snapshot: ThesisSnapshot | None = None


@router.put("/{symbol}", response_model=LivingThesis)
def upsert_thesis(
    symbol: str,
    body: UpsertThesisRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> LivingThesis:
    if body.thesis.symbol.upper() != symbol.strip().upper():
        raise HTTPException(status_code=400, detail="symbol path mismatch")
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
