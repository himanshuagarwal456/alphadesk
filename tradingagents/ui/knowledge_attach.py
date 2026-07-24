"""Attach Learn More briefings to feed cards (card content first, catalog second)."""

from __future__ import annotations

import re
from functools import lru_cache

from tradingagents.knowledge.seed import load_catalog
from tradingagents.ui.feed_schema import (
    Card,
    LearnMoreBrief,
    LearnMoreItem,
    LearnMoreResource,
)


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


def _first_sentence(text: str, limit: int = 220) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[#*`>]", "", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    match = re.search(r"(.+?[.!?])(\s|$)", cleaned)
    sentence = match.group(1) if match else cleaned
    return sentence[:limit].strip()


def _what_to_check(card_type: str | None, title: str, symbol: str | None) -> str:
    name = symbol or "this name"
    title_l = (title or "").lower()
    kind = (card_type or "").lower()
    if kind == "thesis_change" or "thesis" in title_l:
        return (
            f"Re-read the living thesis for {name}: which catalyst still holds, "
            "what would invalidate it, and whether size still matches conviction."
        )
    if kind == "event" or "news" in title_l:
        return (
            f"Ask whether the news is already priced into {name}, whether it changes "
            "the next catalyst, and if risk limits need a trim or add."
        )
    if "macro" in title_l:
        return (
            "Map the macro print to book exposures (rates, growth, risk-off). "
            "Check which held names move with this regime and whether sizing should change."
        )
    if "sentiment" in title_l:
        return (
            f"Separate noise from signal: does the tone shift for {name} change the "
            "near-term thesis, or only the path around an event?"
        )
    if "fundamental" in title_l:
        return (
            f"Tie the fundamental claim back to margins, cash flow, and guidance for {name}. "
            "Decide if the thesis needs a confidence or rating update."
        )
    if "market" in title_l or "verdict" in title_l or "debate" in title_l:
        return (
            f"Weigh the technical/debate read against your book weight in {name}. "
            "Confirm stop, target, and whether the stance is initiate, manage, or exit."
        )
    return (
        f"Use this card to update your view of {name}: does it change conviction, "
        "timing, or size — or is it noise relative to the living thesis?"
    )


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
            f"On this card about {symbol}, {concept.title.lower()} is part of the claim. "
            f"{concept.short_definition} "
            "Use it to judge whether conviction, risk, or sizing should change."
            if symbol
            else (
                f"{concept.title} shows up in this card. {concept.short_definition} "
                "Use it to interpret the claim, not as a separate lesson."
            )
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


def build_learn_brief(
    card: Card,
    *,
    symbol: str | None = None,
) -> LearnMoreBrief:
    """Explain the card content itself; attach glossary terms only as support."""
    sym = symbol or (card.symbols[0] if card.symbols else None)
    headline = (card.headline or "").strip()
    body_lead = _first_sentence(card.body)
    takeaways = [
        f"{c.agent}: {c.text}"
        for c in (card.comments or [])[:3]
        if (c.text or "").strip()
    ]

    parts: list[str] = []
    if headline:
        parts.append(f"The card’s claim: {headline}")
    if body_lead and body_lead not in headline:
        parts.append(f"In more detail: {body_lead}")
    if takeaways:
        parts.append(
            "What the desk is emphasizing: " + " · ".join(takeaways)
        )
    if not parts:
        parts.append(
            "This card flags a research signal. Open the evidence and agent comments "
            "to decide whether action is needed."
        )
    what_this_means = " ".join(parts)

    if card.portfolio_impact:
        why = card.portfolio_impact
        if sym:
            why = f"{why} Focus on how that maps to {sym}."
    elif sym:
        why = (
            f"For {sym}, this card is meant to change how you read conviction, risk, "
            "or timing — not just to add another headline."
        )
    else:
        why = (
            "This matters for the book if it changes conviction, concentration, "
            "or the next decision on size and timing."
        )

    text = " ".join(
        part
        for part in (
            card.title,
            card.headline,
            card.body,
            card.card_type or "",
            " ".join(card.badges),
            card.portfolio_impact or "",
            " ".join(takeaways),
        )
        if part
    )
    concepts = build_learn_more_items(
        text,
        symbol=sym,
        card_type=card.card_type,
    )
    return LearnMoreBrief(
        title=card.title or "Learn More",
        headline=headline,
        what_this_means=what_this_means,
        why_it_matters=why,
        what_to_check=_what_to_check(card.card_type, card.title, sym),
        agent_takeaways=takeaways,
        concepts=concepts,
    )


def attach_learn_more(
    card: Card,
    *,
    symbol: str | None = None,
) -> Card:
    """Return a copy of ``card`` with a card-first Learn More briefing attached."""
    if card.learn_brief is not None:
        return card
    brief = build_learn_brief(
        card, symbol=symbol or (card.symbols[0] if card.symbols else None)
    )
    updates: dict = {"learn_brief": brief}
    if not card.learn_more and brief.concepts:
        updates["learn_more"] = brief.concepts
    return card.model_copy(update=updates)
