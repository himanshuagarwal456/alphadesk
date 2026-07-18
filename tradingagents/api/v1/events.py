"""Run-event stream endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.domain.schemas import RunEvent
from tradingagents.persistence.repositories import RunEventRepository

router = APIRouter(prefix="/runs/{run_id}/events")


class AppendEventRequest(BaseModel):
    event_type: str = Field(min_length=1)
    message: str = ""
    payload: dict = Field(default_factory=dict)


@router.get("", response_model=list[RunEvent])
def list_events(
    run_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    after_sequence: int | None = Query(default=None, ge=-1),
    limit: int = Query(default=500, ge=1, le=2000),
) -> list[RunEvent]:
    return RunEventRepository(session).list_for_run(
        workspace_id,
        run_id,
        after_sequence=after_sequence,
        limit=limit,
    )


@router.post("", response_model=RunEvent, status_code=201)
def append_event(
    run_id: str,
    body: AppendEventRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> RunEvent:
    return RunEventRepository(session).append(
        workspace_id=workspace_id,
        analysis_run_id=run_id,
        event_type=body.event_type,
        message=body.message,
        payload=body.payload,
    )
