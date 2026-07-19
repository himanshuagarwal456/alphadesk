"""Deterministic sample data so the feed can be demoed/tested without a live run.

``sample_feed()`` builds a multi-story feed (desk brief + theme arcs). When a
real ``Portfolio`` is passed, every open holding gets a synthetic run so the
desk brief reflects the full book — not just two demo tickers.
"""

from __future__ import annotations

import hashlib
from typing import Any

import numpy as np
import pandas as pd

from tradingagents.evidence import Evidence

from .deck_builder import build_feed
from .feed_schema import Feed

_RATING_CYCLE = ("Underweight", "Hold", "Buy", "Overweight", "Sell", "Hold")
_SENTIMENT = {
    "Sell": ("Bearish", 2.4),
    "Underweight": ("Bearish", 3.2),
    "Hold": ("Neutral", 5.1),
    "Overweight": ("Bullish", 6.8),
    "Buy": ("Bullish", 7.4),
}


def sample_ohlcv(days: int = 120, start_price: float = 140.0, trend: float = 0.15) -> pd.DataFrame:
    """A deterministic OHLCV frame (sine + linear trend), yfinance-shaped."""
    idx = pd.date_range(end=pd.Timestamp("2026-01-15"), periods=days, freq="B")
    t = np.arange(days)
    close = start_price + 18.0 * np.sin(t / 9.0) + trend * t
    open_ = close - np.sin(t / 5.0)
    high = np.maximum(open_, close) + 1.6
    low = np.minimum(open_, close) - 1.6
    volume = (5_000_000 + 1_500_000 * np.abs(np.sin(t / 4.0))).astype(int)
    return pd.DataFrame(
        {"Open": open_, "High": high, "Low": low, "Close": close, "Volume": volume},
        index=idx,
    )


def sample_final_state(
    symbol: str = "NVDA",
    *,
    rating: str = "Underweight",
    sentiment_band: str = "Bearish",
    sentiment_score: float = 3.2,
    target: float = 120.0,
    stop: float = 132.0,
    trade_date: str = "2026-01-15",
) -> dict:
    """A canned run state shaped like a real ``final_state``."""
    state = {
        "company_of_interest": symbol,
        "trade_date": trade_date,
        "market_report": (
            f"{symbol} broke below its 50-day moving average on above-average volume, "
            "a bearish signal. RSI is rolling over from overbought territory and MACD "
            "has crossed negative."
            if rating in {"Sell", "Underweight"}
            else (
                f"{symbol} is holding above a rising 50-day average with improving "
                "breadth; MACD turned positive."
            )
        ),
        "sentiment_report": (
            f"**Overall Sentiment:** **{sentiment_band}** (Score: {sentiment_score:.1f}/10)\n"
            "**Confidence:** Medium\n\nRetail chatter has cooled and news tone skews cautious "
            "into the print."
        ),
        "news_report": (
            "Sector headlines flag tighter export controls and softening enterprise demand; "
            "no company-specific catalysts before earnings."
        ),
        "fundamentals_report": (
            "Growth remains strong but decelerating; valuation rich versus the 5-year median. "
            "Margins near peak leave little room for upside surprise."
        ),
        "investment_debate_state": {
            "bull_history": "Bull: durable AI demand, pricing power, and a widening moat justify a premium.",
            "bear_history": "Bear: peak margins, export risk, and a stretched multiple skew risk to the downside.",
            "judge_decision": "The bear case on valuation and margin risk is more compelling near-term.",
        },
        "trader_investment_plan": (
            f"**Action**: Sell\n\n**Reasoning**: Technical breakdown plus stretched valuation.\n\n"
            f"**Entry Price**: {stop + 4:.0f}\n\n**Stop Loss**: {stop:.0f}\n\n"
            "FINAL TRANSACTION PROPOSAL: **SELL**"
        ),
        "risk_debate_state": {
            "aggressive_history": "Aggressive: a dip is a buying opportunity.",
            "conservative_history": "Conservative: protect gains, trim into strength.",
            "neutral_history": "Neutral: reduce, keep a core.",
            "judge_decision": f"Trim exposure; rate {rating}.",
        },
        "investment_plan": "Reduce position size ahead of earnings.",
        "final_trade_decision": (
            f"**Rating**: {rating}\n\n"
            "**Executive Summary**: Trim into strength and reduce exposure ahead of a binary "
            "earnings event; risk/reward is unfavorable at current levels.\n\n"
            "**Investment Thesis**: Technical breakdown, cautious sentiment, and a rich multiple "
            "outweigh the secular growth story on a 1–3 month horizon.\n\n"
            f"**Price Target**: {target:.0f}\n\n**Time Horizon**: 1-3 months"
        ),
        "portfolio_decision_struct": {
            "rating": rating,
            "executive_summary": f"{symbol}: desk rates {rating}.",
            "investment_thesis": f"Synthetic thesis for {symbol} in the demo feed.",
            "price_target": target,
            "time_horizon": "1-3 months",
            "catalysts": ["Earnings"],
            "invalidation_conditions": ["Thesis breaks on guidance cut"],
            "invalidation_triggered": False,
        },
    }
    state["evidence"] = [
        Evidence(
            provider_id="yfinance",
            title=f"{symbol} sector outlook",
            source_url=f"https://finance.yahoo.com/quote/{symbol}/news/",
            publisher="Yahoo Finance",
            published_at="2026-01-14T15:00:00Z",
            summary="A deterministic sample source used only by the feed demo.",
        ).model_dump(mode="json"),
        Evidence(
            provider_id="fred",
            source_type="macro",
            title="Unemployment Rate (UNRATE)",
            source_url="https://fred.stlouisfed.org/series/UNRATE",
            publisher="FRED",
            published_at="2026-01-01T00:00:00Z",
            summary="Latest: 4.2 % (2026-01-01); change over window: +0.1.",
            source_quality_score=0.95,
        ).model_dump(mode="json"),
    ]
    return state


