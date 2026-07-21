"""Exposure normalization and security/portfolio aggregation (Batch 1)."""

from __future__ import annotations

from collections import defaultdict

from tradingagents.factor_intelligence.catalog import default_factor_definitions
from tradingagents.factor_intelligence.characteristics import (
    compute_characteristics,
    impute_with_median,
    mean_ignore_none,
    standardize,
    winsorize,
)
from tradingagents.factor_intelligence.schemas import (
    FactorModelVersion,
    PortfolioFactorExposure,
    SecurityFactorExposure,
    SecurityFundamentalSnapshot,
)
from tradingagents.portfolio.schemas import Portfolio

_SECTOR_MAP = {
    "technology": "SECTOR_TECHNOLOGY",
    "information technology": "SECTOR_TECHNOLOGY",
    "financial services": "SECTOR_FINANCIALS",
    "financials": "SECTOR_FINANCIALS",
    "healthcare": "SECTOR_HEALTHCARE",
    "health care": "SECTOR_HEALTHCARE",
    "energy": "SECTOR_ENERGY",
    "consumer cyclical": "SECTOR_CONSUMER",
    "consumer defensive": "SECTOR_CONSUMER",
    "consumer staples": "SECTOR_CONSUMER",
    "consumer discretionary": "SECTOR_CONSUMER",
    "industrials": "SECTOR_INDUSTRIALS",
    "utilities": "SECTOR_UTILITIES",
    "real estate": "SECTOR_REAL_ESTATE",
    "basic materials": "SECTOR_MATERIALS",
    "materials": "SECTOR_MATERIALS",
    "communication services": "SECTOR_COMMUNICATION",
}


def _sector_factor_code(sector: str | None) -> str:
    if not sector:
        return "SECTOR_OTHER"
    return _SECTOR_MAP.get(sector.strip().lower(), "SECTOR_OTHER")


def _composite(parts: list[float | None]) -> float | None:
    return mean_ignore_none(parts)


def build_security_exposures(
    snapshots: list[SecurityFundamentalSnapshot],
    *,
    model: FactorModelVersion,
    winsorize_pct: float = 0.025,
) -> list[SecurityFactorExposure]:
    """Build cross-sectionally standardized exposures for a universe."""
    if not snapshots:
        return []
    factors = {f.code: f for f in (model.factor_definitions or default_factor_definitions())}
    # descriptor matrix: code -> list aligned with snapshots
    char_rows = [
        {
            c.descriptor_code: c.raw_value
            for c in compute_characteristics(s, model_version_id=model.id or "")
        }
        for s in snapshots
    ]
    descriptor_codes = sorted({k for row in char_rows for k in row})
    zscores: dict[str, list[float]] = {}
    for code in descriptor_codes:
        raw = [row.get(code) for row in char_rows]
        clipped = winsorize(raw, pct=winsorize_pct)
        filled = impute_with_median(clipped)
        # re-standardize after imputation
        std = standardize(filled)
        zscores[code] = [float(v or 0.0) for v in std]

    style_composites = {
        "SIZE": ["LOG_MARKET_CAP"],  # invert later: small = high size factor
        "VALUE": ["BOOK_TO_PRICE", "EARNINGS_YIELD"],
        "GROWTH": ["REVENUE_GROWTH", "EARNINGS_GROWTH"],
        "MOMENTUM": ["MOMENTUM_12_1", "MOMENTUM_6M"],
        "QUALITY": ["ROE", "ROA", "GROSS_PROFITABILITY"],
        "LOW_VOLATILITY": ["HIST_VOLATILITY", "MARKET_BETA"],  # invert
        "LIQUIDITY": ["AVG_DOLLAR_VOLUME"],
        "DIVIDEND_YIELD": ["DIVIDEND_YIELD"],
        "MARKET": ["MARKET_BETA"],
    }

    out: list[SecurityFactorExposure] = []
    for idx, snap in enumerate(snapshots):
        conf = snap.source_quality
        for factor_code, desc_list in style_composites.items():
            factor = factors.get(factor_code)
            if factor is None or not factor.id:
                continue
            parts = [zscores[d][idx] if d in zscores else None for d in desc_list]
            score = _composite(parts)
            if score is None:
                score = 0.0
            # Size: smaller caps -> higher Size score (invert log cap)
            if factor_code == "SIZE":
                score = -score
            # Low vol: lower vol/beta -> higher Low Volatility score
            if factor_code == "LOW_VOLATILITY":
                score = -score
            out.append(
                SecurityFactorExposure(
                    model_version_id=model.id or "",
                    effective_date=snap.as_of,
                    security_id=snap.symbol,
                    symbol=snap.symbol,
                    factor_id=factor.id,
                    factor_code=factor.code,
                    raw_value=score,
                    normalized_exposure=float(score),
                    confidence=conf,
                    source_quality=snap.source_quality,
                )
            )
        # Sector binary
        sector_code = _sector_factor_code(snap.sector)
        for code, factor in factors.items():
            if factor.category.value != "sector" or not factor.id:
                continue
            exposure = 1.0 if code == sector_code else 0.0
            out.append(
                SecurityFactorExposure(
                    model_version_id=model.id or "",
                    effective_date=snap.as_of,
                    security_id=snap.symbol,
                    symbol=snap.symbol,
                    factor_id=factor.id,
                    factor_code=factor.code,
                    raw_value=exposure,
                    normalized_exposure=exposure,
                    confidence=conf if snap.sector else 0.4,
                    source_quality=snap.source_quality,
                )
            )
    return out


