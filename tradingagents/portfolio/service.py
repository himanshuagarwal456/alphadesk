"""Portfolio product helpers: summary, editing, thesis coverage."""

from __future__ import annotations

from pydantic import BaseModel, Field

from tradingagents.thesis.schemas import LivingThesis

from .product import PortfolioControls
from .schemas import Portfolio, Position

CURRENT_SNAPSHOT_ID = "current"


class PortfolioSummary(BaseModel):
    snapshot_id: str
    as_of: str | None = None
    cash: float
    total_value: float
    gross_exposure: float
    net_exposure: float
    concentration: float
    weights: dict[str, float] = Field(default_factory=dict)
    open_positions: int = 0
    unpriced_positions: int = 0
    priced_positions: int = 0
    has_prices: bool = False
    research_only: bool = True
    monitoring_enabled: bool = True


class ThesisCoverageItem(BaseModel):
    symbol: str
    held: bool
    quantity: float | None = None
    has_thesis: bool
    thesis_status: str | None = None
    monitoring_enabled: bool = True


class ThesisCoverage(BaseModel):
    items: list[ThesisCoverageItem]
    held_count: int
    with_thesis: int
    without_thesis: int


class PositionDetail(BaseModel):
    """Position-level company navigation payload."""

    symbol: str
    position: Position | None = None
    weight: float | None = None
    price_status: str
    thesis_status: str | None = None
    has_thesis: bool = False
    research_context: str = ""
    monitoring_enabled: bool = True
    research_only: bool = True


def summarize_portfolio(
    portfolio: Portfolio,
    *,
    snapshot_id: str,
    controls: PortfolioControls | None = None,
) -> PortfolioSummary:
    controls = controls or PortfolioControls()
    open_positions = portfolio.open_positions
    unpriced = [p for p in open_positions if p.current_price is None]
    priced = [p for p in open_positions if p.current_price is not None]
    return PortfolioSummary(
        snapshot_id=snapshot_id,
        as_of=portfolio.as_of,
        cash=portfolio.cash,
        total_value=portfolio.total_value,
        gross_exposure=portfolio.gross_exposure,
        net_exposure=portfolio.net_exposure,
        concentration=portfolio.concentration,
        weights=portfolio.weights(),
        open_positions=len(open_positions),
        unpriced_positions=len(unpriced),
        priced_positions=len(priced),
        has_prices=portfolio.has_prices,
        research_only=True,
        monitoring_enabled=controls.monitoring_enabled,
    )


def upsert_position(portfolio: Portfolio, position: Position) -> Portfolio:
    others = [p for p in portfolio.positions if p.symbol != position.symbol]
    if position.quantity == 0:
        return portfolio.model_copy(update={"positions": others})
    return portfolio.model_copy(update={"positions": [*others, position]})


def remove_position(portfolio: Portfolio, symbol: str) -> Portfolio:
    target = symbol.strip().upper()
    return portfolio.model_copy(
        update={"positions": [p for p in portfolio.positions if p.symbol != target]}
    )


def thesis_coverage(
    portfolio: Portfolio,
    theses: list[LivingThesis],
    *,
    monitoring_by_symbol: dict[str, bool] | None = None,
) -> ThesisCoverage:
    monitoring_by_symbol = monitoring_by_symbol or {}
    thesis_by_symbol = {t.symbol.upper(): t for t in theses}
    held = {p.symbol: p for p in portfolio.open_positions}
    symbols = sorted(set(held) | set(thesis_by_symbol))
    items: list[ThesisCoverageItem] = []
    for symbol in symbols:
        thesis = thesis_by_symbol.get(symbol)
        position = held.get(symbol)
        items.append(
            ThesisCoverageItem(
                symbol=symbol,
                held=position is not None,
                quantity=position.quantity if position else None,
                has_thesis=thesis is not None,
                thesis_status=thesis.status.value if thesis else None,
                monitoring_enabled=monitoring_by_symbol.get(symbol, True),
            )
        )
    with_thesis = sum(1 for i in items if i.held and i.has_thesis)
    held_count = sum(1 for i in items if i.held)
    return ThesisCoverage(
        items=items,
        held_count=held_count,
        with_thesis=with_thesis,
        without_thesis=held_count - with_thesis,
    )


def position_detail(
    portfolio: Portfolio,
    symbol: str,
    *,
    thesis: LivingThesis | None = None,
    monitoring_enabled: bool = True,
    research_context: str = "",
) -> PositionDetail:
    target = symbol.strip().upper()
    position = portfolio.get(target)
    weights = portfolio.weights()
    if position is None:
        price_status = "not_held"
    elif position.current_price is None:
        price_status = "missing_price"
    elif position.current_price == 0:
        price_status = "zero_price"
    else:
        price_status = "priced"
    return PositionDetail(
        symbol=target,
        position=position,
        weight=weights.get(target),
        price_status=price_status,
        thesis_status=thesis.status.value if thesis else None,
        has_thesis=thesis is not None,
        research_context=research_context,
        monitoring_enabled=monitoring_enabled,
        research_only=True,
    )
