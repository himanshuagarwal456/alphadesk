"""Factor model and portfolio factor-exposure APIs (Batch 1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.factor_intelligence.schemas import (
    FactorDefinition,
    FactorModelVersion,
    PortfolioFactorExposureReport,
)
from tradingagents.factor_intelligence.service import FactorIntelligenceService

router = APIRouter(prefix="/factor-models")


@router.get("", response_model=list[FactorModelVersion])
def list_factor_models(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[FactorModelVersion]:
    return FactorIntelligenceService(session, workspace_id=workspace_id).list_models()


@router.get("/factors", response_model=list[FactorDefinition])
def list_factors(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[FactorDefinition]:
    return FactorIntelligenceService(session, workspace_id=workspace_id).list_factors()


@router.get("/{version_id}", response_model=FactorModelVersion)
def get_factor_model(
    version_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> FactorModelVersion:
    model = FactorIntelligenceService(session, workspace_id=workspace_id).get_model(
        version_id
    )
    if model is None:
        raise HTTPException(status_code=404, detail="factor model not found")
    return model


portfolio_factors_router = APIRouter(prefix="/portfolios")


@portfolio_factors_router.get(
    "/current/factor-exposures",
    response_model=PortfolioFactorExposureReport,
)
def current_factor_exposures(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    as_of: str | None = None,
    model_version: str | None = Query(default=None, alias="model_version"),
) -> PortfolioFactorExposureReport:
    try:
        return FactorIntelligenceService(
            session, workspace_id=workspace_id
        ).analyze_current_portfolio(as_of=as_of, model_version_id=model_version)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
