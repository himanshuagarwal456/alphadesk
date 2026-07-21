"""Immutable V1 factor catalog and model version helpers."""

from __future__ import annotations

from datetime import date

from tradingagents.factor_intelligence.schemas import (
    ExposureType,
    FactorCategory,
    FactorDefinition,
    FactorModelVersion,
    ModelStatus,
)

METHODOLOGY_VERSION = "factor-intelligence-batch1"
MODEL_NAME = "alphadesk-us-equity-v1"
MODEL_VERSION = "1.0.0"


def default_factor_definitions() -> list[FactorDefinition]:
    """Initial Batch 1 factors from the product spec."""
    defs = [
        FactorDefinition(
            code="MARKET",
            name="Market",
            category=FactorCategory.MARKET,
            description="Broad equity market exposure (beta proxy).",
            exposure_type=ExposureType.CONTINUOUS,
        ),
        FactorDefinition(
            code="SIZE",
            name="Size",
            category=FactorCategory.STYLE,
            description="Log market-cap style factor (smaller = higher Size score).",
        ),
        FactorDefinition(
            code="VALUE",
            name="Value",
            category=FactorCategory.STYLE,
            description="Composite of book-to-price and earnings yield.",
        ),
        FactorDefinition(
            code="GROWTH",
            name="Growth",
            category=FactorCategory.STYLE,
            description="Composite of revenue and earnings growth.",
        ),
        FactorDefinition(
            code="MOMENTUM",
            name="Momentum",
            category=FactorCategory.STYLE,
            description="Intermediate-term price momentum (12-1 / 6m).",
        ),
        FactorDefinition(
            code="QUALITY",
            name="Quality",
            category=FactorCategory.STYLE,
            description="Profitability and return-on-capital composite.",
        ),
        FactorDefinition(
            code="LOW_VOLATILITY",
            name="Low Volatility",
            category=FactorCategory.STYLE,
            description="Inverse historical volatility / beta composite.",
        ),
        FactorDefinition(
            code="LIQUIDITY",
            name="Liquidity",
            category=FactorCategory.STYLE,
            description="Average dollar volume liquidity score.",
        ),
        FactorDefinition(
            code="DIVIDEND_YIELD",
            name="Dividend Yield",
            category=FactorCategory.STYLE,
            description="Trailing dividend yield style factor.",
        ),
    ]
    # Sector binary factors commonly used in V1 narratives.
    for code, name in (
        ("SECTOR_TECHNOLOGY", "Technology"),
        ("SECTOR_FINANCIALS", "Financials"),
        ("SECTOR_HEALTHCARE", "Health Care"),
        ("SECTOR_ENERGY", "Energy"),
        ("SECTOR_CONSUMER", "Consumer"),
        ("SECTOR_INDUSTRIALS", "Industrials"),
        ("SECTOR_UTILITIES", "Utilities"),
        ("SECTOR_REAL_ESTATE", "Real Estate"),
        ("SECTOR_MATERIALS", "Materials"),
        ("SECTOR_COMMUNICATION", "Communication Services"),
        ("SECTOR_OTHER", "Other / Unclassified"),
    ):
        defs.append(
            FactorDefinition(
                code=code,
                name=name,
                category=FactorCategory.SECTOR,
                description=f"Binary sector exposure for {name}.",
                exposure_type=ExposureType.BINARY,
                unit="binary",
            )
        )
    return defs


def active_model_version(*, as_of: str | None = None) -> FactorModelVersion:
    day = as_of or date.today().isoformat()
    return FactorModelVersion(
        name=MODEL_NAME,
        version=MODEL_VERSION,
        universe="us_equity_etf",
        effective_date=day,
        methodology_version=METHODOLOGY_VERSION,
        data_cutoff=day,
        factor_definitions=default_factor_definitions(),
        estimation_parameters={
            "winsorize_pct": 0.025,
            "standardize": "cross_section_zscore",
            "missing_data": "industry_median_then_universe_median",
            "batch": 1,
        },
        status=ModelStatus.ACTIVE,
    )
