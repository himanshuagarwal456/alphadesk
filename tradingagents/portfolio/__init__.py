"""Portfolio-awareness layer for TradingAgents.

Turns the framework from a stateless per-ticker decision engine into a
portfolio-aware one: an existing book is loaded (from a broker CSV export or a
persisted store), and the agent graph reasons about held positions
(manage / trim / exit) versus new candidates (initiate) with full awareness of
exposure, concentration, and available cash.

Public surface:

- ``Position`` / ``Portfolio``   — structured book state (schemas)
- ``load_portfolio_from_csv``    — broker CSV export -> ``Portfolio``
- ``PortfolioStore``             — deterministic, date-aware JSON persistence
- ``Stance`` / ``classify_stance`` — initiate vs. manage/exit routing per name
- ``render_portfolio_context``   — book state -> Portfolio Manager prompt block
- ``iter_book_targets`` / ``run_book`` — run over holdings + a candidate watchlist
"""

from .context import (
    Stance,
    classify_stance,
    render_market_view,
    render_portfolio_context,
)
from .csv_loader import PortfolioCSVError, load_portfolio_from_csv
from .runner import BookTarget, iter_book_targets, run_book
from .schemas import Direction, Portfolio, Position
from .store import PortfolioStore

__all__ = [
    "BookTarget",
    "Direction",
    "Portfolio",
    "PortfolioCSVError",
    "PortfolioStore",
    "Position",
    "Stance",
    "classify_stance",
    "iter_book_targets",
    "load_portfolio_from_csv",
    "render_market_view",
    "render_portfolio_context",
    "run_book",
]
