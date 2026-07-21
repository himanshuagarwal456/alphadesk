"""Monitoring persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.monitoring.schemas import (
    MonitorDefinition,
    MonitorRun,
    Notification,
    NotificationStatus,
)

from ..models import (
    AlertFingerprintRow,
    MonitorDefinitionRow,
    MonitorRunRow,
    NotificationRow,
)
from .workspaces import WorkspaceRepository


class MonitoringRepository:
    def __init__(self, session: Session):
        self._session = session

    def save_monitor(self, monitor: MonitorDefinition) -> MonitorDefinition:
        WorkspaceRepository(self._session).ensure(monitor.workspace_id)
        data = monitor.model_dump(mode="json")
        row = self._session.scalars(
            select(MonitorDefinitionRow).where(
                MonitorDefinitionRow.workspace_id == monitor.workspace_id,
                MonitorDefinitionRow.id == monitor.id,
            )
        ).first()
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                MonitorDefinitionRow(
                    id=monitor.id,
                    workspace_id=monitor.workspace_id,
                    kind=monitor.kind.value,
                    name=monitor.name,
                    enabled="true" if monitor.enabled else "false",
                    payload=data,
                    created_at=monitor.created_at,
                    updated_at=now,
                )
            )
        else:
            row.kind = monitor.kind.value
            row.name = monitor.name
            row.enabled = "true" if monitor.enabled else "false"
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return monitor

    def list_monitors(self, workspace_id: str) -> list[MonitorDefinition]:
        stmt = (
            select(MonitorDefinitionRow)
            .where(MonitorDefinitionRow.workspace_id == workspace_id)
            .order_by(MonitorDefinitionRow.name.asc())
        )
        return [
            MonitorDefinition.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]

    def save_run(self, run: MonitorRun) -> MonitorRun:
        WorkspaceRepository(self._session).ensure(run.workspace_id)
        data = run.model_dump(mode="json")
        row = self._session.scalars(
            select(MonitorRunRow).where(
                MonitorRunRow.workspace_id == run.workspace_id,
                MonitorRunRow.id == run.id,
            )
        ).first()
        if row is None:
            self._session.add(
                MonitorRunRow(
                    id=run.id,
                    workspace_id=run.workspace_id,
                    monitor_id=run.monitor_id,
                    status=run.status.value,
                    payload=data,
                    started_at=run.started_at,
                    completed_at=run.completed_at,
                )
            )
        else:
            row.status = run.status.value
            row.payload = data
            row.completed_at = run.completed_at
        self._session.flush()
        return run

    def list_runs(self, workspace_id: str, *, limit: int = 50) -> list[MonitorRun]:
        stmt = (
            select(MonitorRunRow)
            .where(MonitorRunRow.workspace_id == workspace_id)
            .order_by(MonitorRunRow.started_at.desc())
            .limit(limit)
        )
        return [MonitorRun.model_validate(row.payload) for row in self._session.scalars(stmt)]

    def has_fingerprint(self, workspace_id: str, fingerprint: str) -> bool:
        row = self._session.scalars(
            select(AlertFingerprintRow).where(
                AlertFingerprintRow.workspace_id == workspace_id,
                AlertFingerprintRow.fingerprint == fingerprint,
            )
        ).first()
        return row is not None

    def save_fingerprint(
        self,
        workspace_id: str,
        fingerprint: str,
        *,
        intelligence_card_id: str | None = None,
    ) -> None:
        WorkspaceRepository(self._session).ensure(workspace_id)
        if self.has_fingerprint(workspace_id, fingerprint):
            return
        self._session.add(
            AlertFingerprintRow(
                workspace_id=workspace_id,
                fingerprint=fingerprint,
                intelligence_card_id=intelligence_card_id,
                created_at=datetime.now(timezone.utc),
            )
        )
        self._session.flush()

    def save_notification(self, note: Notification) -> Notification:
        WorkspaceRepository(self._session).ensure(note.workspace_id)
        data = note.model_dump(mode="json")
        self._session.add(
            NotificationRow(
                id=note.id,
                workspace_id=note.workspace_id,
                status=note.status.value,
                symbol=note.symbol,
                intelligence_card_id=note.intelligence_card_id,
                payload=data,
                created_at=note.created_at,
            )
        )
        self._session.flush()
        return note

    def list_notifications(
        self,
        workspace_id: str,
        *,
        status: NotificationStatus | None = None,
        limit: int = 50,
    ) -> list[Notification]:
        stmt = select(NotificationRow).where(NotificationRow.workspace_id == workspace_id)
        if status is not None:
            stmt = stmt.where(NotificationRow.status == status.value)
        stmt = stmt.order_by(NotificationRow.created_at.desc()).limit(limit)
        return [
            Notification.model_validate(row.payload) for row in self._session.scalars(stmt)
        ]

    def update_notification_status(
        self,
        workspace_id: str,
        notification_id: str,
        *,
        status: NotificationStatus,
    ) -> Notification | None:
        row = self._session.scalars(
            select(NotificationRow).where(
                NotificationRow.workspace_id == workspace_id,
                NotificationRow.id == notification_id,
            )
        ).first()
        if row is None:
            return None
        note = Notification.model_validate(row.payload)
        note = note.model_copy(update={"status": status})
        row.status = status.value
        row.payload = note.model_dump(mode="json")
        self._session.flush()
        return note
