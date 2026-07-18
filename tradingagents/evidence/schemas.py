"""Versioned, source-linked evidence records.

Evidence is deliberately separate from an agent's conclusions. It captures what
was retrieved, from whom, and when; later augmentation or intelligence layers
can reference its stable ``id`` without rewriting the underlying source record.
"""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class Evidence(BaseModel):
    """An immutable normalized reference to an externally published source."""

    id: str | None = Field(
        default=None,
        description="Stable content-derived ID. Generated when omitted.",
    )
    provider_id: str = Field(description="Connector that retrieved this source, e.g. yfinance.")
    source_type: Literal["news", "macro"] = "news"
    title: str = Field(min_length=1)
    source_url: HttpUrl | None = None
    publisher: str | None = None
    published_at: datetime | None = None
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    summary: str = Field(
        default="",
        max_length=2_000,
        description="Bounded normalized excerpt; not a copy of the source document.",
    )
    raw_content_ref: str | None = Field(
        default=None,
        description="Optional external reference only; publisher-owned raw content is not stored.",
    )
    source_quality_score: float | None = Field(
        default=None,
        ge=0,
        le=1,
        description="Provider-authority score assigned by the normalizer.",
    )
    schema_version: Literal[1] = 1

    @model_validator(mode="after")
    def _assign_id(self) -> Evidence:
        """Derive a stable ID from source identity, not retrieval time."""
        if self.id is None:
            identity = "\x1f".join(
                (
                    self.provider_id.strip().lower(),
                    str(self.source_url or "").strip(),
                    self.title.strip().lower(),
                    self.published_at.isoformat() if self.published_at else "",
                )
            )
            self.id = f"ev_{sha256(identity.encode('utf-8')).hexdigest()[:24]}"
        return self
