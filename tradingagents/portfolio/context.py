"""Turn book state into decision context the agent graph can reason about.

This is the bridge between the structured :class:`Portfolio` and the LLM
agents. It answers two questions for a given symbol on a given run:

1. **Stance** — is this a name we already hold (``MANAGE``: add / trim / hold /
   exit) or a fresh candidate (``INITIATE``: size & enter)? This is the
   "initiate vs. manage/exit" routing decision, computed deterministically from
   the book before the graph runs.
2. **Context block** — a compact markdown briefing (stance, the specific
   position if held, book-level exposure / concentration / cash, and an optional
   top-down market view) that gets injected into the Portfolio Manager prompt so
   the final call is portfolio-aware instead of made in isolation.

Everything here is pure and deterministic: the same ``(portfolio, symbol)``
always renders the same context, which keeps runs reproducible.
"""

from __future__ import annotations

from enum import Enum

from .schemas import Direction, Portfolio


class Stance(str, Enum):
    """Whether a run is opening exposure or managing existing exposure."""

    INITIATE = "initiate"  # not currently held -> size & enter
    MANAGE = "manage"      # already held -> add / trim / hold / exit


def classify_stance(portfolio: Portfolio | None, symbol: str) -> Stance:
    """Route a symbol to the initiate vs. manage path based on the book.

    A non-zero open position in ``symbol`` means MANAGE (the desk already
    carries the risk and must decide add/trim/hold/exit); anything else,
    including an empty or absent book, means INITIATE.
    """
    if portfolio is not None and portfolio.holds(symbol):
        return Stance.MANAGE
    return Stance.INITIATE


def _fmt_money(value: float, currency: str) -> str:
    return f"{value:,.2f} {currency}"


def _fmt_pct(value: float) -> str:
    return f"{value * 100:.1f}%"


def _held_position_lines(portfolio: Portfolio, symbol: str) -> list[str]:
    """Describe the specific held position (the subject of a MANAGE run)."""
    pos = portfolio.get(symbol)
    if pos is None:
        return []
    ccy = pos.currency
    lines = [
        "**Current position in this name:**",
        f"- Direction: {pos.direction.value} ({pos.quantity:g} units)",
    ]
    if pos.avg_cost is not None:
        lines.append(f"- Average cost: {_fmt_money(pos.avg_cost, ccy)}")
    if pos.current_price is not None:
        lines.append(f"- Current price: {_fmt_money(pos.current_price, ccy)}")
    if pos.market_value is not None:
        lines.append(f"- Market value: {_fmt_money(pos.market_value, ccy)}")
    if pos.unrealized_pnl is not None and pos.unrealized_pnl_pct is not None:
        lines.append(
            f"- Unrealized P&L: {_fmt_money(pos.unrealized_pnl, ccy)} "
            f"({_fmt_pct(pos.unrealized_pnl_pct)})"
        )
    weight = portfolio.weights().get(pos.symbol)
    if weight is not None:
        lines.append(f"- Weight (of gross exposure): {_fmt_pct(weight)}")
    return lines


def _book_summary_lines(portfolio: Portfolio) -> list[str]:
    """Describe book-level exposure so sizing respects the whole desk."""
    ccy = portfolio.base_currency
    lines = ["**Portfolio (book) overview:**"]
    if portfolio.as_of:
        lines.append(f"- As of: {portfolio.as_of}")
    lines.append(f"- Cash available: {_fmt_money(portfolio.cash, ccy)}")
    open_positions = portfolio.open_positions
    lines.append(f"- Open positions: {len(open_positions)}")

    if portfolio.has_prices:
        lines.append(f"- Net exposure: {_fmt_money(portfolio.net_exposure, ccy)}")
        lines.append(f"- Gross exposure: {_fmt_money(portfolio.gross_exposure, ccy)}")
        lines.append(f"- Total value (positions + cash): {_fmt_money(portfolio.total_value, ccy)}")
        direction = portfolio.direction
        if direction is not Direction.FLAT:
            lines.append(f"- Net book direction: {direction.value}")
        lines.append(f"- Largest single-name concentration: {_fmt_pct(portfolio.concentration)}")
    else:
        lines.append(
            "- (Position prices not provided, so exposure/concentration are unknown; "
            "reason qualitatively about position count and cash.)"
        )

    if open_positions:
        held = ", ".join(sorted(portfolio.symbols))
        lines.append(f"- Current holdings: {held}")
    return lines


def render_portfolio_context(
    portfolio: Portfolio | None,
    symbol: str,
    *,
    market_view: str = "",
) -> str:
    """Render the portfolio-aware briefing injected into the PM prompt.

    Returns an empty string when there is no book *and* no market view, so the
    default (portfolio-unaware) prompt is used unchanged — this keeps the added
    behaviour opt-in and every existing run byte-for-byte identical.
    """
    market_block = render_market_view(market_view)

    if portfolio is None:
        return market_block

    stance = classify_stance(portfolio, symbol)
    lines: list[str] = ["## Portfolio Context"]

    if stance is Stance.MANAGE:
        lines.append(
            f"**Stance: MANAGE an existing position in {symbol.upper()}.** "
            "This is a name the desk already holds — decide whether to add, "
            "trim, hold, or exit rather than treating it as a fresh entry. "
            "Anchor the decision to the current cost basis and unrealized P&L."
        )
        lines.append("")
        lines.extend(_held_position_lines(portfolio, symbol))
    else:
        lines.append(
            f"**Stance: INITIATE a new position in {symbol.upper()}.** "
            "This name is not currently in the book — decide whether to enter "
            "and, if so, at what size given the existing exposure and cash below."
        )

    lines.append("")
    lines.extend(_book_summary_lines(portfolio))
    lines.append("")
    lines.append(
        "**Sizing constraints to respect:** do not recommend adding risk that "
        "pushes single-name concentration to an imprudent level, that exceeds "
        "available cash for a new long, or that ignores the book's existing net "
        "direction. If the book is already heavily exposed to this name or "
        "correlated names, prefer trimming or holding over adding."
    )

    if market_block:
        lines.append("")
        lines.append(market_block)

    return "\n".join(lines).strip()


def render_market_view(market_view: str) -> str:
    """Wrap a free-text top-down market view as a labelled prompt block."""
    text = (market_view or "").strip()
    if not text:
        return ""
    return f"## Market View (top-down sizing lens)\n{text}"
