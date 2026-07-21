"""Attach Learn More concept snippets to feed cards (offline catalog)."""

from __future__ import annotations

from functools import lru_cache

from tradingagents.knowledge.seed import load_catalog
from tradingagents.ui.feed_schema import Card, LearnMoreItem, LearnMoreResource


@lru_cache(maxsize=1)
def _catalog_index() -> tuple[tuple, dict]:
    concepts, resources, links = load_catalog()
    by_id = {c.id: c for c in concepts if c.id}
    resources_by_id = {r.id: r for r in resources if r.id}
    links_by_concept: dict[str, list] = {}
    for link in links:
        links_by_concept.setdefault(link.concept_id, []).append(link)
    for concept_links in links_by_concept.values():
        concept_links.sort(key=lambda item: item.display_order)
    return tuple(concepts), {
        "by_id": by_id,
        "resources_by_id": resources_by_id,
        "links_by_concept": links_by_concept,
    }


def suggest_concepts_for_text(text: str, *, limit: int = 4) -> list:
    concepts, _index = _catalog_index()
    hay = (text or "").lower()
    scored: list[tuple[float, object]] = []
    for concept in concepts:
        score = 0.0
        if concept.title.lower() in hay:
            score += 3.0
        if concept.slug.replace("-", " ") in hay:
            score += 2.5
        for tag in concept.tags:
            if tag in hay:
                score += 1.0
        for token in concept.short_definition.lower().split():
            token = token.strip(".,;:()")
            if len(token) > 5 and token in hay:
                score += 0.15
        if score > 0:
            scored.append((score, concept))
    scored.sort(key=lambda item: (-item[0], item[1].title))
    return [concept for _, concept in scored[:limit]]


def build_learn_more_items(
    text: str,
    *,
    symbol: str | None = None,
    card_type: str | None = None,
    limit: int = 4,
) -> list[LearnMoreItem]:
    concepts = suggest_concepts_for_text(text, limit=limit)
    if not concepts and card_type == "thesis_change":
        concepts = suggest_concepts_for_text(
            "investment thesis conviction catalyst invalidation concentration risk",
            limit=limit,
        )
    _, index = _catalog_index()
    items: list[LearnMoreItem] = []
    for concept in concepts:
        if not concept.id:
            continue
        explanation = (
            concept.intermediate_explanation.strip()
            or concept.beginner_explanation.strip()
            or concept.short_definition
        )
        why = (
            f"This card about {symbol} touches {concept.title.lower()}. "
            f"{concept.short_definition} "
            "Understanding it helps you judge whether conviction, risk, or sizing should change."
            if symbol
            else f"{concept.title} often drives thesis revisions. {concept.short_definition}"
        )
        resources: list[LearnMoreResource] = []
        for link in index["links_by_concept"].get(concept.id, [])[:3]:
            resource = index["resources_by_id"].get(link.resource_id)
            if resource is None:
                continue
            resources.append(
                LearnMoreResource(
                    title=resource.title,
                    provider=resource.provider,
                    url=str(resource.url),
                )
            )
        items.append(
            LearnMoreItem(
                concept_id=concept.id,
                slug=concept.slug,
                title=concept.title,
                short_definition=concept.short_definition,
                explanation=explanation,
                why_it_matters=why,
                difficulty=concept.difficulty.value,
                estimated_read_time=concept.estimated_read_time,
                resources=resources,
            )
        )
    return items


def attach_learn_more(
    card: Card,
    *,
    symbol: str | None = None,
) -> Card:
    """Return a copy of ``card`` with Learn More snippets attached when matched."""
    if card.learn_more:
        return card
    text = " ".join(
        part
        for part in (
            card.title,
            card.headline,
            card.body,
            card.card_type or "",
            " ".join(card.badges),
            card.portfolio_impact or "",
        )
        if part
    )
    items = build_learn_more_items(
        text,
        symbol=symbol or (card.symbols[0] if card.symbols else None),
        card_type=card.card_type,
    )
    if not items:
        return card
    return card.model_copy(update={"learn_more": items})
