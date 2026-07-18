"""Evidence endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.evidence.schemas import Evidence
from tradingagents.persistence.repositories import EvidenceRepository

router = APIRouter(prefix="/evidence")


@router.post("", response_model=list[Evidence], status_code=201)
def upsert_evidence(
    body: list[Evidence],
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[Evidence]:
    return EvidenceRepository(session).save_many(body, workspace_id=workspace_id)


@router.get("", response_model=list[Evidence])
def list_evidence(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    provider_id: str | None = None,
    limit: int = Query(default=200, ge=1, le=1000),
) -> list[Evidence]:
    return EvidenceRepository(session).list(
        workspace_id, provider_id=provider_id, limit=limit
    )


@router.get("/{evidence_id}", response_model=Evidence)
def get_evidence(
    evidence_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> Evidence:
    record = EvidenceRepository(session).get(workspace_id, evidence_id)
    if record is None:
        raise HTTPException(status_code=404, detail="evidence not found")
    return record
