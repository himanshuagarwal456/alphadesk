"""Phase 5 portfolio product: preview, editing, watchlists, coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

from tradingagents.agents.schemas import PortfolioRating
from tradingagents.portfolio import (
    CURRENT_SNAPSHOT_ID,
    Portfolio,
    Position,
    RowStatus,
    preview_portfolio_csv,
    summarize_portfolio,
    thesis_coverage,
    upsert_position,
)
from tradingagents.thesis.schemas import LivingThesis, ThesisSnapshot, ThesisStatus

FIXTURES = Path(__file__).parent / "fixtures" / "portfolios"


@pytest.mark.unit
def test_preview_mixed_fixture_meets_95_percent_success():
    preview = preview_portfolio_csv(path=FIXTURES / "broker_mixed_20.csv", as_of="2026-07-18")
    assert preview.fatal_error is None
    assert preview.ok_rows == 19
    assert preview.error_rows == 1
    assert preview.cash_rows == 1
    assert preview.row_success_rate >= 0.95
    assert preview.portfolio is not None
    assert preview.portfolio.cash == pytest.approx(2500.0)
    assert not preview.can_confirm  # error row blocks confirm
    # Missing price is never coerced to zero in ok rows.
    assert all(
        (r.position is None or r.position.current_price != 0 or "price=" in r.message)
        for r in preview.rows
        if r.status is RowStatus.OK
    )


@pytest.mark.unit
def test_preview_column_map_correction_for_unusual_headers():
    bare = preview_portfolio_csv(path=FIXTURES / "unusual_headers.csv")
    assert bare.fatal_error is not None
    fixed = preview_portfolio_csv(
        path=FIXTURES / "unusual_headers.csv",
        column_map={
            "symbol": "Equity Name",
            "quantity": "Units Owned",
            "avg_cost": "Paid Per Unit",
            "current_price": "Latest Quote",
        },
    )
    assert fixed.fatal_error is None
    assert fixed.can_confirm
    assert fixed.ok_rows == 2
    assert {p.symbol for p in fixed.portfolio.positions} == {"BRKB", "LLY"}


@pytest.mark.unit
def test_summary_distinguishes_missing_price_from_zero():
    book = Portfolio(
        as_of="2026-07-18",
        cash=1000.0,
        positions=[
            Position(symbol="AAPL", quantity=10, current_price=100.0),
            Position(symbol="MSFT", quantity=5, current_price=None),
            Position(symbol="ZERO", quantity=2, current_price=0.0),
        ],
    )
    summary = summarize_portfolio(book, snapshot_id=CURRENT_SNAPSHOT_ID)
    assert summary.unpriced_positions == 1
    assert summary.priced_positions == 2
    assert summary.research_only is True
    assert summary.weights["AAPL"] == pytest.approx(1.0)  # only non-zero priced contributes?
    # ZERO has market_value 0 so abs contribution 0; MSFT unpriced excluded.
    assert "MSFT" not in summary.weights


@pytest.mark.unit
def test_thesis_coverage_and_position_edit():
    book = Portfolio(
        positions=[
            Position(symbol="NVDA", quantity=3, current_price=100.0),
            Position(symbol="AAPL", quantity=1, current_price=200.0),
        ]
    )
    snap = ThesisSnapshot(
        snapshot_id="th_NVDA_2026-07-18",
        symbol="NVDA",
        as_of="2026-07-18",
        rating=PortfolioRating.BUY,
        executive_summary="Buy",
        investment_thesis="AI",
    )
    thesis = LivingThesis(
        symbol="NVDA",
        status=ThesisStatus.ACTIVE,
        current_snapshot_id=snap.snapshot_id,
        opened_at="2026-07-18",
        updated_at="2026-07-18",
        snapshot_ids=[snap.snapshot_id],
        confidence_history=[],
        current=snap,
    )
    coverage = thesis_coverage(book, [thesis])
    assert coverage.held_count == 2
    assert coverage.with_thesis == 1
    assert coverage.without_thesis == 1

    edited = upsert_position(
        book, Position(symbol="AAPL", quantity=0, current_price=200.0)
    )
    assert not edited.holds("AAPL")
    assert edited.holds("NVDA")
