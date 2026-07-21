"""Factor Intelligence domain models (Batch 1)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, model_validator


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(str(p) for p in parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


class FactorCategory(str, Enum):
    MARKET = "market"
    STYLE = "style"
    SECTOR = "sector"
    INDUSTRY = "industry"
    COUNTRY = "country"
    CURRENCY = "currency"
    MACRO = "macro"


class ExposureType(str, Enum):
    CONTINUOUS = "continuous"
    CATEGORICAL = "categorical"
    BINARY = "binary"


class ModelStatus(str, Enum):
    BUILDING = "building"
    VALIDATING = "validating"
    ACTIVE = "active"
    FAILED = "failed"
    ARCHIVED = "archived"


class FactorDefinition(BaseModel):
    id: str | None = None
    code: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: FactorCategory
    description: str = ""
    exposure_type: ExposureType = ExposureType.CONTINUOUS
    unit: str = "zscore"
    status: str = "active"
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> FactorDefinition:
        self.code = self.code.strip().upper().replace(" ", "_")
        if self.id is None:
            self.id = _stable_id("fdef", self.code)
        return self


class FactorModelVersion(BaseModel):
    id: str | None = None
    name: str = "alphadesk-us-equity-v1"
    version: str = "1.0.0"
    universe: str = "us_equity_etf"
    effective_date: str
    methodology_version: str = "factor-intelligence-batch1"
    data_cutoff: str
    factor_definitions: list[FactorDefinition] = Field(default_factory=list)
    estimation_parameters: dict = Field(default_factory=dict)
    status: ModelStatus = ModelStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> FactorModelVersion:
        if self.id is None:
            self.id = _stable_id(
                "fmver",
                self.name,
                self.version,
                self.effective_date,
                self.methodology_version,
            )
        return self


class SecurityFundamentalSnapshot(BaseModel):
    """Point-in-time security inputs for characteristic calculation.

    Callers supply these values (from vendors, fixtures, or SEC facts). The
    factor engines never invent fundamentals.
    """

    symbol: str
    as_of: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    asset_type: str = "stock"
    market_cap: float | None = None
    price: float | None = None
    book_value_per_share: float | None = None
    trailing_eps: float | None = None
    free_cash_flow: float | None = None
    shares_outstanding: float | None = None
    revenue_growth: float | None = None
    earnings_growth: float | None = None
    return_on_equity: float | None = None
    return_on_assets: float | None = None
    gross_margins: float | None = None
    debt_to_equity: float | None = None
    debt_to_assets: float | None = None
    beta: float | None = None
    trailing_volatility: float | None = None
    average_dollar_volume: float | None = None
    dividend_yield: float | None = None
    momentum_12_1: float | None = None
    momentum_6m: float | None = None
    source: str = "fixture"
    source_quality: float = Field(default=0.8, ge=0, le=1)
    schema_version: int = 1

    @model_validator(mode="after")
    def _normalize(self) -> SecurityFundamentalSnapshot:
        self.symbol = self.symbol.strip().upper()
        return self


class SecurityCharacteristic(BaseModel):
    model_version_id: str
    effective_date: str
    symbol: str
    descriptor_code: str
    raw_value: float | None = None
    source_quality: float = 1.0
    schema_version: int = 1


class SecurityFactorExposure(BaseModel):
    model_version_id: str
    effective_date: str
    security_id: str
    symbol: str
    factor_id: str
    factor_code: str
    raw_value: float | None = None
    normalized_exposure: float = 0.0
    confidence: float = Field(default=1.0, ge=0, le=1)
    source_quality: float = Field(default=1.0, ge=0, le=1)
    schema_version: int = 1


class PortfolioFactorExposure(BaseModel):
    portfolio_id: str
    workspace_id: str
    model_version_id: str
    effective_date: str
    factor_id: str
    factor_code: str
    factor_name: str
    category: FactorCategory
    portfolio_exposure: float
    benchmark_exposure: float | None = None
    active_exposure: float | None = None
    coverage: float = Field(default=1.0, ge=0, le=1)
    contributing_symbols: list[str] = Field(default_factory=list)
    schema_version: int = 1


class PortfolioFactorExposureReport(BaseModel):
    """API response for portfolio factor exposures."""

    portfolio_id: str
    workspace_id: str
    model_version: FactorModelVersion
    effective_date: str
    coverage: float
    unmodeled_symbols: list[str] = Field(default_factory=list)
    exposures: list[PortfolioFactorExposure] = Field(default_factory=list)
    security_exposures: list[SecurityFactorExposure] = Field(default_factory=list)
    methodology_note: str = (
        "AlphaDesk open multi-factor model (Batch 1 exposures). "
        "Not equivalent to proprietary Barra/Axioma systems."
    )
