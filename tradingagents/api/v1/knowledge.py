"""Learn More / knowledge catalog endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.domain.schemas import IntelligenceCardRecord
from tradingagents.knowledge.schemas import (
    CardLearnMore,
    Concept,
    KnowledgeContext,
    ProgressStatus,
    UserConceptProgress,
)
from tradingagents.knowledge.service import KnowledgeContextService
from tradingagents.persistence.repositories import IntelligenceCardRepository

router = APIRouter(prefix="/knowledge")


class ProgressUpdateRequest(BaseModel):
    status: ProgressStatus | None = None
    saved: bool | None = None


class DemoCardRequest(BaseModel):
    symbol: str = "AMD"
    title: str = "Gross margin improved"
    headline: str = "AMD gross margin improved on richer mix."
    body: str = (
        "Gross margin expanded versus the prior quarter. Review pricing power, "
        "operating leverage, and whether the living thesis needs an update."
    )


@router.get("/concepts", response_model=list[Concept])
def list_concepts(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[Concept]:
    return KnowledgeContextService(session, workspace_id=workspace_id).list_concepts()


@router.get("/concepts/{concept_id}", response_model=Concept)
def get_concept(
    concept_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> Concept:
    concept = KnowledgeContextService(session, workspace_id=workspace_id).get_concept(
        concept_id
    )
    if concept is None:
        raise HTTPException(status_code=404, detail="concept not found")
    return concept


@router.get("/context", response_model=KnowledgeContext)
def get_context(
    concept_id: str = Query(..., min_length=1),
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    intelligence_card_id: str | None = None,
    mark_viewed: bool = True,
) -> KnowledgeContext:
    try:
        return KnowledgeContextService(session, workspace_id=workspace_id).build_context(
            concept_id=concept_id,
            intelligence_card_id=intelligence_card_id,
            mark_viewed=mark_viewed,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/cards/{card_id}/concepts", response_model=list[Concept])
def concepts_for_card(
    card_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> list[Concept]:
    return KnowledgeContextService(session, workspace_id=workspace_id).concepts_for_card(
        card_id
    )


@router.get("/cards/{card_id}/learn-more", response_model=CardLearnMore)
def learn_more_for_card(
    card_id: str,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> CardLearnMore:
    """Card-first Learn More: unpack this card, then optional glossary terms."""
    try:
        return KnowledgeContextService(
            session, workspace_id=workspace_id
        ).build_card_learn_more(card_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post(
    "/concepts/{concept_id}/progress",
    response_model=UserConceptProgress,
)
def update_progress(
    concept_id: str,
    body: ProgressUpdateRequest,
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> UserConceptProgress:
    service = KnowledgeContextService(session, workspace_id=workspace_id)
    if service.get_concept(concept_id) is None:
        raise HTTPException(status_code=404, detail="concept not found")
    concept = service.get_concept(concept_id)
    assert concept is not None and concept.id
    return service.update_progress(
        concept.id, status=body.status, saved=body.saved
    )


@router.post("/demo-card", response_model=IntelligenceCardRecord, status_code=201)
def create_demo_card(
    body: DemoCardRequest = Body(default_factory=DemoCardRequest),
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> IntelligenceCardRecord:
    """Create a sample Intelligence Card and attach matching concepts."""
    req = body
    card = IntelligenceCardRecord(
        id=f"card_demo_{req.symbol.lower()}_gm",
        workspace_id=workspace_id,
        symbol=req.symbol.upper(),
        card_type="fundamentals",
        title=req.title,
        headline=req.headline,
        body=req.body,
    )
    saved = IntelligenceCardRepository(session).save(card, workspace_id=workspace_id)
    KnowledgeContextService(session, workspace_id=workspace_id).attach_concepts_to_card(
        saved
    )
    return saved
