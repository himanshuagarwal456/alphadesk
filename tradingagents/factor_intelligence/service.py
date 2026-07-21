"""Portfolio Factor Intelligence application service (Batch 1)."""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from tradingagents.factor_intelligence.catalog import (
    active_model_version,
    default_factor_definitions,
)
from tradingagents.factor_intelligence.exposures import (
    aggregate_portfolio_exposures,
    build_security_exposures,
)
from tradingagents.factor_intelligence.fixtures import (
    fixture_snapshot,
    fixture_universe,
    synthetic_snapshot_from_position,
)
from tradingagents.factor_intelligence.schemas import (
    FactorDefinition,
    FactorModelVersion,
    PortfolioFactorExposureReport,
    SecurityFactorExposure,
    SecurityFundamentalSnapshot,
)
from tradingagents.persistence.repositories.factor_intelligence import (
    FactorIntelligenceRepository,
)
from tradingagents.persistence.repositories.portfolios import PortfolioRepository
from tradingagents.persistence.repositories.state import PortfolioStateRepository
from tradingagents.portfolio.schemas import Portfolio
from tradingagents.portfolio.service import CURRENT_SNAPSHOT_ID


class FactorIntelligenceService:
    def __init__(self, session: Session, *, workspace_id: str):
        self._session = session
        self._workspace_id = workspace_id
        self._repo = FactorIntelligenceRepository(session)

    def ensure_catalog(self, *, as_of: str | None = None) -> FactorModelVersion:
        existing = self._repo.get_active_model()
        if existing is not None:
            return existing
        model = active_model_version(as_of=as_of or date.today().isoformat())
        for factor in model.factor_definitions:
            self._repo.upsert_factor(factor)
        return self._repo.save_model(model)

    def list_factors(self) -> list[FactorDefinition]:
        self.ensure_catalog()
        factors = self._repo.list_factors()
        return factors or default_factor_definitions()

    def list_models(self) -> list[FactorModelVersion]:
        self.ensure_catalog()
        return self._repo.list_models()

    def get_model(self, version_id: str) -> FactorModelVersion | None:
        self.ensure_catalog()
        return self._repo.get_model(version_id)

    def build_security_exposures(
        self,
        snapshots: list[SecurityFundamentalSnapshot],
        *,
        model: FactorModelVersion | None = None,
        persist: bool = True,
    ) -> list[SecurityFactorExposure]:
        model = model or self.ensure_catalog(
            as_of=snapshots[0].as_of if snapshots else None
        )
        exposures = build_security_exposures(snapshots, model=model)
        if persist:
            self._repo.save_security_exposures(exposures)
        return exposures

    def analyze_portfolio(
        self,
        portfolio: Portfolio,
        *,
        as_of: str | None = None,
        snapshots: list[SecurityFundamentalSnapshot] | None = None,
        model_version_id: str | None = None,
        portfolio_id: str | None = None,
        persist: bool = True,
    ) -> PortfolioFactorExposureReport:
        day = as_of or portfolio.as_of or date.today().isoformat()
        if model_version_id:
            model = self.get_model(model_version_id) or self.ensure_catalog(as_of=day)
        else:
            model = self.ensure_catalog(as_of=day)

        symbols = [p.symbol for p in portfolio.open_positions]
        if snapshots is None:
            snapshots = []
            for symbol in symbols:
                snap = fixture_snapshot(symbol, as_of=day)
                if snap is None:
                    pos = next(p for p in portfolio.open_positions if p.symbol == symbol)
                    snap = synthetic_snapshot_from_position(
                        symbol, as_of=day, market_value=pos.market_value
                    )
                snapshots.append(snap)
            # Enrich cross-section with fixture peers so z-scores are meaningful.
            peer_symbols = ["AAPL", "MSFT", "AMD", "NVDA", "JPM", "XOM", "NEE", "SPY", "GLD"]
            have = {s.symbol for s in snapshots}
            for peer in fixture_universe(peer_symbols, as_of=day):
                if peer.symbol not in have:
                    snapshots.append(peer)

        security_exposures = self.build_security_exposures(
            snapshots, model=model, persist=persist
        )
        # Keep only portfolio symbols in the report detail (peers used for z-score only).
        portfolio_secs = [e for e in security_exposures if e.symbol in set(symbols)]
        pid = portfolio_id or CURRENT_SNAPSHOT_ID
        exposures, coverage, unmodeled = aggregate_portfolio_exposures(
            portfolio=portfolio,
            security_exposures=portfolio_secs,
            model=model,
            workspace_id=self._workspace_id,
            portfolio_id=pid,
            effective_date=day,
        )
        if persist:
            self._repo.save_portfolio_exposures(exposures)
        return PortfolioFactorExposureReport(
            portfolio_id=pid,
            workspace_id=self._workspace_id,
            model_version=model,
            effective_date=day,
            coverage=round(coverage, 6),
            unmodeled_symbols=unmodeled,
            exposures=exposures,
            security_exposures=portfolio_secs,
        )

    def analyze_current_portfolio(
        self,
        *,
        as_of: str | None = None,
        model_version_id: str | None = None,
    ) -> PortfolioFactorExposureReport:
        controls = PortfolioStateRepository(self._session).get_controls(self._workspace_id)
        snapshot_id = controls.current_snapshot_id or CURRENT_SNAPSHOT_ID
        book = PortfolioRepository(self._session).get(self._workspace_id, snapshot_id)
        if book is None and snapshot_id != CURRENT_SNAPSHOT_ID:
            book = PortfolioRepository(self._session).get(
                self._workspace_id, CURRENT_SNAPSHOT_ID
            )
            snapshot_id = CURRENT_SNAPSHOT_ID
        if book is None:
            raise KeyError("no current portfolio")
        return self.analyze_portfolio(
            book,
            as_of=as_of or book.as_of,
            model_version_id=model_version_id,
            portfolio_id=snapshot_id,
        )
