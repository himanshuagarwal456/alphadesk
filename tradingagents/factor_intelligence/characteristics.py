"""Deterministic security characteristic calculations (Batch 1)."""

from __future__ import annotations

import math
from statistics import median

from tradingagents.factor_intelligence.schemas import (
    SecurityCharacteristic,
    SecurityFundamentalSnapshot,
)

# Descriptor codes used before composite factor scores.
DESCRIPTOR_CODES = (
    "LOG_MARKET_CAP",
    "BOOK_TO_PRICE",
    "EARNINGS_YIELD",
    "REVENUE_GROWTH",
    "EARNINGS_GROWTH",
    "MOMENTUM_12_1",
    "MOMENTUM_6M",
    "ROE",
    "ROA",
    "GROSS_PROFITABILITY",
    "HIST_VOLATILITY",
    "MARKET_BETA",
    "AVG_DOLLAR_VOLUME",
    "DIVIDEND_YIELD",
)


def _safe_div(numer: float | None, denom: float | None) -> float | None:
    if numer is None or denom is None or denom == 0:
        return None
    return float(numer) / float(denom)


def compute_characteristics(
    snapshot: SecurityFundamentalSnapshot,
    *,
    model_version_id: str,
) -> list[SecurityCharacteristic]:
    """Compute raw descriptors for one security on ``snapshot.as_of``."""
    btp = None
    if snapshot.book_value_per_share is not None and snapshot.price not in (None, 0):
        btp = snapshot.book_value_per_share / snapshot.price
    ey = None
    if snapshot.trailing_eps is not None and snapshot.price not in (None, 0):
        ey = snapshot.trailing_eps / snapshot.price
    fcf_yield = None
    if (
        snapshot.free_cash_flow is not None
        and snapshot.market_cap not in (None, 0)
    ):
        fcf_yield = snapshot.free_cash_flow / snapshot.market_cap

    values = {
        "LOG_MARKET_CAP": (
            math.log(snapshot.market_cap) if snapshot.market_cap and snapshot.market_cap > 0 else None
        ),
        "BOOK_TO_PRICE": btp,
        "EARNINGS_YIELD": ey if ey is not None else fcf_yield,
        "REVENUE_GROWTH": snapshot.revenue_growth,
        "EARNINGS_GROWTH": snapshot.earnings_growth,
        "MOMENTUM_12_1": snapshot.momentum_12_1,
        "MOMENTUM_6M": snapshot.momentum_6m,
        "ROE": snapshot.return_on_equity,
        "ROA": snapshot.return_on_assets,
        "GROSS_PROFITABILITY": snapshot.gross_margins,
        "HIST_VOLATILITY": snapshot.trailing_volatility,
        "MARKET_BETA": snapshot.beta,
        "AVG_DOLLAR_VOLUME": (
            math.log(snapshot.average_dollar_volume)
            if snapshot.average_dollar_volume and snapshot.average_dollar_volume > 0
            else None
        ),
        "DIVIDEND_YIELD": snapshot.dividend_yield,
    }
    out: list[SecurityCharacteristic] = []
    for code in DESCRIPTOR_CODES:
        out.append(
            SecurityCharacteristic(
                model_version_id=model_version_id,
                effective_date=snapshot.as_of,
                symbol=snapshot.symbol,
                descriptor_code=code,
                raw_value=values.get(code),
                source_quality=snapshot.source_quality,
            )
        )
    return out


def winsorize(values: list[float | None], *, pct: float = 0.025) -> list[float | None]:
    observed = sorted(v for v in values if v is not None and math.isfinite(v))
    if len(observed) < 5:
        return values
    lo_i = min(len(observed) - 1, max(0, int(pct * len(observed))))
    hi_i = max(lo_i, min(len(observed) - 1, int((1 - pct) * len(observed)) - 1))
    lo, hi = observed[lo_i], observed[hi_i]
    out: list[float | None] = []
    for v in values:
        if v is None or not math.isfinite(v):
            out.append(None)
        else:
            out.append(min(max(v, lo), hi))
    return out


def standardize(values: list[float | None]) -> list[float | None]:
    observed = [v for v in values if v is not None and math.isfinite(v)]
    if len(observed) < 2:
        return [0.0 if v is not None else None for v in values]
    mean = sum(observed) / len(observed)
    var = sum((v - mean) ** 2 for v in observed) / len(observed)
    std = math.sqrt(var) if var > 1e-12 else 1.0
    return [
        (v - mean) / std if v is not None and math.isfinite(v) else None for v in values
    ]


def impute_with_median(values: list[float | None]) -> list[float]:
    observed = [v for v in values if v is not None and math.isfinite(v)]
    fill = float(median(observed)) if observed else 0.0
    return [float(v) if v is not None and math.isfinite(v) else fill for v in values]


def mean_ignore_none(values: list[float | None]) -> float | None:
    observed = [v for v in values if v is not None and math.isfinite(v)]
    if not observed:
        return None
    return sum(observed) / len(observed)
