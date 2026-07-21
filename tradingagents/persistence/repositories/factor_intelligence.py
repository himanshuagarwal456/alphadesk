"""Factor intelligence persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.factor_intelligence.schemas import (
    FactorDefinition,
    FactorModelVersion,
    PortfolioFactorExposure,
    SecurityFactorExposure,
)

from ..models import (
    FactorDefinitionRow,
    FactorModelVersionRow,
    PortfolioFactorExposureRow,
    SecurityFactorExposureRow,
)


class FactorIntelligenceRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_factor(self, factor: FactorDefinition) -> FactorDefinition:
        data = factor.model_dump(mode="json")
        row = self._session.scalars(
            select(FactorDefinitionRow).where(FactorDefinitionRow.id == factor.id)
        ).first()
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                FactorDefinitionRow(
                    id=factor.id,
                    code=factor.code,
                    name=factor.name,
                    category=factor.category.value,
                    status=factor.status,
                    payload=data,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            row.code = factor.code
            row.name = factor.name
            row.category = factor.category.value
            row.status = factor.status
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return factor

    def list_factors(self) -> list[FactorDefinition]:
        rows = self._session.scalars(
            select(FactorDefinitionRow).order_by(FactorDefinitionRow.code.asc())
        )
        return [FactorDefinition.model_validate(row.payload) for row in rows]

    def save_model(self, model: FactorModelVersion) -> FactorModelVersion:
        data = model.model_dump(mode="json")
        row = self._session.scalars(
            select(FactorModelVersionRow).where(FactorModelVersionRow.id == model.id)
        ).first()
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                FactorModelVersionRow(
                    id=model.id,
                    name=model.name,
                    version=model.version,
                    status=model.status.value,
                    effective_date=model.effective_date,
                    payload=data,
                    created_at=model.created_at,
                    updated_at=now,
                )
            )
        else:
            row.status = model.status.value
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return model

    def get_model(self, version_id: str) -> FactorModelVersion | None:
        row = self._session.scalars(
            select(FactorModelVersionRow).where(FactorModelVersionRow.id == version_id)
        ).first()
        if row is None:
            return None
        return FactorModelVersion.model_validate(row.payload)

    def get_active_model(self) -> FactorModelVersion | None:
        row = self._session.scalars(
            select(FactorModelVersionRow)
            .where(FactorModelVersionRow.status == "active")
            .order_by(FactorModelVersionRow.created_at.desc())
        ).first()
        if row is None:
            return None
        return FactorModelVersion.model_validate(row.payload)

    def list_models(self) -> list[FactorModelVersion]:
        rows = self._session.scalars(
            select(FactorModelVersionRow).order_by(FactorModelVersionRow.created_at.desc())
        )
        return [FactorModelVersion.model_validate(row.payload) for row in rows]

    def save_security_exposures(self, exposures: list[SecurityFactorExposure]) -> None:
        for exp in exposures:
            data = exp.model_dump(mode="json")
            row_id = f"{exp.model_version_id}:{exp.symbol}:{exp.factor_code}:{exp.effective_date}"
            existing = self._session.scalars(
                select(SecurityFactorExposureRow).where(
                    SecurityFactorExposureRow.id == row_id
                )
            ).first()
            if existing is None:
                self._session.add(
                    SecurityFactorExposureRow(
                        id=row_id,
                        model_version_id=exp.model_version_id,
                        symbol=exp.symbol,
                        factor_code=exp.factor_code,
                        effective_date=exp.effective_date,
                        payload=data,
                    )
                )
            else:
                existing.payload = data
        self._session.flush()

    def save_portfolio_exposures(self, exposures: list[PortfolioFactorExposure]) -> None:
        for exp in exposures:
            data = exp.model_dump(mode="json")
            row_id = (
                f"{exp.workspace_id}:{exp.portfolio_id}:{exp.model_version_id}:"
                f"{exp.factor_code}:{exp.effective_date}"
            )
            existing = self._session.scalars(
                select(PortfolioFactorExposureRow).where(
                    PortfolioFactorExposureRow.id == row_id
                )
            ).first()
            if existing is None:
                self._session.add(
                    PortfolioFactorExposureRow(
                        id=row_id,
                        workspace_id=exp.workspace_id,
                        portfolio_id=exp.portfolio_id,
                        model_version_id=exp.model_version_id,
                        factor_code=exp.factor_code,
                        effective_date=exp.effective_date,
                        payload=data,
                    )
                )
            else:
                existing.payload = data
        self._session.flush()
