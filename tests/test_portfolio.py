"""Portfolio layer: schema exposure math, broker-CSV parsing, and store round-trips.

Pure in-memory / tmp-path tests — no network, no keys.
"""

import pytest

from tradingagents.portfolio import (
    Direction,
    Portfolio,
    PortfolioCSVError,
    PortfolioStore,
    Position,
    load_portfolio_from_csv,
)

# ---------------------------------------------------------------------------
# Position
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPosition:
    def test_symbol_is_normalised(self):
        p = Position(symbol="  nvda ", quantity=10)
        assert p.symbol == "NVDA"

    def test_empty_symbol_rejected(self):
        with pytest.raises(ValueError):
            Position(symbol="   ", quantity=1)

    def test_long_direction_and_values(self):
        p = Position(symbol="AAPL", quantity=100, avg_cost=150.0, current_price=200.0)
        assert p.direction is Direction.LONG
        assert p.is_open
        assert p.market_value == pytest.approx(20000.0)
        assert p.cost_basis == pytest.approx(15000.0)
        assert p.unrealized_pnl == pytest.approx(5000.0)
        assert p.unrealized_pnl_pct == pytest.approx(1 / 3)

    def test_short_pnl_is_direction_aware(self):
        # Short 10 @ 100, now 90 -> profit; pct positive because price fell.
        p = Position(symbol="TSLA", quantity=-10, avg_cost=100.0, current_price=90.0)
        assert p.direction is Direction.SHORT
        assert p.market_value == pytest.approx(-900.0)
        assert p.unrealized_pnl == pytest.approx(100.0)
        assert p.unrealized_pnl_pct == pytest.approx(0.1)

    def test_missing_prices_are_unknown_not_zero(self):
        p = Position(symbol="MSFT", quantity=5)
        assert p.market_value is None
        assert p.unrealized_pnl is None
        assert p.unrealized_pnl_pct is None

    def test_zero_quantity_is_not_open(self):
        assert Position(symbol="X", quantity=0).is_open is False


# ---------------------------------------------------------------------------
# Portfolio
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPortfolio:
    def _book(self) -> Portfolio:
        return Portfolio(
            as_of="2026-01-15",
            cash=10000.0,
            positions=[
                Position(symbol="NVDA", quantity=100, avg_cost=100.0, current_price=120.0),
                Position(symbol="AAPL", quantity=50, avg_cost=200.0, current_price=180.0),
                Position(symbol="SPY", quantity=-20, avg_cost=500.0, current_price=490.0),
            ],
        )

    def test_positions_sorted_deterministically(self):
        assert self._book().symbols == ["AAPL", "NVDA", "SPY"]

    def test_holds_and_get(self):
        book = self._book()
        assert book.holds("nvda") is True
        assert book.holds("GOOG") is False
        assert book.get("aapl").quantity == 50

    def test_exposure_math(self):
        book = self._book()
        # long: 100*120 + 50*180 = 12000 + 9000 = 21000
        # short: -20*490 = -9800
        assert book.long_market_value == pytest.approx(21000.0)
        assert book.short_market_value == pytest.approx(-9800.0)
        assert book.gross_exposure == pytest.approx(30800.0)
        assert book.net_exposure == pytest.approx(11200.0)
        assert book.total_value == pytest.approx(21200.0)
        assert book.direction is Direction.LONG

    def test_weights_and_concentration(self):
        book = self._book()
        weights = book.weights()
        assert weights["NVDA"] == pytest.approx(12000.0 / 30800.0)
        assert sum(weights.values()) == pytest.approx(1.0)
        assert book.concentration == pytest.approx(12000.0 / 30800.0)

    def test_unpriced_book_has_no_exposure(self):
        book = Portfolio(positions=[Position(symbol="ABC", quantity=10)])
        assert book.has_prices is False
        assert book.gross_exposure == 0.0
        assert book.weights() == {}
        assert book.concentration == 0.0


