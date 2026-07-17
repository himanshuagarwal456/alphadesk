"""Thin yfinance OHLCV fetch for chart substrate.

Isolated here (the only network dependency in the UI layer) and fail-open:
returns ``None`` when data is unavailable so a card degrades to text instead of
breaking the feed build. Not unit-tested against the network; the deck builder
is tested with synthetic frames from :mod:`.sample`.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


def fetch_ohlcv(
    symbol: str, end_date: str | None = None, *, lookback_days: int = 180
) -> pd.DataFrame | None:
    """Fetch daily OHLCV up to ``end_date`` (default today), or None on failure."""
    try:
        import yfinance as yf

        from tradingagents.dataflows.symbol_utils import normalize_symbol

        end = datetime.strptime(end_date, "%Y-%m-%d") if end_date else datetime.now()
        start = end - timedelta(days=lookback_days)
        df = yf.Ticker(normalize_symbol(symbol)).history(
            start=start.strftime("%Y-%m-%d"),
            end=(end + timedelta(days=1)).strftime("%Y-%m-%d"),
        )
        if df is None or df.empty:
            return None
        return df
    except Exception as exc:  # noqa: BLE001 — fail-open: charts degrade to text
        logger.warning("OHLCV fetch failed for %s: %s", symbol, exc)
        return None
