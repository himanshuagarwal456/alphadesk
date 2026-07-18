"""Analysis-run endpoints with durable job status."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.domain.schemas import AnalysisRun, RunStatus
from tradingagents.persistence.repositories import AnalysisRunRepository, RunEventRepository

router = APIRouter(prefix="/runs")


class CreateRunRequest(BaseModel):
    symbol: str = Field(min_length=1)
    trade_date: str = Field(min_length=1)
    selected_analysts: list[str] = Field(default_factory=list)
    status: RunStatus = RunStatus.QUEUED


class UpdateStatusRequest(BaseModel):
    status: RunStatus
    error: str | None = None
    message: str | None = None


@router.post("", response_model=AnalysisRun, status_code=201)
def create_run(
    body: CreateRunRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> AnalysisRun:
    run = AnalysisRun(
        symbol=body.symbol,
        trade_date=body.trade_date,
        selected_analysts=body.selected_analysts,
        status=body.status,
        workspace_id=workspace_id,
    )
    saved = AnalysisRunRepository(session).save(run, workspace_id=workspace_id)
    RunEventRepository(session).append(
        workspace_id=workspace_id,
        analysis_run_id=saved.id,
        event_type="run.created",
        message=f"Run queued for {saved.symbol} on {saved.trade_date}",
        payload={"status": saved.status.value},
    )
    return saved


@router.get("", response_model=list[AnalysisRun])
def list_runs(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    symbol: str | None = None,
    status: RunStatus | None = None,
    limit: int = Query(default=100, ge=1, le=500),
) -> list[AnalysisRun]:
    return AnalysisRunRepository(session).list(
        workspace_id, symbol=symbol, status=status, limit=limit
    )


@router.get("/{run_id}", response_model=AnalysisRun)
def get_run(
    run_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> AnalysisRun:
    run = AnalysisRunRepository(session).get(workspace_id, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="run not found")
    return run


@router.post("/{run_id}/status", response_model=AnalysisRun)
def update_run_status(
    run_id: str,
    body: UpdateStatusRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> AnalysisRun:
    updated = AnalysisRunRepository(session).update_status(
        workspace_id, run_id, body.status, error=body.error
    )
    if updated is None:
        raise HTTPException(status_code=404, detail="run not found")
    RunEventRepository(session).append(
        workspace_id=workspace_id,
        analysis_run_id=run_id,
        event_type="run.status",
        message=body.message or f"Status -> {body.status.value}",
        payload={"status": body.status.value, "error": body.error},
    )
    return updated
