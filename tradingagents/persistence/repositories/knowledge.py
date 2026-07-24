"""Knowledge catalog persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.knowledge.schemas import (
    Concept,
    ConceptResource,
    IntelligenceCardConcept,
    KnowledgeResource,
    UserConceptProgress,
)

from ..models import (
    ConceptResourceRow,
    ConceptRow,
    IntelligenceCardConceptRow,
    KnowledgeResourceRow,
    UserConceptProgressRow,
)


class KnowledgeRepository:
    def __init__(self, session: Session):
        self._session = session

    def count_concepts(self) -> int:
        return len(list(self._session.scalars(select(ConceptRow.id))))

    def upsert_concept(self, concept: Concept) -> Concept:
        row = self._session.scalars(
            select(ConceptRow).where(ConceptRow.id == concept.id)
        ).first()
        data = concept.model_dump(mode="json")
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                ConceptRow(
                    id=concept.id,
                    slug=concept.slug,
                    title=concept.title,
                    status=concept.status.value,
                    payload=data,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            row.slug = concept.slug
            row.title = concept.title
            row.status = concept.status.value
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return concept

    def upsert_resource(self, resource: KnowledgeResource) -> KnowledgeResource:
        row = self._session.scalars(
            select(KnowledgeResourceRow).where(KnowledgeResourceRow.id == resource.id)
        ).first()
        data = resource.model_dump(mode="json")
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                KnowledgeResourceRow(
                    id=resource.id,
                    title=resource.title,
                    provider=resource.provider,
                    status=resource.status.value,
                    payload=data,
                    created_at=now,
                    updated_at=now,
                )
            )
        else:
            row.title = resource.title
            row.provider = resource.provider
            row.status = resource.status.value
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return resource

    def link_concept_resource(self, link: ConceptResource) -> ConceptResource:
        row = self._session.scalars(
            select(ConceptResourceRow).where(
                ConceptResourceRow.concept_id == link.concept_id,
                ConceptResourceRow.resource_id == link.resource_id,
            )
        ).first()
        if row is None:
            self._session.add(
                ConceptResourceRow(
                    concept_id=link.concept_id,
                    resource_id=link.resource_id,
                    relevance_score=link.relevance_score,
                    display_order=link.display_order,
                )
            )
        else:
            row.relevance_score = link.relevance_score
            row.display_order = link.display_order
        self._session.flush()
        return link

    def replace_concept_resources(
        self, concept_id: str, links: list[ConceptResource]
    ) -> None:
        """Drop prior outbound links for ``concept_id`` and write ``links``."""
        existing = list(
            self._session.scalars(
                select(ConceptResourceRow).where(
                    ConceptResourceRow.concept_id == concept_id
                )
            )
        )
        for row in existing:
            self._session.delete(row)
        self._session.flush()
        for link in links:
            self.link_concept_resource(link)

    def link_card_concept(self, link: IntelligenceCardConcept) -> IntelligenceCardConcept:
        row = self._session.scalars(
            select(IntelligenceCardConceptRow).where(
                IntelligenceCardConceptRow.intelligence_card_id
                == link.intelligence_card_id,
                IntelligenceCardConceptRow.concept_id == link.concept_id,
            )
        ).first()
        if row is None:
            self._session.add(
                IntelligenceCardConceptRow(
                    intelligence_card_id=link.intelligence_card_id,
                    concept_id=link.concept_id,
                    relevance_score=link.relevance_score,
                    context_reason=link.context_reason,
                    display_order=link.display_order,
                )
            )
        else:
            row.relevance_score = link.relevance_score
            row.context_reason = link.context_reason
            row.display_order = link.display_order
        self._session.flush()
        return link

    def get_concept(self, concept_id: str) -> Concept | None:
        row = self._session.scalars(
            select(ConceptRow).where(ConceptRow.id == concept_id)
        ).first()
        return Concept.model_validate(row.payload) if row else None

    def get_concept_by_slug(self, slug: str) -> Concept | None:
        row = self._session.scalars(
            select(ConceptRow).where(ConceptRow.slug == slug.strip().lower())
        ).first()
        return Concept.model_validate(row.payload) if row else None

    def list_concepts(self, *, limit: int = 200) -> list[Concept]:
        stmt = select(ConceptRow).order_by(ConceptRow.title.asc()).limit(limit)
        return [Concept.model_validate(row.payload) for row in self._session.scalars(stmt)]

    def list_resources_for_concept(self, concept_id: str) -> list[KnowledgeResource]:
        links = list(
            self._session.scalars(
                select(ConceptResourceRow)
                .where(ConceptResourceRow.concept_id == concept_id)
                .order_by(ConceptResourceRow.display_order.asc())
            )
        )
        out: list[KnowledgeResource] = []
        for link in links:
            row = self._session.scalars(
                select(KnowledgeResourceRow).where(
                    KnowledgeResourceRow.id == link.resource_id
                )
            ).first()
            if row is not None:
                out.append(KnowledgeResource.model_validate(row.payload))
        return out

    def list_concepts_for_card(self, card_id: str) -> list[IntelligenceCardConcept]:
        rows = self._session.scalars(
            select(IntelligenceCardConceptRow)
            .where(IntelligenceCardConceptRow.intelligence_card_id == card_id)
            .order_by(IntelligenceCardConceptRow.display_order.asc())
        )
        return [
            IntelligenceCardConcept(
                intelligence_card_id=row.intelligence_card_id,
                concept_id=row.concept_id,
                relevance_score=row.relevance_score,
                context_reason=row.context_reason or "",
                display_order=row.display_order,
            )
            for row in rows
        ]

    def get_progress(self, user_id: str, concept_id: str) -> UserConceptProgress | None:
        row = self._session.scalars(
            select(UserConceptProgressRow).where(
                UserConceptProgressRow.user_id == user_id,
                UserConceptProgressRow.concept_id == concept_id,
            )
        ).first()
        if row is None:
            return None
        return UserConceptProgress.model_validate(row.payload)

    def save_progress(self, progress: UserConceptProgress) -> UserConceptProgress:
        row = self._session.scalars(
            select(UserConceptProgressRow).where(
                UserConceptProgressRow.user_id == progress.user_id,
                UserConceptProgressRow.concept_id == progress.concept_id,
            )
        ).first()
        data = progress.model_dump(mode="json")
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                UserConceptProgressRow(
                    user_id=progress.user_id,
                    concept_id=progress.concept_id,
                    status=progress.status.value,
                    saved="true" if progress.saved else "false",
                    payload=data,
                    updated_at=now,
                )
            )
        else:
            row.status = progress.status.value
            row.saved = "true" if progress.saved else "false"
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return progress
