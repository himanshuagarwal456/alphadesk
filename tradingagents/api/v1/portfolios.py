"""Portfolio product API: import, current book, summary, coverage, editing."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.persistence.repositories import (
    PortfolioRepository,
    PortfolioStateRepository,
    ThesisRepository,
    WatchlistRepository,
)
from tradingagents.portfolio.context import render_portfolio_context
from tradingagents.portfolio.preview import ImportPreview, preview_portfolio_csv
from tradingagents.portfolio.product import PortfolioControls, WatchlistItem
from tradingagents.portfolio.schemas import Portfolio, Position
from tradingagents.portfolio.service import (
    CURRENT_SNAPSHOT_ID,
    PortfolioSummary,
    PositionDetail,
    ThesisCoverage,
    position_detail,
    remove_position,
    summarize_portfolio,
    thesis_coverage,
    upsert_position,
)

router = APIRouter(prefix="/portfolios")


class PortfolioSnapshotResponse(BaseModel):
    id: str
    portfolio: Portfolio
    research_only: bool = True


class SavePortfolioRequest(BaseModel):
    portfolio: Portfolio
    snapshot_id: str | None = Field(default=None)
    activate: bool = Field(
        default=False,
        description="When true, also mark this snapshot as the workspace current book.",
    )


class ImportPreviewRequest(BaseModel):
    content: str = Field(min_length=1)
    as_of: str | None = None
    base_currency: str = "USD"
    cash: float | None = None
    column_map: dict[str, str] | None = None


class ImportConfirmRequest(BaseModel):
    portfolio: Portfolio
    snapshot_id: str = CURRENT_SNAPSHOT_ID
    monitoring_enabled: bool = True


class UpsertPositionRequest(BaseModel):
    position: Position


class ControlsUpdateRequest(BaseModel):
    monitoring_enabled: bool


class WatchlistUpsertRequest(BaseModel):
    name: str = Field(min_length=1)
    items: list[WatchlistItem] = Field(default_factory=list)
    id: str | None = None


def _activate_current(
    session: Session,
    workspace_id: str,
    snapshot_id: str,
    *,
    monitoring_enabled: bool | None = None,
) -> PortfolioControls:
    state = PortfolioStateRepository(session)
    controls = state.get_controls(workspace_id)
    updates: dict = {"current_snapshot_id": snapshot_id, "research_only": True}
    if monitoring_enabled is not None:
        updates["monitoring_enabled"] = monitoring_enabled
    return state.set_controls(workspace_id, controls.model_copy(update=updates))


def _require_current(session: Session, workspace_id: str) -> tuple[str, Portfolio]:
    controls = PortfolioStateRepository(session).get_controls(workspace_id)
    snapshot_id = controls.current_snapshot_id or CURRENT_SNAPSHOT_ID
    portfolio = PortfolioRepository(session).get(workspace_id, snapshot_id)
    if portfolio is None and snapshot_id != CURRENT_SNAPSHOT_ID:
        portfolio = PortfolioRepository(session).get(workspace_id, CURRENT_SNAPSHOT_ID)
        snapshot_id = CURRENT_SNAPSHOT_ID
    if portfolio is None:
        raise HTTPException(status_code=404, detail="current portfolio not found")
    return snapshot_id, portfolio


# --- Static paths first (before /{snapshot_id}) --------------------------------


@router.post("/import/preview", response_model=ImportPreview)
def import_preview(
    body: ImportPreviewRequest,
    workspace_id: str = Depends(get_workspace_id),  # noqa: ARG001 - tenancy header
) -> ImportPreview:
    return preview_portfolio_csv(
        content=body.content,
        as_of=body.as_of or date.today().isoformat(),
        base_currency=body.base_currency,
        cash=body.cash,
        column_map=body.column_map,
    )


@router.post("/import/confirm", response_model=PortfolioSnapshotResponse, status_code=201)
def import_confirm(
    body: ImportConfirmRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    if not body.portfolio.positions and body.portfolio.cash == 0:
        raise HTTPException(status_code=400, detail="portfolio is empty")
    sid, portfolio = PortfolioRepository(session).save(
        body.portfolio,
        workspace_id=workspace_id,
        snapshot_id=body.snapshot_id or CURRENT_SNAPSHOT_ID,
    )
    _activate_current(
        session,
        workspace_id,
        sid,
        monitoring_enabled=body.monitoring_enabled,
    )
    return PortfolioSnapshotResponse(id=sid, portfolio=portfolio, research_only=True)


@router.get("/current", response_model=PortfolioSnapshotResponse)
def get_current_portfolio(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    snapshot_id, portfolio = _require_current(session, workspace_id)
    return PortfolioSnapshotResponse(
        id=snapshot_id, portfolio=portfolio, research_only=True
    )


@router.put("/current", response_model=PortfolioSnapshotResponse)
def replace_current_portfolio(
    body: SavePortfolioRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    sid, portfolio = PortfolioRepository(session).save(
        body.portfolio,
        workspace_id=workspace_id,
        snapshot_id=CURRENT_SNAPSHOT_ID,
    )
    _activate_current(session, workspace_id, sid)
    return PortfolioSnapshotResponse(id=sid, portfolio=portfolio, research_only=True)


@router.post("/current/positions", response_model=PortfolioSnapshotResponse)
def upsert_current_position(
    body: UpsertPositionRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    snapshot_id, portfolio = _require_current(session, workspace_id)
    updated = upsert_position(portfolio, body.position)
    sid, saved = PortfolioRepository(session).save(
        updated, workspace_id=workspace_id, snapshot_id=snapshot_id
    )
    _activate_current(session, workspace_id, sid)
    return PortfolioSnapshotResponse(id=sid, portfolio=saved, research_only=True)


@router.delete(
    "/current/positions/{symbol}",
    response_model=PortfolioSnapshotResponse,
)
def delete_current_position(
    symbol: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    snapshot_id, portfolio = _require_current(session, workspace_id)
    if not portfolio.holds(symbol):
        raise HTTPException(status_code=404, detail="position not found")
    updated = remove_position(portfolio, symbol)
    sid, saved = PortfolioRepository(session).save(
        updated, workspace_id=workspace_id, snapshot_id=snapshot_id
    )
    return PortfolioSnapshotResponse(id=sid, portfolio=saved, research_only=True)


@router.get("/current/summary", response_model=PortfolioSummary)
def current_summary(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSummary:
    snapshot_id, portfolio = _require_current(session, workspace_id)
    controls = PortfolioStateRepository(session).get_controls(workspace_id)
    return summarize_portfolio(portfolio, snapshot_id=snapshot_id, controls=controls)


@router.get("/current/thesis-coverage", response_model=ThesisCoverage)
def current_thesis_coverage(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> ThesisCoverage:
    _, portfolio = _require_current(session, workspace_id)
    theses = ThesisRepository(session).list(workspace_id, limit=500)
    watchlists = WatchlistRepository(session).list(workspace_id, limit=50)
    monitoring: dict[str, bool] = {}
    for watchlist in watchlists:
        for item in watchlist.items:
            monitoring[item.symbol] = item.monitoring_enabled
    return thesis_coverage(portfolio, theses, monitoring_by_symbol=monitoring)


@router.get("/current/positions/{symbol}", response_model=PositionDetail)
def current_position_detail(
    symbol: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PositionDetail:
    _, portfolio = _require_current(session, workspace_id)
    thesis = ThesisRepository(session).get(workspace_id, symbol)
    watchlists = WatchlistRepository(session).list(workspace_id, limit=50)
    monitoring = True
    for watchlist in watchlists:
        for item in watchlist.items:
            if item.symbol == symbol.strip().upper():
                monitoring = item.monitoring_enabled
                break
    context = render_portfolio_context(portfolio, symbol)
    return position_detail(
        portfolio,
        symbol,
        thesis=thesis,
        monitoring_enabled=monitoring,
        research_context=context,
    )


@router.get("/controls", response_model=PortfolioControls)
def get_controls(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioControls:
    return PortfolioStateRepository(session).get_controls(workspace_id)


@router.put("/controls", response_model=PortfolioControls)
def update_controls(
    body: ControlsUpdateRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioControls:
    state = PortfolioStateRepository(session)
    controls = state.get_controls(workspace_id)
    return state.set_controls(
        workspace_id,
        controls.model_copy(
            update={"monitoring_enabled": body.monitoring_enabled, "research_only": True}
        ),
    )


@router.post("", response_model=PortfolioSnapshotResponse, status_code=201)
def save_portfolio(
    body: SavePortfolioRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    sid, portfolio = PortfolioRepository(session).save(
        body.portfolio, workspace_id=workspace_id, snapshot_id=body.snapshot_id
    )
    if body.activate or sid == CURRENT_SNAPSHOT_ID:
        _activate_current(session, workspace_id, sid)
    return PortfolioSnapshotResponse(id=sid, portfolio=portfolio, research_only=True)


@router.get("", response_model=list[PortfolioSnapshotResponse])
def list_portfolios(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[PortfolioSnapshotResponse]:
    return [
        PortfolioSnapshotResponse(id=sid, portfolio=p, research_only=True)
        for sid, p in PortfolioRepository(session).list(workspace_id, limit=limit)
    ]


@router.get("/{snapshot_id}/summary", response_model=PortfolioSummary)
def snapshot_summary(
    snapshot_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSummary:
    portfolio = PortfolioRepository(session).get(workspace_id, snapshot_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio snapshot not found")
    controls = PortfolioStateRepository(session).get_controls(workspace_id)
    return summarize_portfolio(portfolio, snapshot_id=snapshot_id, controls=controls)


@router.get("/{snapshot_id}", response_model=PortfolioSnapshotResponse)
def get_portfolio(
    snapshot_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioSnapshotResponse:
    portfolio = PortfolioRepository(session).get(workspace_id, snapshot_id)
    if portfolio is None:
        raise HTTPException(status_code=404, detail="portfolio snapshot not found")
    return PortfolioSnapshotResponse(
        id=snapshot_id, portfolio=portfolio, research_only=True
    )


# Watchlists live under /v1/watchlists via a sibling router.
