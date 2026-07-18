"""Evidence repository (workspace-scoped)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.evidence.schemas import Evidence

from ..models import EvidenceRow
from .workspaces import WorkspaceRepository


class EvidenceRepository:
    def __init__(self, session: Session):
        self._session = session

    def save_many(
        self,
        records: list[Evidence],
        *,
        workspace_id: str,
    ) -> list[Evidence]:
        WorkspaceRepository(self._session).ensure(workspace_id)
        saved: list[Evidence] = []
        for record in records:
            payload = record.model_dump(mode="json")
            row = self._session.scalars(
                select(EvidenceRow).where(
                    EvidenceRow.workspace_id == workspace_id,
                    EvidenceRow.id == record.id,
                )
            ).first()
            if row is None:
                self._session.add(
                    EvidenceRow(
                        id=record.id,
                        workspace_id=workspace_id,
                        provider_id=record.provider_id,
                        source_type=record.source_type,
                        ownership=record.ownership,
                        payload=payload,
                        created_at=record.retrieved_at,
                    )
                )
            else:
                row.provider_id = record.provider_id
                row.source_type = record.source_type
                row.ownership = record.ownership
                row.payload = payload
            saved.append(record)
        self._session.flush()
        return saved

    def get(self, workspace_id: str, evidence_id: str) -> Evidence | None:
        row = self._session.scalars(
            select(EvidenceRow).where(
                EvidenceRow.workspace_id == workspace_id,
                EvidenceRow.id == evidence_id,
            )
        ).first()
        if row is None:
            return None
        return Evidence.model_validate(row.payload)

    def list(
        self,
        workspace_id: str,
        *,
        provider_id: str | None = None,
        limit: int = 200,
    ) -> list[Evidence]:
        stmt = select(EvidenceRow).where(EvidenceRow.workspace_id == workspace_id)
        if provider_id:
            stmt = stmt.where(EvidenceRow.provider_id == provider_id)
        stmt = stmt.order_by(EvidenceRow.created_at.desc()).limit(limit)
        return [Evidence.model_validate(row.payload) for row in self._session.scalars(stmt)]
