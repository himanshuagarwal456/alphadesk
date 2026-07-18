"""Workspace repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.domain.schemas import Workspace

from ..models import WorkspaceRow


class WorkspaceRepository:
    def __init__(self, session: Session):
        self._session = session

    def ensure(self, workspace_id: str, *, name: str | None = None) -> Workspace:
        row = self._session.get(WorkspaceRow, workspace_id)
        if row is None:
            row = WorkspaceRow(id=workspace_id, name=name or workspace_id)
            self._session.add(row)
            self._session.flush()
        return Workspace(id=row.id, name=row.name, created_at=row.created_at)

    def get(self, workspace_id: str) -> Workspace | None:
        row = self._session.get(WorkspaceRow, workspace_id)
        if row is None:
            return None
        return Workspace(id=row.id, name=row.name, created_at=row.created_at)

    def list(self) -> list[Workspace]:
        rows = self._session.scalars(select(WorkspaceRow).order_by(WorkspaceRow.id)).all()
        return [Workspace(id=r.id, name=r.name, created_at=r.created_at) for r in rows]
