"""Deterministic sample data so the feed can be demoed/tested without a live run.

``sample_feed()`` builds a multi-story feed (desk brief + theme arcs) from
synthetic OHLCV and canned ``final_state`` dicts, so `alphadesk-feed --demo`
shows the full UX with no API spend or network.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from tradingagents.evidence import Evidence

from .deck_builder import build_feed
from .feed_schema import Feed


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
) -> dict:
    """A canned run state shaped like a real ``final_state``."""
    state = {
        "company_of_interest": symbol,
        "trade_date": "2026-01-15",
        "market_report": (
            f"{symbol} broke below its 50-day moving average on above-average volume, "
            "a bearish signal. RSI is rolling over from overbought territory and MACD "
            "has crossed negative."
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


def sample_feed() -> Feed:
    """Desk brief + theme stories from a held bearish name and a bullish candidate."""
    nvda = sample_final_state("NVDA", rating="Underweight", sentiment_band="Bearish",
                              sentiment_score=3.2, target=120.0, stop=132.0)
    aapl = sample_final_state("AAPL", rating="Buy", sentiment_band="Bullish",
                              sentiment_score=7.4, target=245.0, stop=205.0)
    aapl["market_report"] = ("AAPL is holding above a rising 50-day average with improving "
                             "breadth; MACD turned positive.")

    class _Book:
        """Minimal portfolio stand-in: NVDA is held at 22% of the book."""

        def holds(self, s):
            return s.upper() == "NVDA"

        def weights(self):
            return {"NVDA": 0.22}

    return build_feed(
        [nvda, aapl],
        portfolio=_Book(),
        ohlcv_map={"NVDA": sample_ohlcv(start_price=140, trend=-0.05),
                   "AAPL": sample_ohlcv(start_price=210, trend=0.2)},
        as_of="2026-01-15",
    )
