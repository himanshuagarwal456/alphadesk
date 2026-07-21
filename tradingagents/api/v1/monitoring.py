"""Monitoring and notification endpoints (Phase 8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.monitoring.schemas import (
    DetectedEvent,
    MonitorDefinition,
    MonitorRun,
    Notification,
    NotificationStatus,
)
from tradingagents.monitoring.service import MonitoringService
from tradingagents.persistence.repositories import PortfolioStateRepository
from tradingagents.portfolio.product import PortfolioControls

router = APIRouter(prefix="/monitoring")


class IngestEventsRequest(BaseModel):
    events: list[DetectedEvent] = Field(default_factory=list)
    use_demo_if_empty: bool = False


class NotificationUpdateRequest(BaseModel):
    status: NotificationStatus


class MonitoringControlsUpdate(BaseModel):
    monitoring_enabled: bool


@router.get("/monitors", response_model=list[MonitorDefinition])
def list_monitors(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[MonitorDefinition]:
    return MonitoringService(session, workspace_id=workspace_id).list_monitors()


@router.post("/monitors", response_model=MonitorDefinition, status_code=201)
def save_monitor(
    body: MonitorDefinition,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> MonitorDefinition:
    body = body.model_copy(update={"workspace_id": workspace_id})
    return MonitoringService(session, workspace_id=workspace_id).save_monitor(body)


@router.post("/tick", response_model=MonitorRun)
def tick_monitoring(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    use_demo_if_empty: bool = True,
) -> MonitorRun:
    return MonitoringService(session, workspace_id=workspace_id).tick(
        use_demo_if_empty=use_demo_if_empty
    )


@router.post("/events", response_model=MonitorRun)
def ingest_events(
    body: IngestEventsRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> MonitorRun:
    return MonitoringService(session, workspace_id=workspace_id).ingest_events(
        body.events, use_demo_if_empty=body.use_demo_if_empty
    )


@router.get("/health")
def monitoring_health(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> dict:
    return MonitoringService(session, workspace_id=workspace_id).health()


@router.get("/notifications", response_model=list[Notification])
def list_notifications(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    status: NotificationStatus | None = None,
    limit: int = 50,
) -> list[Notification]:
    return MonitoringService(session, workspace_id=workspace_id).list_notifications(
        status=status, limit=limit
    )


@router.post("/notifications/{notification_id}", response_model=Notification)
def update_notification(
    notification_id: str,
    body: NotificationUpdateRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> Notification:
    note = MonitoringService(session, workspace_id=workspace_id).mark_notification(
        notification_id, status=body.status
    )
    if note is None:
        raise HTTPException(status_code=404, detail="notification not found")
    return note


@router.get("/controls", response_model=PortfolioControls)
def get_controls(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioControls:
    return PortfolioStateRepository(session).get_controls(workspace_id)


@router.put("/controls", response_model=PortfolioControls)
def update_controls(
    body: MonitoringControlsUpdate,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PortfolioControls:
    repo = PortfolioStateRepository(session)
    current = repo.get_controls(workspace_id)
    updated = current.model_copy(update={"monitoring_enabled": body.monitoring_enabled})
    return repo.set_controls(workspace_id, updated)
