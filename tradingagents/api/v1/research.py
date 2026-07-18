"""Private research upload and browser endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.research import DocumentSearchHit, PrivateDocument
from tradingagents.research.ingest import UploadValidationError
from tradingagents.research.service import PrivateResearchService

router = APIRouter(prefix="/research")


class ExportFilter(BaseModel):
    include_private: bool = False
    evidence_ids: list[str] = Field(default_factory=list)


@router.post("/documents", response_model=PrivateDocument, status_code=201)
async def upload_document(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    symbols: str = Form(default=""),
    themes: str = Form(default=""),
) -> PrivateDocument:
    data = await file.read()
    symbol_list = [s.strip() for s in symbols.split(",") if s.strip()]
    theme_list = [t.strip() for t in themes.split(",") if t.strip()]
    try:
        return PrivateResearchService(session, workspace_id=workspace_id).upload(
            filename=file.filename or "upload.bin",
            data=data,
            title=title,
            symbols=symbol_list,
            themes=theme_list,
        )
    except UploadValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/documents", response_model=list[PrivateDocument])
def list_documents(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    include_deleted: bool = False,
) -> list[PrivateDocument]:
    return PrivateResearchService(session, workspace_id=workspace_id).list(
        include_deleted=include_deleted
    )


@router.get("/documents/{document_id}", response_model=PrivateDocument)
def get_document(
    document_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PrivateDocument:
    doc = PrivateResearchService(session, workspace_id=workspace_id).get(document_id)
    if doc is None or doc.deleted:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.get("/documents/{document_id}/text")
def get_extracted_text(
    document_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> dict[str, str]:
    doc = PrivateResearchService(session, workspace_id=workspace_id).get(document_id)
    if doc is None or doc.deleted:
        raise HTTPException(status_code=404, detail="document not found")
    return {"document_id": doc.id, "extracted_text": doc.extracted_text}


@router.delete("/documents/{document_id}", response_model=PrivateDocument)
def delete_document(
    document_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> PrivateDocument:
    doc = PrivateResearchService(session, workspace_id=workspace_id).delete(document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="document not found")
    return doc


@router.get("/search", response_model=list[DocumentSearchHit])
def search_documents(
    q: str = Query(..., min_length=1),
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[DocumentSearchHit]:
    return PrivateResearchService(session, workspace_id=workspace_id).search(
        q, limit=limit
    )


@router.post("/exports/filter")
def filter_export_evidence(
    body: ExportFilter,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> dict:
    """Public exports exclude private evidence by default."""
    from tradingagents.persistence.repositories import EvidenceRepository

    private_ids = set(
        PrivateResearchService(session, workspace_id=workspace_id).active_evidence_ids()
    )
    # Also treat any evidence marked private in this workspace as private.
    for item in EvidenceRepository(session).list(workspace_id, limit=1000):
        if item.ownership == "private":
            private_ids.add(item.id)
    if body.include_private:
        return {"evidence_ids": body.evidence_ids, "excluded_private": []}
    kept = [eid for eid in body.evidence_ids if eid not in private_ids]
    excluded = [eid for eid in body.evidence_ids if eid in private_ids]
    return {"evidence_ids": kept, "excluded_private": excluded}
