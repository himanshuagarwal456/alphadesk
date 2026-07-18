"""Private user-owned research documents (Phase 7)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, field_validator


class DocumentKind(str, Enum):
    MARKDOWN = "markdown"
    TEXT = "text"
    CSV = "csv"
    PDF = "pdf"


class PrivateDocument(BaseModel):
    id: str | None = None
    workspace_id: str
    title: str = Field(min_length=1)
    filename: str
    kind: DocumentKind
    content_hash: str
    content_type: str
    size_bytes: int = Field(ge=0)
    object_key: str
    extracted_text: str = ""
    symbols: list[str] = Field(default_factory=list)
    themes: list[str] = Field(default_factory=list)
    evidence_id: str | None = None
    source_record_id: str | None = None
    ownership: str = "private"
    deleted: bool = False
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @field_validator("symbols", "themes")
    @classmethod
    def _normalize_tags(cls, values: list[str]) -> list[str]:
        return sorted({v.strip().upper() if isinstance(v, str) else v for v in values if v})

    def model_post_init(self, __context) -> None:
        if self.id is None:
            digest = sha256(
                f"{self.workspace_id}|{self.content_hash}|{self.filename}".encode()
            ).hexdigest()[:24]
            self.id = f"pd_{digest}"


class DocumentSearchHit(BaseModel):
    document: PrivateDocument
    snippet: str
