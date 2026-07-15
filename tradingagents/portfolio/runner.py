"""Run the agent graph over a whole book: holdings + candidate watchlist.

The upstream entry point analyses one ticker at a time. A desk instead wakes
up with an existing book and a universe of candidates, and has to decide what
to do across *all* of them. :func:`iter_book_targets` turns a
``(portfolio, watchlist)`` pair into the deterministic list of names to run —
each tagged with its stance (``manage`` for held names, ``initiate`` for new
candidates) — and :func:`run_book` drives the graph over that list.

The graph is passed in (duck-typed on ``.propagate``) rather than imported, so
this module stays free of the heavy ``trading_graph`` import and is trivially
unit-testable with a stub.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from .context import Stance, classify_stance
from .schemas import Portfolio


@dataclass(frozen=True)
class BookTarget:
    """One name to run, with the stance and asset type resolved from the book."""

    symbol: str
    stance: Stance
    asset_type: str = "stock"


class _GraphLike(Protocol):
    def propagate(self, company_name: str, trade_date: str, asset_type: str = ...): ...


def iter_book_targets(
    portfolio: Portfolio | None,
    watchlist: list[str] | None = None,
) -> list[BookTarget]:
    """Resolve the ordered set of names to run for a book + candidate list.

    Held names come first (stance ``MANAGE``, asset type taken from the
    position), then candidate names not already held (stance ``INITIATE``).
    Ordering is deterministic (each group symbol-sorted) and symbols are
    de-duplicated case-insensitively, so a name that is both held and on the
    watchlist is run once, as a MANAGE.
    """
    targets: list[BookTarget] = []
    seen: set[str] = set()

    if portfolio is not None:
        for pos in sorted(portfolio.open_positions, key=lambda p: p.symbol):
            if pos.symbol in seen:
                continue
            seen.add(pos.symbol)
            targets.append(
                BookTarget(symbol=pos.symbol, stance=Stance.MANAGE, asset_type=pos.asset_type)
            )

    for raw in sorted({(s or "").strip().upper() for s in (watchlist or []) if (s or "").strip()}):
        if raw in seen:
            continue
        seen.add(raw)
        targets.append(
            BookTarget(
                symbol=raw,
                stance=classify_stance(portfolio, raw),
                asset_type="stock",
            )
        )

    return targets


def run_book(
    graph: _GraphLike,
    trade_date: str,
    portfolio: Portfolio | None = None,
    watchlist: list[str] | None = None,
    *,
    market_view: str = "",
) -> dict[str, Any]:
    """Run ``graph.propagate`` over every book target, returning a per-symbol map.

    Each value is ``{"stance", "asset_type", "decision", "final_state"}``. A
    per-name failure is captured as ``{"error": ...}`` so one bad ticker does
    not abort the whole book run.
    """
    results: dict[str, Any] = {}
    for target in iter_book_targets(portfolio, watchlist):
        try:
            final_state, decision = graph.propagate(
                target.symbol,
                trade_date,
                asset_type=target.asset_type,
                portfolio=portfolio,
                market_view=market_view,
            )
            results[target.symbol] = {
                "stance": target.stance.value,
                "asset_type": target.asset_type,
                "decision": decision,
                "final_state": final_state,
            }
        except Exception as exc:  # noqa: BLE001 — isolate per-name failures
            results[target.symbol] = {
                "stance": target.stance.value,
                "asset_type": target.asset_type,
                "error": f"{type(exc).__name__}: {exc}",
            }
    return results
