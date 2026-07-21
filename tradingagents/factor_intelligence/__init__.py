"""Portfolio Factor Intelligence package."""

from tradingagents.factor_intelligence.schemas import (
    FactorCategory,
    FactorDefinition,
    FactorModelVersion,
    PortfolioFactorExposure,
    SecurityCharacteristic,
    SecurityFactorExposure,
    SecurityFundamentalSnapshot,
)

__all__ = [
    "FactorCategory",
    "FactorDefinition",
    "FactorIntelligenceService",
    "FactorModelVersion",
    "PortfolioFactorExposure",
    "SecurityCharacteristic",
    "SecurityFactorExposure",
    "SecurityFundamentalSnapshot",
]


def __getattr__(name: str):
    if name == "FactorIntelligenceService":
        from tradingagents.factor_intelligence.service import FactorIntelligenceService

        return FactorIntelligenceService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
