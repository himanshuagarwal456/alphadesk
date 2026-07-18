"""Watchlist and workspace portfolio-state repositories."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.portfolio.product import PortfolioControls, Watchlist

from ..models import WatchlistRow, WorkspacePortfolioStateRow
from .workspaces import WorkspaceRepository


class PortfolioStateRepository:
    def __init__(self, session: Session):
        self._session = session

    def get_controls(self, workspace_id: str) -> PortfolioControls:
        row = self._session.get(WorkspacePortfolioStateRow, workspace_id)
        if row is None:
            return PortfolioControls()
        return PortfolioControls(
            monitoring_enabled=row.monitoring_enabled == "true",
            research_only=True,
            current_snapshot_id=row.current_snapshot_id,
        )

    def set_controls(
        self,
        workspace_id: str,
        controls: PortfolioControls,
    ) -> PortfolioControls:
        WorkspaceRepository(self._session).ensure(workspace_id)
        forced = controls.model_copy(update={"research_only": True})
        row = self._session.get(WorkspacePortfolioStateRow, workspace_id)
        if row is None:
            self._session.add(
                WorkspacePortfolioStateRow(
                    workspace_id=workspace_id,
                    current_snapshot_id=forced.current_snapshot_id,
                    monitoring_enabled="true" if forced.monitoring_enabled else "false",
                    payload=forced.model_dump(mode="json"),
                )
            )
        else:
            row.current_snapshot_id = forced.current_snapshot_id
            row.monitoring_enabled = "true" if forced.monitoring_enabled else "false"
            row.payload = forced.model_dump(mode="json")
            row.updated_at = datetime.now(timezone.utc)
        self._session.flush()
        return forced


class WatchlistRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, watchlist: Watchlist, *, workspace_id: str) -> Watchlist:
        WorkspaceRepository(self._session).ensure(workspace_id)
        now = datetime.now(timezone.utc)
        payload = Watchlist(
            id=watchlist.id,
            name=watchlist.name,
            workspace_id=workspace_id,
            items=watchlist.items,
            created_at=watchlist.created_at,
            updated_at=now,
        )
        data = payload.model_dump(mode="json")
        row = self._session.scalars(
            select(WatchlistRow).where(
                WatchlistRow.workspace_id == workspace_id,
                WatchlistRow.id == payload.id,
            )
        ).first()
        if row is None:
            self._session.add(
                WatchlistRow(
                    id=payload.id,
                    workspace_id=workspace_id,
                    name=payload.name,
                    payload=data,
                    created_at=payload.created_at,
                    updated_at=payload.updated_at,
                )
            )
        else:
            row.name = payload.name
            row.payload = data
            row.updated_at = payload.updated_at
        self._session.flush()
        return payload

    def get(self, workspace_id: str, watchlist_id: str) -> Watchlist | None:
        row = self._session.scalars(
            select(WatchlistRow).where(
                WatchlistRow.workspace_id == workspace_id,
                WatchlistRow.id == watchlist_id,
            )
        ).first()
        if row is None:
            return None
        return Watchlist.model_validate(row.payload)

    def list(self, workspace_id: str, *, limit: int = 50) -> list[Watchlist]:
        stmt = (
            select(WatchlistRow)
            .where(WatchlistRow.workspace_id == workspace_id)
            .order_by(WatchlistRow.updated_at.desc())
            .limit(limit)
        )
        return [Watchlist.model_validate(row.payload) for row in self._session.scalars(stmt)]

    def delete(self, workspace_id: str, watchlist_id: str) -> bool:
        row = self._session.scalars(
            select(WatchlistRow).where(
                WatchlistRow.workspace_id == workspace_id,
                WatchlistRow.id == watchlist_id,
            )
        ).first()
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