def _rating_for_symbol(symbol: str) -> str:
    digest = int(hashlib.sha256(symbol.encode()).hexdigest()[:8], 16)
    return _RATING_CYCLE[digest % len(_RATING_CYCLE)]


def _runs_for_portfolio(portfolio: Any, *, trade_date: str) -> tuple[list[dict], dict]:
    """One synthetic run + OHLCV series per open position."""
    runs: list[dict] = []
    ohlcv_map: dict = {}
    positions = getattr(portfolio, "open_positions", None)
    if positions is None:
        positions = getattr(portfolio, "positions", []) or []
    for idx, pos in enumerate(positions):
        symbol = str(getattr(pos, "symbol", "") or "").upper()
        if not symbol:
            continue
        rating = _rating_for_symbol(symbol)
        band, score = _SENTIMENT[rating]
        price = getattr(pos, "current_price", None) or 100.0
        target = float(price) * (1.12 if rating in {"Buy", "Overweight"} else 0.88)
        stop = float(price) * 0.94
        runs.append(
            sample_final_state(
                symbol,
                rating=rating,
                sentiment_band=band,
                sentiment_score=score,
                target=round(target, 2),
                stop=round(stop, 2),
                trade_date=trade_date,
            )
        )
        trend = 0.2 if rating in {"Buy", "Overweight"} else -0.05
        ohlcv_map[symbol] = sample_ohlcv(
            start_price=float(price) * 0.85, trend=trend
        )
        # Keep deterministic variety if many names share similar prices.
        _ = idx
    return runs, ohlcv_map


def sample_feed(portfolio: Any = None, *, as_of: str = "2026-01-15") -> Feed:
    """Desk brief + theme stories.

    Pass a real :class:`~tradingagents.portfolio.schemas.Portfolio` to cover
    every holding. Without one, falls back to the two-name NVDA/AAPL demo.
    """
    if portfolio is not None and getattr(portfolio, "open_positions", None):
        runs, ohlcv_map = _runs_for_portfolio(portfolio, trade_date=as_of)
        if runs:
            return build_feed(
                runs, portfolio=portfolio, ohlcv_map=ohlcv_map, as_of=as_of
            )

    nvda = sample_final_state(
        "NVDA",
        rating="Underweight",
        sentiment_band="Bearish",
        sentiment_score=3.2,
        target=120.0,
        stop=132.0,
        trade_date=as_of,
    )
    aapl = sample_final_state(
        "AAPL",
        rating="Buy",
        sentiment_band="Bullish",
        sentiment_score=7.4,
        target=245.0,
        stop=205.0,
        trade_date=as_of,
    )

    class _Book:
        """Minimal portfolio stand-in: NVDA is held at 22% of the book."""

        def holds(self, s):
            return s.upper() == "NVDA"

        def weights(self):
            return {"NVDA": 0.22}

        @property
        def open_positions(self):
            return []

    return build_feed(
        [nvda, aapl],
        portfolio=portfolio or _Book(),
        ohlcv_map={
            "NVDA": sample_ohlcv(start_price=140, trend=-0.05),
            "AAPL": sample_ohlcv(start_price=210, trend=0.2),
        },
        as_of=as_of,
    )