# ---------------------------------------------------------------------------
# CSV loader
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestCSVLoader:
    def test_standard_export(self):
        csv_text = (
            "Symbol,Quantity,Average Cost,Last Price\n"
            "NVDA,100,100.00,120.50\n"
            "AAPL,50,200.00,180.00\n"
        )
        book = load_portfolio_from_csv(content=csv_text, as_of="2026-01-15")
        assert book.symbols == ["AAPL", "NVDA"]
        assert book.get("NVDA").current_price == pytest.approx(120.50)
        assert book.as_of == "2026-01-15"

    def test_broker_decorations_are_cleaned(self):
        # $, commas, and accounting-style negative parentheses.
        csv_text = (
            "Ticker,Shares,Cost Basis Per Share,Market Value\n"
            "BRK.B,\"1,000\",\"$300.00\",\"$300,000.00\"\n"
            "HEDGE,(25),\"$40.00\",\"($1,000.00)\"\n"
        )
        book = load_portfolio_from_csv(content=csv_text)
        assert book.get("BRK.B").quantity == pytest.approx(1000.0)
        assert book.get("BRK.B").avg_cost == pytest.approx(300.0)
        short = book.get("HEDGE")
        assert short.quantity == pytest.approx(-25.0)
        assert short.direction is Direction.SHORT

    def test_price_inferred_from_market_value(self):
        csv_text = "Symbol,Quantity,Market Value\nMSFT,10,4000.00\n"
        book = load_portfolio_from_csv(content=csv_text)
        assert book.get("MSFT").current_price == pytest.approx(400.0)

    def test_cash_row_folded_into_cash(self):
        csv_text = (
            "Symbol,Quantity,Last Price,Market Value\n"
            "NVDA,100,120.00,12000.00\n"
            "SPAXX,5000,1.00,5000.00\n"
        )
        book = load_portfolio_from_csv(content=csv_text)
        assert book.holds("SPAXX") is False
        assert book.cash == pytest.approx(5000.0)

    def test_explicit_cash_overrides_detected(self):
        csv_text = "Symbol,Quantity,Last Price\nNVDA,100,120.00\n"
        book = load_portfolio_from_csv(content=csv_text, cash=2500.0)
        assert book.cash == pytest.approx(2500.0)

    def test_column_map_override(self):
        csv_text = "MySym,MyQty\nNVDA,100\n"
        book = load_portfolio_from_csv(
            content=csv_text, column_map={"symbol": "MySym", "quantity": "MyQty"}
        )
        assert book.get("NVDA").quantity == pytest.approx(100.0)

    def test_missing_required_column_raises(self):
        with pytest.raises(PortfolioCSVError):
            load_portfolio_from_csv(content="Foo,Bar\n1,2\n")

    def test_empty_positions_raises(self):
        with pytest.raises(PortfolioCSVError):
            load_portfolio_from_csv(content="Symbol,Quantity\n")

    def test_path_and_content_mutually_exclusive(self):
        with pytest.raises(PortfolioCSVError):
            load_portfolio_from_csv(path="x.csv", content="y")


# ---------------------------------------------------------------------------
# Store
# ---------------------------------------------------------------------------


@pytest.mark.unit
class TestPortfolioStore:
    def _book(self) -> Portfolio:
        return Portfolio(
            as_of="2026-01-15",
            cash=1000.0,
            positions=[Position(symbol="NVDA", quantity=100, avg_cost=100.0, current_price=120.0)],
        )

    def test_save_load_round_trip(self, tmp_path):
        store = PortfolioStore(tmp_path)
        assert store.load() is None
        store.save(self._book())
        loaded = store.load()
        assert loaded is not None
        assert loaded.get("NVDA").quantity == pytest.approx(100.0)
        assert loaded.cash == pytest.approx(1000.0)

    def test_serialisation_is_byte_stable(self, tmp_path):
        store = PortfolioStore(tmp_path)
        store.save(self._book())
        first = store.book_path.read_text(encoding="utf-8")
        store.save(self._book())
        assert store.book_path.read_text(encoding="utf-8") == first

    def test_dated_snapshots(self, tmp_path):
        store = PortfolioStore(tmp_path)
        store.snapshot(self._book())
        other = self._book()
        other.as_of = "2026-02-15"
        store.snapshot(other)
        assert store.snapshot_dates() == ["2026-01-15", "2026-02-15"]
        assert store.load_snapshot("2026-01-15").as_of == "2026-01-15"
        assert store.load_snapshot("2099-01-01") is None

    def test_snapshot_requires_date(self, tmp_path):
        store = PortfolioStore(tmp_path)
        book = self._book()
        book.as_of = None
        with pytest.raises(ValueError):
            store.snapshot(book)
