"""Portfolio snapshot endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.persistence.repositories import PortfolioRepository
from tradingagents.portfolio.schemas import Portfolio

router = APIRouter(prefix="/portfolios")


class PortfolioSnapshotResponse(BaseModel):
    id: str
    portfolio: Portfolio


class SavePortfolioRequest(BaseModel):
    portfolio: Portfolio
    snapshot_id: str | None = Field(default=None)


@router.post("", response_model=PortfolioSnapshotResponse, status_code=201)
def save_portfolio(
    body: SavePortfolioRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    sid, portfolio = PortfolioRepository(session).save(
        body.portfolio, workspace_id=workspace_id, snapshot_id=body.snapshot_id
    )
    return PortfolioSnapshotResponse(id=sid, portfolio=portfolio)


@router.get("", response_model=list[PortfolioSnapshotResponse])
def list_portfolios(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PortfolioSnapshotResponse]:
    return [
        PortfolioSnapshotResponse(id=sid, portfolio=p)
        for sid, p in PortfolioRepository(session).list(workspace_id, limit=limit)
    ]


@router.get("/{snapshot_id}", response_model=PortfolioSnapshotResponse)
def get_portfolio(
    snapshot_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    portfolio = PortfolioRepository(session).get(workspace_id, snapshot_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio snapshot not found")
    return PortfolioSnapshotResponse(id=snapshot_id, portfolio=portfolio)
