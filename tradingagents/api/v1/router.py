"""Aggregated `/v1` router."""

from __future__ import annotations

from fastapi import APIRouter

from . import (
    cards,
    events,
    evidence,
    journal,
    knowledge,
    monitoring,
    ops,
    portfolios,
    research,
    runs,
    theses,
    watchlists,
    workspaces,
)

api_router = APIRouter()
api_router.include_router(workspaces.router, tags=["workspaces"])
api_router.include_router(runs.router, tags=["runs"])
api_router.include_router(events.router, tags=["events"])
api_router.include_router(evidence.router, tags=["evidence"])
api_router.include_router(theses.router, tags=["theses"])
api_router.include_router(journal.router, tags=["journal"])
api_router.include_router(portfolios.router, tags=["portfolios"])
api_router.include_router(watchlists.router, tags=["watchlists"])
api_router.include_router(cards.router, tags=["cards"])
api_router.include_router(research.router, tags=["research"])
api_router.include_router(knowledge.router, tags=["knowledge"])
api_router.include_router(monitoring.router, tags=["monitoring"])
api_router.include_router(ops.router, tags=["ops"])
