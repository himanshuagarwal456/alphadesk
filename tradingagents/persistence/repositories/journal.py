"""Decision-journal repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.journal.schemas import DecisionJournalEntry

from ..models import JournalEntryRow
from .workspaces import WorkspaceRepository


class JournalRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(
        self,
        entry: DecisionJournalEntry,
        *,
        workspace_id: str,
    ) -> DecisionJournalEntry:
        WorkspaceRepository(self._session).ensure(workspace_id)
        payload = entry.model_dump(mode="json")
        row = self._session.scalars(
            select(JournalEntryRow).where(
                JournalEntryRow.workspace_id == workspace_id,
                JournalEntryRow.id == entry.id,
            )
        ).first()
        if row is None:
            self._session.add(
                JournalEntryRow(
                    id=entry.id,
                    workspace_id=workspace_id,
                    symbol=entry.symbol.upper(),
                    trade_date=entry.trade_date,
                    decision_type=entry.decision_type.value,
                    payload=payload,
                    created_at=entry.created_at,
                )
            )
        else:
            row.payload = payload
            row.decision_type = entry.decision_type.value
        self._session.flush()
        return entry

    def get(self, workspace_id: str, entry_id: str) -> DecisionJournalEntry | None:
        row = self._session.scalars(
            select(JournalEntryRow).where(
                JournalEntryRow.workspace_id == workspace_id,
                JournalEntryRow.id == entry_id,
            )
        ).first()
        if row is None:
            return None
        return DecisionJournalEntry.model_validate(row.payload)

    def list(
        self,
        workspace_id: str,
        *,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[DecisionJournalEntry]:
        stmt = select(JournalEntryRow).where(JournalEntryRow.workspace_id == workspace_id)
        if symbol:
            stmt = stmt.where(JournalEntryRow.symbol == symbol.strip().upper())
        stmt = stmt.order_by(JournalEntryRow.created_at.desc()).limit(limit)
        return [
            DecisionJournalEntry.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]
