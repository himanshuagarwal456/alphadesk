"""Learn More / Knowledge & Context package."""

from tradingagents.knowledge.schemas import (
    Concept,
    KnowledgeContext,
    KnowledgeResource,
    ProgressStatus,
    UserConceptProgress,
)

__all__ = [
    "Concept",
    "KnowledgeContext",
    "KnowledgeContextService",
    "KnowledgeResource",
    "ProgressStatus",
    "UserConceptProgress",
]


def __getattr__(name: str):
    if name == "KnowledgeContextService":
        from tradingagents.knowledge.service import KnowledgeContextService

        return KnowledgeContextService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
