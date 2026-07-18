"""Private research ingestion service (workspace-scoped)."""

from __future__ import annotations

import hashlib

from sqlalchemy.orm import Session

from tradingagents.domain.schemas import OwnershipClass, SourceRecord
from tradingagents.evidence.schemas import Evidence
from tradingagents.persistence.object_store import LocalObjectStore
from tradingagents.persistence.repositories.evidence import EvidenceRepository
from tradingagents.persistence.repositories.research import PrivateDocumentRepository
from tradingagents.persistence.settings import load_persistence_settings

from . import DocumentSearchHit, PrivateDocument
from .ingest import validate_and_extract


class PrivateResearchService:
    def __init__(
        self,
        session: Session,
        *,
        workspace_id: str,
        object_store: LocalObjectStore | None = None,
    ):
        self._session = session
        self._workspace_id = workspace_id
        settings = load_persistence_settings()
        self._store = object_store or LocalObjectStore(settings.object_store_dir)
        self._docs = PrivateDocumentRepository(session)
        self._evidence = EvidenceRepository(session)

    def upload(
        self,
        *,
        filename: str,
        data: bytes,
        title: str | None = None,
        symbols: list[str] | None = None,
        themes: list[str] | None = None,
    ) -> PrivateDocument:
        extracted = validate_and_extract(filename=filename, data=data)
        content_hash = hashlib.sha256(extracted.data).hexdigest()
        existing = self._docs.find_by_hash(self._workspace_id, content_hash)
        if existing and not existing.deleted:
            return existing

        object_key = f"{self._workspace_id}/research/{content_hash}/{extracted.filename}"
        self._store.put(
            object_key, extracted.data, content_type=extracted.content_type
        )
        summary = extracted.extracted_text[:2_000]
        evidence = Evidence(
            provider_id="user_upload",
            source_type="document",
            title=title or extracted.filename,
            summary=summary,
            ownership="private",
            workspace_id=self._workspace_id,
            raw_content_ref=object_key,
            source_quality_score=0.9,
        )
        source = SourceRecord(
            provider_id="user_upload",
            source_type="document",
            title=evidence.title,
            content_hash=content_hash,
            ownership=OwnershipClass.PRIVATE,
            workspace_id=self._workspace_id,
        )
        self._evidence.save_many([evidence], workspace_id=self._workspace_id)
        doc = PrivateDocument(
            workspace_id=self._workspace_id,
            title=title or extracted.filename,
            filename=extracted.filename,
            kind=extracted.kind,
            content_hash=content_hash,
            content_type=extracted.content_type,
            size_bytes=len(extracted.data),
            object_key=object_key,
            extracted_text=extracted.extracted_text,
            symbols=symbols or [],
            themes=themes or [],
            evidence_id=evidence.id,
            source_record_id=source.id,
            ownership="private",
        )
        return self._docs.save(doc, workspace_id=self._workspace_id)

    def list(self, *, include_deleted: bool = False) -> list[PrivateDocument]:
        return self._docs.list(
            self._workspace_id, include_deleted=include_deleted
        )

    def get(self, document_id: str) -> PrivateDocument | None:
        return self._docs.get(self._workspace_id, document_id)

    def delete(self, document_id: str) -> PrivateDocument | None:
        doc = self._docs.get(self._workspace_id, document_id)
        if doc is None or doc.deleted:
            return None
        deleted = doc.model_copy(
            update={"deleted": True, "created_at": doc.created_at}
        )
        # Soft-delete: keep blob for audit but mark evidence ownership tombstone
        # by clearing association for future runs.
        deleted = deleted.model_copy(update={"evidence_id": None})
        self._docs.save(deleted, workspace_id=self._workspace_id)
        self._store.delete(doc.object_key)
        return deleted

    def search(self, query: str, *, limit: int = 50) -> list[DocumentSearchHit]:
        needle = query.strip().lower()
        if not needle:
            return []
        hits: list[DocumentSearchHit] = []
        for doc in self._docs.list(self._workspace_id, include_deleted=False):
            hay = f"{doc.title}\n{doc.extracted_text}".lower()
            idx = hay.find(needle)
            if idx < 0:
                continue
            start = max(0, idx - 40)
            end = min(len(doc.extracted_text), idx + len(needle) + 80)
            snippet = doc.extracted_text[start:end].replace("\n", " ")
            hits.append(DocumentSearchHit(document=doc, snippet=snippet))
            if len(hits) >= limit:
                break
        return hits

    def active_evidence_ids(self) -> list[str]:
        """Evidence IDs safe to use in future runs (non-deleted private docs)."""
        return [
            doc.evidence_id
            for doc in self._docs.list(self._workspace_id, include_deleted=False)
            if doc.evidence_id
        ]