def aggregate_portfolio_exposures(
    *,
    portfolio: Portfolio,
    security_exposures: list[SecurityFactorExposure],
    model: FactorModelVersion,
    workspace_id: str,
    portfolio_id: str,
    effective_date: str,
    benchmark_exposures: dict[str, float] | None = None,
) -> tuple[list[PortfolioFactorExposure], float, list[str]]:
    """Weight-average security exposures to portfolio factor exposures."""
    weights = portfolio.weights()
    by_symbol: dict[str, list[SecurityFactorExposure]] = defaultdict(list)
    for exp in security_exposures:
        by_symbol[exp.symbol].append(exp)

    modeled = [s for s in weights if s in by_symbol]
    unmodeled = sorted(s for s in weights if s not in by_symbol)
    modeled_weight = sum(weights[s] for s in modeled)
    coverage = float(modeled_weight) if weights else 0.0

    factors = {f.code: f for f in model.factor_definitions}
    # factor_code -> weighted sum
    accum: dict[str, float] = defaultdict(float)
    contrib: dict[str, list[str]] = defaultdict(list)
    for symbol in modeled:
        w = weights[symbol]
        # renormalize within modeled book so exposures are interpretable when coverage < 1
        wn = w / modeled_weight if modeled_weight > 0 else 0.0
        for exp in by_symbol[symbol]:
            accum[exp.factor_code] += wn * exp.normalized_exposure
            if abs(exp.normalized_exposure) > 0.25:
                contrib[exp.factor_code].append(symbol)

    out: list[PortfolioFactorExposure] = []
    for code, value in sorted(accum.items()):
        factor = factors.get(code)
        if factor is None or not factor.id:
            continue
        bench = (benchmark_exposures or {}).get(code)
        active = (value - bench) if bench is not None else None
        out.append(
            PortfolioFactorExposure(
                portfolio_id=portfolio_id,
                workspace_id=workspace_id,
                model_version_id=model.id or "",
                effective_date=effective_date,
                factor_id=factor.id,
                factor_code=factor.code,
                factor_name=factor.name,
                category=factor.category,
                portfolio_exposure=round(value, 6),
                benchmark_exposure=None if bench is None else round(bench, 6),
                active_exposure=None if active is None else round(active, 6),
                coverage=round(coverage, 6),
                contributing_symbols=sorted(set(contrib.get(code, [])))[:12],
            )
        )
    return out, coverage, unmodeled
