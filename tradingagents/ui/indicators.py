"""Pure technical-indicator math on OHLCV frames.

Kept free of any plotting or network dependency so it is trivially unit-tested
with synthetic data and reusable outside the dashboard. Every function takes a
pandas Series/DataFrame and returns one, with the same index, so results align
for overlay plotting.
"""

from __future__ import annotations

import pandas as pd


def sma(close: pd.Series, window: int = 20) -> pd.Series:
    """Simple moving average."""
    return close.rolling(window=window, min_periods=1).mean()


def ema(close: pd.Series, span: int = 20) -> pd.Series:
    """Exponential moving average."""
    return close.ewm(span=span, adjust=False).mean()


def rsi(close: pd.Series, window: int = 14) -> pd.Series:
    """Relative Strength Index (Wilder's smoothing), returned on a 0–100 scale."""
    delta = close.diff()
    gain = delta.clip(lower=0.0)
    loss = -delta.clip(upper=0.0)
    avg_gain = gain.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / window, min_periods=window, adjust=False).mean()
    rs = avg_gain / avg_loss
    result = 100.0 - (100.0 / (1.0 + rs))
    # When there are no losses in the window, RSI is 100 (avoid inf/NaN artifacts).
    result = result.where(avg_loss != 0, 100.0)
    return result.rename("rsi")


def macd(
    close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9
) -> pd.DataFrame:
    """MACD line, signal line, and histogram."""
    macd_line = ema(close, fast) - ema(close, slow)
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    return pd.DataFrame(
        {
            "macd": macd_line,
            "signal": signal_line,
            "hist": macd_line - signal_line,
        }
    )


def bollinger(
    close: pd.Series, window: int = 20, num_std: float = 2.0
) -> pd.DataFrame:
    """Bollinger bands: middle SMA plus upper/lower standard-deviation envelopes."""
    mid = sma(close, window)
    std = close.rolling(window=window, min_periods=1).std(ddof=0)
    return pd.DataFrame(
        {
            "mid": mid,
            "upper": mid + num_std * std,
            "lower": mid - num_std * std,
        }
    )
