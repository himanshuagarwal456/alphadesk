"""Decision-journal and outcome-review repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.journal.schemas import DecisionJournalEntry, OutcomeReview

from ..models import JournalEntryRow, OutcomeReviewRow
from .workspaces import WorkspaceRepository


class JournalRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(
        self,
        entry: DecisionJournalEntry,
        *,
        workspace_id: str,
        overwrite: bool = False,
    ) -> DecisionJournalEntry:
        """Persist a journal entry.

        Entries are append-only by default: an existing id raises unless
        ``overwrite`` is set (used only for lesson-reuse flag updates).
        """
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
        elif overwrite:
            row.payload = payload
            row.decision_type = entry.decision_type.value
        else:
            raise ValueError(
                f"journal entry {entry.id} already exists; decisions are append-only"
            )
        self._session.flush()
        return entry

    def set_lesson_reuse(
        self,
        workspace_id: str,
        entry_id: str,
        *,
        allow_lesson_reuse: bool,
    ) -> DecisionJournalEntry | None:
        entry = self.get(workspace_id, entry_id)
        if entry is None:
            return None
        updated = entry.model_copy(update={"allow_lesson_reuse": allow_lesson_reuse})
        return self.save(updated, workspace_id=workspace_id, overwrite=True)

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

    def save_outcome(
        self,
        review: OutcomeReview,
        *,
        workspace_id: str,
    ) -> OutcomeReview:
        WorkspaceRepository(self._session).ensure(workspace_id)
        if self.get(workspace_id, review.journal_entry_id) is None:
            raise KeyError("journal entry not found")
        payload = review.model_copy(update={"workspace_id": workspace_id})
        data = payload.model_dump(mode="json")
        row = self._session.scalars(
            select(OutcomeReviewRow).where(
                OutcomeReviewRow.workspace_id == workspace_id,
                OutcomeReviewRow.id == payload.id,
            )
        ).first()
        if row is None:
            self._session.add(
                OutcomeReviewRow(
                    id=payload.id,
                    workspace_id=workspace_id,
                    journal_entry_id=payload.journal_entry_id,
                    payload=data,
                    created_at=payload.reviewed_at,
                )
            )
        else:
            row.payload = data
        # Propagate lesson-reuse preference onto the decision record.
        self.set_lesson_reuse(
            workspace_id,
            payload.journal_entry_id,
            allow_lesson_reuse=payload.allow_lesson_reuse,
        )
        self._session.flush()
        return payload

    def list_outcomes(
        self,
        workspace_id: str,
        *,
        journal_entry_id: str | None = None,
        limit: int = 100,
    ) -> list[OutcomeReview]:
        stmt = select(OutcomeReviewRow).where(
            OutcomeReviewRow.workspace_id == workspace_id
        )
        if journal_entry_id:
            stmt = stmt.where(OutcomeReviewRow.journal_entry_id == journal_entry_id)
        stmt = stmt.order_by(OutcomeReviewRow.created_at.desc()).limit(limit)
        return [
            OutcomeReview.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]
