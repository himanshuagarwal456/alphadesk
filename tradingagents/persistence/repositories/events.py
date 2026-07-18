"""Run-event stream repository for UI progress."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from tradingagents.domain.schemas import RunEvent

from ..models import RunEventRow
from .workspaces import WorkspaceRepository


class RunEventRepository:
    def __init__(self, session: Session):
        self._session = session

    def append(
        self,
        *,
        workspace_id: str,
        analysis_run_id: str,
        event_type: str,
        message: str = "",
        payload: dict | None = None,
    ) -> RunEvent:
        WorkspaceRepository(self._session).ensure(workspace_id)
        next_seq = (
            self._session.scalar(
                select(func.coalesce(func.max(RunEventRow.sequence), -1)).where(
                    RunEventRow.workspace_id == workspace_id,
                    RunEventRow.analysis_run_id == analysis_run_id,
                )
            )
            + 1
        )
        event = RunEvent(
            analysis_run_id=analysis_run_id,
            workspace_id=workspace_id,
            sequence=next_seq,
            event_type=event_type,
            message=message,
            payload=payload or {},
        )
        self._session.add(
            RunEventRow(
                id=event.id,
                workspace_id=workspace_id,
                analysis_run_id=analysis_run_id,
                sequence=event.sequence,
                event_type=event.event_type,
                message=event.message,
                payload=event.payload,
                created_at=event.created_at,
            )
        )
        self._session.flush()
        return event

    def list_for_run(
        self,
        workspace_id: str,
        analysis_run_id: str,
        *,
        after_sequence: int | None = None,
        limit: int = 500,
    ) -> list[RunEvent]:
        stmt = select(RunEventRow).where(
            RunEventRow.workspace_id == workspace_id,
            RunEventRow.analysis_run_id == analysis_run_id,
        )
        if after_sequence is not None:
            stmt = stmt.where(RunEventRow.sequence > after_sequence)
        stmt = stmt.order_by(RunEventRow.sequence.asc()).limit(limit)
        return [
            RunEvent(
                id=row.id,
                analysis_run_id=row.analysis_run_id,
                workspace_id=row.workspace_id,
                sequence=row.sequence,
                event_type=row.event_type,
                message=row.message,
                payload=row.payload or {},
                created_at=row.created_at,
            )
            for row in self._session.scalars(stmt)
        ]
