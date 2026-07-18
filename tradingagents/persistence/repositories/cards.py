"""Intelligence card repository."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.domain.schemas import IntelligenceCardRecord

from ..models import IntelligenceCardRow
from .workspaces import WorkspaceRepository


class IntelligenceCardRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(
        self,
        card: IntelligenceCardRecord,
        *,
        workspace_id: str | None = None,
    ) -> IntelligenceCardRecord:
        ws = workspace_id or card.workspace_id
        WorkspaceRepository(self._session).ensure(ws)
        payload = card.model_copy(update={"workspace_id": ws})
        data = payload.model_dump(mode="json")
        row = self._session.scalars(
            select(IntelligenceCardRow).where(
                IntelligenceCardRow.workspace_id == ws,
                IntelligenceCardRow.id == payload.id,
            )
        ).first()
        if row is None:
            self._session.add(
                IntelligenceCardRow(
                    id=payload.id,
                    workspace_id=ws,
                    symbol=payload.symbol,
                    card_type=payload.card_type,
                    title=payload.title,
                    payload=data,
                    created_at=payload.created_at,
                )
            )
        else:
            row.symbol = payload.symbol
            row.card_type = payload.card_type
            row.title = payload.title
            row.payload = data
        self._session.flush()
        return payload

    def get(self, workspace_id: str, card_id: str) -> IntelligenceCardRecord | None:
        row = self._session.scalars(
            select(IntelligenceCardRow).where(
                IntelligenceCardRow.workspace_id == workspace_id,
                IntelligenceCardRow.id == card_id,
            )
        ).first()
        if row is None:
            return None
        return IntelligenceCardRecord.model_validate(row.payload)

    def list(
        self,
        workspace_id: str,
        *,
        symbol: str | None = None,
        limit: int = 100,
    ) -> list[IntelligenceCardRecord]:
        stmt = select(IntelligenceCardRow).where(
            IntelligenceCardRow.workspace_id == workspace_id
        )
        if symbol:
            stmt = stmt.where(IntelligenceCardRow.symbol == symbol.strip().upper())
        stmt = stmt.order_by(IntelligenceCardRow.created_at.desc()).limit(limit)
        return [
            IntelligenceCardRecord.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]
