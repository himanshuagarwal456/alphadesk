"""Durable analysis-run repository with workspace ownership."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.domain.schemas import AnalysisRun, RunStatus

from ..models import AnalysisRunRow
from .workspaces import WorkspaceRepository


class AnalysisRunRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, run: AnalysisRun, *, workspace_id: str | None = None) -> AnalysisRun:
        ws = workspace_id or run.workspace_id
        if not ws:
            raise ValueError("workspace_id is required to persist an analysis run")
        WorkspaceRepository(self._session).ensure(ws)
        payload = run.model_copy(update={"workspace_id": ws})
        row = self._session.scalars(
            select(AnalysisRunRow).where(
                AnalysisRunRow.workspace_id == ws,
                AnalysisRunRow.id == payload.id,
            )
        ).first()
        now = datetime.now(timezone.utc)
        data = payload.model_dump(mode="json")
        if row is None:
            row = AnalysisRunRow(
                id=payload.id,
                workspace_id=ws,
                symbol=payload.symbol,
                trade_date=payload.trade_date,
                status=payload.status.value,
                payload=data,
                created_at=payload.created_at,
                updated_at=now,
            )
            self._session.add(row)
        else:
            row.symbol = payload.symbol
            row.trade_date = payload.trade_date
            row.status = payload.status.value
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return payload

    def get(self, workspace_id: str, run_id: str) -> AnalysisRun | None:
        row = self._session.scalars(
            select(AnalysisRunRow).where(
                AnalysisRunRow.workspace_id == workspace_id,
                AnalysisRunRow.id == run_id,
            )
        ).first()
        if row is None:
            return None
        return AnalysisRun.model_validate(row.payload)

    def list(
        self,
        workspace_id: str,
        *,
        symbol: str | None = None,
        status: RunStatus | None = None,
        limit: int = 100,
    ) -> list[AnalysisRun]:
        stmt = select(AnalysisRunRow).where(AnalysisRunRow.workspace_id == workspace_id)
        if symbol:
            stmt = stmt.where(AnalysisRunRow.symbol == symbol.strip().upper())
        if status is not None:
            stmt = stmt.where(AnalysisRunRow.status == status.value)
        stmt = stmt.order_by(AnalysisRunRow.created_at.desc()).limit(limit)
        return [AnalysisRun.model_validate(row.payload) for row in self._session.scalars(stmt)]

    def update_status(
        self,
        workspace_id: str,
        run_id: str,
        status: RunStatus,
        *,
        error: str | None = None,
    ) -> AnalysisRun | None:
        run = self.get(workspace_id, run_id)
        if run is None:
            return None
        updates: dict = {"status": status}
        now = datetime.now(timezone.utc)
        if status is RunStatus.RUNNING and run.started_at is None:
            updates["started_at"] = now
        if status in {RunStatus.COMPLETED, RunStatus.FAILED, RunStatus.CANCELLED}:
            updates["completed_at"] = now
        if error is not None:
            updates["error"] = error
        return self.save(run.model_copy(update=updates), workspace_id=workspace_id)
