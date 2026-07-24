"""Learn More / Knowledge & Context domain models (docs/knowledge-feature.md)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, HttpUrl, field_validator, model_validator


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


class ConceptDifficulty(str, Enum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    QUANT = "quant"


class ConceptStatus(str, Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ARCHIVED = "archived"


class ResourceType(str, Enum):
    ARTICLE = "article"
    GUIDE = "guide"
    FILING = "filing"
    GLOSSARY = "glossary"
    VIDEO = "video"
    OTHER = "other"


class AccessType(str, Enum):
    FREE = "free"
    REGISTRATION = "registration"
    PAID = "paid"


class ProgressStatus(str, Enum):
    NOT_STARTED = "not_started"
    VIEWED = "viewed"
    COMPLETED = "completed"


class Concept(BaseModel):
    """A financial concept AlphaDesk explains in its own words."""

    id: str | None = None
    slug: str = Field(min_length=1)
    title: str = Field(min_length=1)
    short_definition: str = Field(min_length=1)
    beginner_explanation: str = ""
    intermediate_explanation: str = ""
    advanced_explanation: str = ""
    quant_explanation: str = ""
    difficulty: ConceptDifficulty = ConceptDifficulty.BEGINNER
    estimated_read_time: int = Field(default=2, ge=1, le=60)
    tags: list[str] = Field(default_factory=list)
    status: ConceptStatus = ConceptStatus.PUBLISHED
    version: int = 1
    schema_version: int = 1

    @field_validator("slug")
    @classmethod
    def _slug(cls, value: str) -> str:
        return value.strip().lower().replace(" ", "-")

    @field_validator("tags")
    @classmethod
    def _tags(cls, values: list[str]) -> list[str]:
        return sorted({v.strip().lower() for v in values if v and v.strip()})

    @model_validator(mode="after")
    def _assign_id(self) -> Concept:
        if self.id is None:
            self.id = _stable_id("kc", self.slug)
        return self


class KnowledgeResource(BaseModel):
    """Outbound learning link metadata only — never republished article bodies."""

    id: str | None = None
    title: str = Field(min_length=1)
    provider: str = Field(min_length=1)
    url: HttpUrl | str
    resource_type: ResourceType = ResourceType.ARTICLE
    difficulty: ConceptDifficulty = ConceptDifficulty.BEGINNER
    estimated_read_time: int = Field(default=5, ge=1, le=120)
    access_type: AccessType = AccessType.FREE
    quality_score: float = Field(default=0.8, ge=0, le=1)
    last_verified_at: datetime | None = None
    status: ConceptStatus = ConceptStatus.PUBLISHED
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> KnowledgeResource:
        if self.id is None:
            # Title+provider keeps IDs stable when we refresh the destination URL.
            self.id = _stable_id("kr", self.title.strip().lower(), self.provider.lower())
        return self


class ConceptResource(BaseModel):
    concept_id: str
    resource_id: str
    relevance_score: float = Field(default=1.0, ge=0, le=1)
    display_order: int = 0


class IntelligenceCardConcept(BaseModel):
    intelligence_card_id: str
    concept_id: str
    relevance_score: float = Field(default=1.0, ge=0, le=1)
    context_reason: str = ""
    display_order: int = 0


class UserConceptProgress(BaseModel):
    """Learning progress. Until auth lands, ``user_id`` is the workspace id."""

    user_id: str
    concept_id: str
    view_count: int = 0
    first_viewed_at: datetime | None = None
    last_viewed_at: datetime | None = None
    status: ProgressStatus = ProgressStatus.NOT_STARTED
    saved: bool = False
    schema_version: int = 1


class KnowledgeContext(BaseModel):
    """Learn More payload returned by the knowledge context service."""

    concept: Concept
    personalized_explanation: str
    why_it_matters: str
    portfolio_example: str
    related_concepts: list[Concept] = Field(default_factory=list)
    external_resources: list[KnowledgeResource] = Field(default_factory=list)
    user_progress: UserConceptProgress | None = None
    explanation_level: ConceptDifficulty = ConceptDifficulty.INTERMEDIATE
    intelligence_card_id: str | None = None
    symbol: str | None = None
