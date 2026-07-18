"""Private document repository."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.research import PrivateDocument

from ..models import PrivateDocumentRow
from .workspaces import WorkspaceRepository


class PrivateDocumentRepository:
    def __init__(self, session: Session):
        self._session = session

    def save(self, document: PrivateDocument, *, workspace_id: str) -> PrivateDocument:
        WorkspaceRepository(self._session).ensure(workspace_id)
        payload = document.model_copy(update={"workspace_id": workspace_id})
        data = payload.model_dump(mode="json")
        row = self._session.scalars(
            select(PrivateDocumentRow).where(
                PrivateDocumentRow.workspace_id == workspace_id,
                PrivateDocumentRow.id == payload.id,
            )
        ).first()
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                PrivateDocumentRow(
                    id=payload.id,
                    workspace_id=workspace_id,
                    content_hash=payload.content_hash,
                    title=payload.title,
                    deleted="true" if payload.deleted else "false",
                    payload=data,
                    created_at=payload.created_at,
                    updated_at=now,
                )
            )
        else:
            row.content_hash = payload.content_hash
            row.title = payload.title
            row.deleted = "true" if payload.deleted else "false"
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return payload

    def get(self, workspace_id: str, document_id: str) -> PrivateDocument | None:
        row = self._session.scalars(
            select(PrivateDocumentRow).where(
                PrivateDocumentRow.workspace_id == workspace_id,
                PrivateDocumentRow.id == document_id,
            )
        ).first()
        if row is None:
            return None
        return PrivateDocument.model_validate(row.payload)

    def find_by_hash(
        self, workspace_id: str, content_hash: str
    ) -> PrivateDocument | None:
        row = self._session.scalars(
            select(PrivateDocumentRow).where(
                PrivateDocumentRow.workspace_id == workspace_id,
                PrivateDocumentRow.content_hash == content_hash,
            )
        ).first()
        if row is None:
            return None
        return PrivateDocument.model_validate(row.payload)

    def list(
        self,
        workspace_id: str,
        *,
        include_deleted: bool = False,
        limit: int = 200,
    ) -> list[PrivateDocument]:
        stmt = select(PrivateDocumentRow).where(
            PrivateDocumentRow.workspace_id == workspace_id
        )
        if not include_deleted:
            stmt = stmt.where(PrivateDocumentRow.deleted == "false")
        stmt = stmt.order_by(PrivateDocumentRow.created_at.desc()).limit(limit)
        return [
            PrivateDocument.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]
