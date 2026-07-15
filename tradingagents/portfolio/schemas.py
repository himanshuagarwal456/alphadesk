"""Structured book state: ``Position`` and ``Portfolio``.

These are the canonical, provider-agnostic representations the rest of the
system reasons about. A broker CSV export (see :mod:`.csv_loader`) or the
persisted store (see :mod:`.store`) both normalise into these types, so
downstream agents never see broker-specific column names or formats.

Design choices:

- Raw, broker-reported facts are model *fields* (they serialise to JSON).
- Everything derivable (market value, exposure, weights, concentration) is a
  *property/method*, so the persisted form stays minimal and there is a single
  source of truth for each derived quantity.
- ``quantity`` is signed: negative means a short position. Exposure math keys
  off the sign, so a portfolio with shorts reports a meaningful net vs gross.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class Direction(str, Enum):
    """Which side of the market a position (or the whole book) leans."""

    LONG = "long"
    SHORT = "short"
    FLAT = "flat"


class Position(BaseModel):
    """A single holding in the book.

    ``quantity`` is signed (negative = short). ``avg_cost`` and
    ``current_price`` are optional because not every broker export includes
    both, and a candidate we do not yet hold has neither; downstream code
    treats missing prices as "unknown" rather than zero.
    """

    symbol: str = Field(description="Ticker symbol, upper-cased and stripped.")
    quantity: float = Field(
        description="Signed share/contract count. Negative denotes a short position."
    )
    avg_cost: float | None = Field(
        default=None, description="Average cost basis per share in the position currency."
    )
    current_price: float | None = Field(
        default=None, description="Latest known price per share in the position currency."
    )
    asset_type: str = Field(
        default="stock", description="Instrument class: stock, crypto, option, etc."
    )
    currency: str = Field(default="USD", description="Quote currency of the position.")

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, v: str) -> str:
        normalized = (v or "").strip().upper()
        if not normalized:
            raise ValueError("position symbol must be a non-empty string")
        return normalized

    @field_validator("currency")
    @classmethod
    def _normalize_currency(cls, v: str) -> str:
        return (v or "USD").strip().upper() or "USD"

    # --- Derived quantities (not serialised) ---

    @property
    def direction(self) -> Direction:
        if self.quantity > 0:
            return Direction.LONG
        if self.quantity < 0:
            return Direction.SHORT
        return Direction.FLAT

    @property
    def is_open(self) -> bool:
        """A zero-quantity row is a closed/flat position, not an exposure."""
        return self.quantity != 0

    @property
    def market_value(self) -> float | None:
        """Signed market value (negative for shorts). None when price unknown."""
        if self.current_price is None:
            return None
        return self.quantity * self.current_price

    @property
    def cost_basis(self) -> float | None:
        """Signed cost basis. None when avg cost unknown."""
        if self.avg_cost is None:
            return None
        return self.quantity * self.avg_cost

    @property
    def unrealized_pnl(self) -> float | None:
        """Mark-to-market P&L. None when either price is unknown."""
        if self.current_price is None or self.avg_cost is None:
            return None
        return self.quantity * (self.current_price - self.avg_cost)

    @property
    def unrealized_pnl_pct(self) -> float | None:
        """Return on cost basis. None when unknown or cost basis is zero."""
        if self.current_price is None or self.avg_cost is None or self.avg_cost == 0:
            return None
        # Direction-aware: a short gains when price falls.
        sign = 1.0 if self.quantity >= 0 else -1.0
        return sign * (self.current_price - self.avg_cost) / self.avg_cost


class Portfolio(BaseModel):
    """A snapshot of an account book at a point in time.

    ``cash`` is in ``base_currency``. Positions may be in other currencies in
    principle, but exposure math here assumes a common base; multi-currency FX
    normalisation is intentionally out of scope for this layer (flagged rather
    than silently mixed).
    """

    as_of: str | None = Field(
        default=None, description="Snapshot date (YYYY-MM-DD) the book reflects."
    )
    base_currency: str = Field(default="USD", description="Reporting currency for cash/values.")
    cash: float = Field(default=0.0, description="Uninvested cash in base_currency.")
    positions: list[Position] = Field(default_factory=list)

    @field_validator("base_currency")
    @classmethod
    def _normalize_currency(cls, v: str) -> str:
        return (v or "USD").strip().upper() or "USD"

    @field_validator("positions")
    @classmethod
    def _sort_positions(cls, v: list[Position]) -> list[Position]:
        # Stable, symbol-sorted ordering so serialisation is deterministic
        # regardless of the source row order (reproducibility requirement).
        return sorted(v, key=lambda p: p.symbol)

    # --- Lookups ---

    @property
    def symbols(self) -> list[str]:
        return [p.symbol for p in self.open_positions]

    @property
    def open_positions(self) -> list[Position]:
        return [p for p in self.positions if p.is_open]

    def get(self, symbol: str) -> Position | None:
        target = (symbol or "").strip().upper()
        for p in self.positions:
            if p.symbol == target and p.is_open:
                return p
        return None

    def holds(self, symbol: str) -> bool:
        """True when the book has a non-zero position in ``symbol``."""
        return self.get(symbol) is not None

    # --- Exposure math ---

    @property
    def long_market_value(self) -> float:
        return sum(
            p.market_value for p in self.open_positions
            if p.market_value is not None and p.quantity > 0
        )

    @property
    def short_market_value(self) -> float:
        """Negative number (sum of signed values of shorts)."""
        return sum(
            p.market_value for p in self.open_positions
            if p.market_value is not None and p.quantity < 0
        )

    @property
    def gross_exposure(self) -> float:
        """Sum of absolute position values (long + |short|), price permitting."""
        return sum(
            abs(p.market_value) for p in self.open_positions if p.market_value is not None
        )

    @property
    def net_exposure(self) -> float:
        """Signed sum of position values (long minus short)."""
        return sum(
            p.market_value for p in self.open_positions if p.market_value is not None
        )

    @property
    def invested_value(self) -> float:
        """Alias for net exposure of priced positions; excludes cash."""
        return self.net_exposure

    @property
    def total_value(self) -> float:
        """Net asset value: net position value + cash."""
        return self.net_exposure + self.cash

    @property
    def direction(self) -> Direction:
        net = self.net_exposure
        if net > 0:
            return Direction.LONG
        if net < 0:
            return Direction.SHORT
        return Direction.FLAT

    def weights(self) -> dict[str, float]:
        """Fraction of gross exposure in each symbol (abs value / gross).

        Uses gross so a market-neutral book still reports meaningful per-name
        concentration. Returns an empty dict when nothing is priced.
        """
        gross = self.gross_exposure
        if gross <= 0:
            return {}
        return {
            p.symbol: abs(p.market_value) / gross
            for p in self.open_positions
            if p.market_value is not None
        }

    @property
    def concentration(self) -> float:
        """Largest single-name weight (0..1); 0 when nothing is priced."""
        w = self.weights()
        return max(w.values()) if w else 0.0

    @property
    def total_unrealized_pnl(self) -> float:
        return sum(
            p.unrealized_pnl for p in self.open_positions if p.unrealized_pnl is not None
        )

    @property
    def has_prices(self) -> bool:
        """Whether any open position carries a current price (exposure is meaningful)."""
        return any(p.current_price is not None for p in self.open_positions)
