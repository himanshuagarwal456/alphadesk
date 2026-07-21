"""Load and install the published knowledge catalog."""

from __future__ import annotations

import json
from pathlib import Path

from tradingagents.knowledge.schemas import (
    AccessType,
    Concept,
    ConceptDifficulty,
    ConceptResource,
    ConceptStatus,
    KnowledgeResource,
    ResourceType,
)

CATALOG_PATH = Path(__file__).resolve().parent / "data" / "catalog_v1.json"


def load_catalog(path: Path | None = None) -> tuple[
    list[Concept],
    list[KnowledgeResource],
    list[ConceptResource],
]:
    payload = json.loads((path or CATALOG_PATH).read_text(encoding="utf-8"))
    if payload.get("version") != "knowledge-v1":
        raise ValueError(f"unsupported knowledge catalog version: {payload.get('version')!r}")

    concepts = [
        Concept(
            slug=item["slug"],
            title=item["title"],
            short_definition=item["short_definition"],
            beginner_explanation=item.get("beginner_explanation", ""),
            intermediate_explanation=item.get("intermediate_explanation", ""),
            advanced_explanation=item.get("advanced_explanation", ""),
            quant_explanation=item.get("quant_explanation", ""),
            difficulty=ConceptDifficulty(item.get("difficulty", "beginner")),
            estimated_read_time=int(item.get("estimated_read_time", 3)),
            tags=list(item.get("tags") or []),
            status=ConceptStatus.PUBLISHED,
        )
        for item in payload["concepts"]
    ]
    by_slug = {c.slug: c for c in concepts}

    resources: list[KnowledgeResource] = []
    links: list[ConceptResource] = []
    for item in payload["resources"]:
        resource = KnowledgeResource(
            title=item["title"],
            provider=item["provider"],
            url=item["url"],
            resource_type=ResourceType(item.get("resource_type", "article")),
            difficulty=ConceptDifficulty(item.get("difficulty", "beginner")),
            estimated_read_time=int(item.get("estimated_read_time", 5)),
            access_type=AccessType(item.get("access_type", "free")),
            quality_score=float(item.get("quality_score", 0.8)),
            status=ConceptStatus.PUBLISHED,
        )
        resources.append(resource)
        for order, slug in enumerate(item.get("concept_slugs") or []):
            concept = by_slug.get(slug)
            if concept is None or concept.id is None:
                continue
            links.append(
                ConceptResource(
                    concept_id=concept.id,
                    resource_id=resource.id or "",
                    relevance_score=1.0,
                    display_order=order,
                )
            )
    return concepts, resources, links
