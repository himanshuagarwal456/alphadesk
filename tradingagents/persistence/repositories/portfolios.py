"""Portfolio snapshot repository."""

from __future__ import annotations

from hashlib import sha256

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.portfolio.schemas import Portfolio

from ..models import PortfolioSnapshotRow
from .workspaces import WorkspaceRepository


def portfolio_snapshot_id(workspace_id: str, portfolio: Portfolio) -> str:
    as_of = portfolio.as_of or "undated"
    digest = sha256(f"{workspace_id}|{as_of}|{len(portfolio.positions)}".encode()).hexdigest()[:20]
    return f"ps_{digest}"


class PortfolioRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(
        self,
        portfolio: Portfolio,
        *,
        workspace_id: str,
        snapshot_id: str | None = None,
    ) -> tuple[str, Portfolio]:
        WorkspaceRepository(self._session).ensure(workspace_id)
        sid = snapshot_id or portfolio_snapshot_id(workspace_id, portfolio)
        payload = portfolio.model_dump(mode="json")
        row = self._session.scalars(
            select(PortfolioSnapshotRow).where(
                PortfolioSnapshotRow.workspace_id == workspace_id,
                PortfolioSnapshotRow.id == sid,
            )
        ).first()
        if row is None:
            self._session.add(
                PortfolioSnapshotRow(
                    id=sid,
                    workspace_id=workspace_id,
                    as_of=portfolio.as_of,
                    payload=payload,
                )
            )
        else:
            row.as_of = portfolio.as_of
            row.payload = payload
        self._session.flush()
        return sid, portfolio

    def get(self, workspace_id: str, snapshot_id: str) -> Portfolio | None:
        row = self._session.scalars(
            select(PortfolioSnapshotRow).where(
                PortfolioSnapshotRow.workspace_id == workspace_id,
                PortfolioSnapshotRow.id == snapshot_id,
            )
        ).first()
        if row is None:
            return None
        return Portfolio.model_validate(row.payload)

    def list(self, workspace_id: str, *, limit: int = 50) -> list[tuple[str, Portfolio]]:
        stmt = (
            select(PortfolioSnapshotRow)
            .where(PortfolioSnapshotRow.workspace_id == workspace_id)
            .order_by(PortfolioSnapshotRow.created_at.desc())
            .limit(limit)
        )
        return [
            (row.id, Portfolio.model_validate(row.payload))
            for row in self._session.scalars(stmt)
        ]

    def delete(self, workspace_id: str, snapshot_id: str) -> bool:
        row = self._session.scalars(
            select(PortfolioSnapshotRow).where(
                PortfolioSnapshotRow.workspace_id == workspace_id,
                PortfolioSnapshotRow.id == snapshot_id,
            )
        ).first()
        if row is None:
            return False
        self._session.delete(row)
        self._session.flush()
        return True
