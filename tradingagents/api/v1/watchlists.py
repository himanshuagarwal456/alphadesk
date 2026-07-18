"""Watchlist endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.persistence.repositories import WatchlistRepository
from tradingagents.portfolio.product import Watchlist, WatchlistItem

router = APIRouter(prefix="/watchlists")


class WatchlistUpsertRequest(BaseModel):
    name: str = Field(min_length=1)
    items: list[WatchlistItem] = Field(default_factory=list)
    id: str | None = None


@router.post("", response_model=Watchlist, status_code=201)
def upsert_watchlist(
    body: WatchlistUpsertRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> Watchlist:
    watchlist = Watchlist(
        id=body.id,
        name=body.name,
        workspace_id=workspace_id,
        items=body.items,
    )
    return WatchlistRepository(session).save(watchlist, workspace_id=workspace_id)


@router.get("", response_model=list[Watchlist])
def list_watchlists(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[Watchlist]:
    return WatchlistRepository(session).list(workspace_id, limit=limit)


@router.get("/{watchlist_id}", response_model=Watchlist)
def get_watchlist(
    watchlist_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> Watchlist:
    watchlist = WatchlistRepository(session).get(workspace_id, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="watchlist not found")
    return watchlist


@router.delete("/{watchlist_id}", status_code=204)
def delete_watchlist(
    watchlist_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> None:
    if not WatchlistRepository(session).delete(workspace_id, watchlist_id):
        raise HTTPException(status_code=404, detail="watchlist not found")
