"""Knowledge context service — builds Learn More responses."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from tradingagents.domain.schemas import IntelligenceCardRecord
from tradingagents.knowledge.schemas import (
    Concept,
    ConceptDifficulty,
    IntelligenceCardConcept,
    KnowledgeContext,
    ProgressStatus,
    UserConceptProgress,
)
from tradingagents.knowledge.seed import load_catalog
from tradingagents.persistence.repositories.cards import IntelligenceCardRepository
from tradingagents.persistence.repositories.knowledge import KnowledgeRepository
from tradingagents.persistence.repositories.portfolios import PortfolioRepository
from tradingagents.persistence.repositories.state import PortfolioStateRepository
from tradingagents.portfolio.service import CURRENT_SNAPSHOT_ID


class KnowledgeContextService:
    def __init__(self, session: Session, *, workspace_id: str):
        self._session = session
        self._workspace_id = workspace_id
        self._knowledge = KnowledgeRepository(session)
        self._cards = IntelligenceCardRepository(session)

    def ensure_seeded(self) -> int:
        """Install catalog on empty DB; always refresh resources/links from catalog."""
        concepts, resources, links = load_catalog()
        created = 0
        if self._knowledge.count_concepts() == 0:
            for concept in concepts:
                self._knowledge.upsert_concept(concept)
            created = len(concepts)
        else:
            # Keep concept copy current without wiping user progress.
            for concept in concepts:
                self._knowledge.upsert_concept(concept)
        for resource in resources:
            self._knowledge.upsert_resource(resource)
        # Replace outbound links so URL refreshes do not leave homepage stubs.
        for concept in concepts:
            if concept.id:
                self._knowledge.replace_concept_resources(
                    concept.id,
                    [link for link in links if link.concept_id == concept.id],
                )
        return created

    def list_concepts(self) -> list[Concept]:
        self.ensure_seeded()
        return self._knowledge.list_concepts()

    def get_concept(self, concept_id_or_slug: str) -> Concept | None:
        self.ensure_seeded()
        concept = self._knowledge.get_concept(concept_id_or_slug)
        if concept is None:
            concept = self._knowledge.get_concept_by_slug(concept_id_or_slug)
        return concept

    def suggest_concepts_for_text(self, text: str, *, limit: int = 5) -> list[Concept]:
        self.ensure_seeded()
        hay = (text or "").lower()
        scored: list[tuple[float, Concept]] = []
        for concept in self._knowledge.list_concepts():
            score = 0.0
            if concept.title.lower() in hay:
                score += 3.0
            if concept.slug.replace("-", " ") in hay:
                score += 2.5
            for tag in concept.tags:
                if tag in hay:
                    score += 1.0
            # Light keyword hits from the short definition's first noun phrase tokens
            for token in concept.short_definition.lower().split():
                token = token.strip(".,;:()")
                if len(token) > 5 and token in hay:
                    score += 0.15
            if score > 0:
                scored.append((score, concept))
        scored.sort(key=lambda item: (-item[0], item[1].title))
        return [concept for _, concept in scored[:limit]]

    def attach_concepts_to_card(
        self,
        card: IntelligenceCardRecord,
        *,
        limit: int = 4,
    ) -> list[IntelligenceCardConcept]:
        text = " ".join(
            part
            for part in (card.title, card.headline, card.body, card.card_type or "")
            if part
        )
        concepts = self.suggest_concepts_for_text(text, limit=limit)
        links: list[IntelligenceCardConcept] = []
        for order, concept in enumerate(concepts):
            if not concept.id:
                continue
            link = IntelligenceCardConcept(
                intelligence_card_id=card.id,
                concept_id=concept.id,
                relevance_score=max(0.4, 1.0 - order * 0.15),
                context_reason=f"Matched from card language for {concept.title}",
                display_order=order,
            )
            self._knowledge.link_card_concept(link)
            links.append(link)
        return links

    def concepts_for_card(self, card_id: str) -> list[Concept]:
        self.ensure_seeded()
        links = self._knowledge.list_concepts_for_card(card_id)
        if not links:
            card = self._cards.get(self._workspace_id, card_id)
            if card is None:
                return []
            links = self.attach_concepts_to_card(card)
        concepts: list[Concept] = []
        for link in links:
            concept = self._knowledge.get_concept(link.concept_id)
            if concept is not None:
                concepts.append(concept)
        return concepts

    def build_context(
        self,
        *,
        concept_id: str,
        intelligence_card_id: str | None = None,
        mark_viewed: bool = True,
    ) -> KnowledgeContext:
        self.ensure_seeded()
        concept = self.get_concept(concept_id)
        if concept is None:
            raise KeyError("concept not found")

        card = None
        if intelligence_card_id:
            card = self._cards.get(self._workspace_id, intelligence_card_id)

        level = self._choose_level(concept)
        explanation = self._explanation_for_level(concept, level)
        why = self._why_it_matters(concept, card)
        example = self._portfolio_example(concept, card)
        related = self._related_concepts(concept)
        resources = self._knowledge.list_resources_for_concept(concept.id or "")

        progress = None
        if mark_viewed and concept.id:
            progress = self.record_view(concept.id)
        elif concept.id:
            progress = self._knowledge.get_progress(self._workspace_id, concept.id)

        return KnowledgeContext(
            concept=concept,
            personalized_explanation=explanation,
            why_it_matters=why,
            portfolio_example=example,
            related_concepts=related,
            external_resources=resources,
            user_progress=progress,
            explanation_level=level,
            intelligence_card_id=intelligence_card_id,
            symbol=(card.symbol if card else None),
        )

    def record_view(self, concept_id: str) -> UserConceptProgress:
        now = datetime.now(timezone.utc)
        existing = self._knowledge.get_progress(self._workspace_id, concept_id)
        if existing is None:
            progress = UserConceptProgress(
                user_id=self._workspace_id,
                concept_id=concept_id,
                view_count=1,
                first_viewed_at=now,
                last_viewed_at=now,
                status=ProgressStatus.VIEWED,
            )
        else:
            status = (
                ProgressStatus.COMPLETED
                if existing.status is ProgressStatus.COMPLETED
                else ProgressStatus.VIEWED
            )
            progress = existing.model_copy(
                update={
                    "view_count": existing.view_count + 1,
                    "last_viewed_at": now,
                    "first_viewed_at": existing.first_viewed_at or now,
                    "status": status,
                }
            )
        return self._knowledge.save_progress(progress)

    def update_progress(
        self,
        concept_id: str,
        *,
        status: ProgressStatus | None = None,
        saved: bool | None = None,
    ) -> UserConceptProgress:
        existing = self._knowledge.get_progress(self._workspace_id, concept_id)
        now = datetime.now(timezone.utc)
        if existing is None:
            existing = UserConceptProgress(
                user_id=self._workspace_id,
                concept_id=concept_id,
                first_viewed_at=now,
                last_viewed_at=now,
                view_count=1 if status is not None else 0,
            )
        updates: dict = {"last_viewed_at": now}
        if status is not None:
            updates["status"] = status
        if saved is not None:
            updates["saved"] = saved
        return self._knowledge.save_progress(existing.model_copy(update=updates))

    def _choose_level(self, concept: Concept) -> ConceptDifficulty:
        # Backend chooses level; alpha defaults to intermediate when available.
        if concept.intermediate_explanation.strip():
            return ConceptDifficulty.INTERMEDIATE
        if concept.beginner_explanation.strip():
            return ConceptDifficulty.BEGINNER
        return concept.difficulty

    def _explanation_for_level(
        self, concept: Concept, level: ConceptDifficulty
    ) -> str:
        mapping = {
            ConceptDifficulty.BEGINNER: concept.beginner_explanation,
            ConceptDifficulty.INTERMEDIATE: concept.intermediate_explanation,
            ConceptDifficulty.ADVANCED: concept.advanced_explanation,
            ConceptDifficulty.QUANT: concept.quant_explanation,
        }
        text = mapping.get(level) or concept.short_definition
        return text.strip() or concept.short_definition

    def _why_it_matters(
        self, concept: Concept, card: IntelligenceCardRecord | None
    ) -> str:
        if card is None:
            return (
                f"{concept.title} shows up often in portfolio research. "
                f"TL;DR: {concept.short_definition}"
            )
        symbol = card.symbol or "this name"
        return (
            f"This Intelligence Card about {symbol} touches {concept.title.lower()}. "
            f"{concept.short_definition} "
            f"Understanding it helps you judge whether the card should change conviction, "
            f"risk, or sizing — not just read as news."
        )

    def _portfolio_example(
        self, concept: Concept, card: IntelligenceCardRecord | None
    ) -> str:
        book = self._load_book()
        symbol = (card.symbol if card else None) or None
        if book is not None and symbol and book.holds(symbol):
            weight = book.weights().get(symbol.upper())
            weight_txt = f" ({weight * 100:.1f}% of book)" if weight is not None else ""
            return (
                f"You hold {symbol}{weight_txt}. "
                f"If {concept.title.lower()} deteriorates for {symbol}, revisit sizing and "
                f"the living thesis — concentration and thesis invalidation matter together."
            )
        if book is not None and book.open_positions:
            top = max(book.open_positions, key=lambda p: abs(p.market_value or 0.0))
            return (
                f"Your largest open holding is {top.symbol}. "
                f"Ask how {concept.title.lower()} would change risk or expected return there "
                f"before acting on a card."
            )
        if symbol:
            return (
                f"{symbol} is not currently held. Use {concept.title.lower()} to decide "
                f"whether it belongs on the watchlist or as an initiate candidate."
            )
        return (
            f"With no active book loaded, treat {concept.title.lower()} as a checklist item "
            f"when you next import a portfolio or open a thesis."
        )

    def _related_concepts(self, concept: Concept, *, limit: int = 4) -> list[Concept]:
        tags = set(concept.tags)
        related: list[tuple[int, Concept]] = []
        for other in self._knowledge.list_concepts():
            if other.id == concept.id:
                continue
            overlap = len(tags.intersection(other.tags))
            if overlap:
                related.append((overlap, other))
        related.sort(key=lambda item: (-item[0], item[1].title))
        return [item[1] for item in related[:limit]]

    def _load_book(self):
        controls = PortfolioStateRepository(self._session).get_controls(
            self._workspace_id
        )
        snapshot_id = controls.current_snapshot_id or CURRENT_SNAPSHOT_ID
        book = PortfolioRepository(self._session).get(self._workspace_id, snapshot_id)
        if book is None and snapshot_id != CURRENT_SNAPSHOT_ID:
            book = PortfolioRepository(self._session).get(
                self._workspace_id, CURRENT_SNAPSHOT_ID
            )
        return book
