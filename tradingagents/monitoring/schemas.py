"""Monitoring domain models (Phase 8)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, model_validator


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


class CardStatus(str, Enum):
    NEW = "new"
    REVIEWED = "reviewed"
    SAVED = "saved"
    DISMISSED = "dismissed"


class MonitorKind(str, Enum):
    SEC_FILINGS = "sec_filings"
    COMPANY_NEWS = "company_news"
    MACRO = "macro"
    PRICE_TRIGGER = "price_trigger"
    THESIS_TRIGGER = "thesis_trigger"
    MANUAL = "manual"


class MonitorRunStatus(str, Enum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class NotificationStatus(str, Enum):
    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"


class MonitorDefinition(BaseModel):
    id: str | None = None
    workspace_id: str
    kind: MonitorKind
    name: str = Field(min_length=1)
    enabled: bool = True
    symbols: list[str] = Field(default_factory=list)
    queue_targeted_analysis: bool = False
    config: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _normalize(self) -> MonitorDefinition:
        self.symbols = sorted({s.strip().upper() for s in self.symbols if s and s.strip()})
        if self.id is None:
            self.id = _stable_id("mon", self.workspace_id, self.kind.value, self.name.lower())
        return self


class DetectedEvent(BaseModel):
    """Normalized inbound signal before materiality / dedup."""

    id: str | None = None
    workspace_id: str
    symbol: str
    source: str = Field(min_length=1)
    event_type: str = Field(min_length=1)
    title: str = Field(min_length=1)
    summary: str = ""
    url: str | None = None
    evidence_id: str | None = None
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict = Field(default_factory=dict)
    schema_version: int = 1

    @model_validator(mode="after")
    def _normalize(self) -> DetectedEvent:
        self.symbol = self.symbol.strip().upper()
        if self.id is None:
            seed = self.evidence_id or f"{self.source}|{self.title}|{self.occurred_at.isoformat()}"
            self.id = _stable_id("mev", self.workspace_id, self.symbol, seed)
        return self


class MaterialityVerdict(BaseModel):
    material: bool
    score: float = Field(ge=0.0, le=1.0)
    reason: str
    impact_key: str = "general"
    should_queue_analysis: bool = False


class MonitorRun(BaseModel):
    id: str | None = None
    workspace_id: str
    monitor_id: str | None = None
    status: MonitorRunStatus = MonitorRunStatus.RUNNING
    events_seen: int = 0
    events_material: int = 0
    cards_created: int = 0
    duplicates_skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    payload: dict = Field(default_factory=dict)
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> MonitorRun:
        if self.id is None:
            self.id = _stable_id(
                "mrun",
                self.workspace_id,
                self.monitor_id or "all",
                self.started_at.isoformat(),
            )
        return self


class Notification(BaseModel):
    id: str | None = None
    workspace_id: str
    title: str
    body: str = ""
    symbol: str | None = None
    intelligence_card_id: str | None = None
    monitor_run_id: str | None = None
    status: NotificationStatus = NotificationStatus.UNREAD
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> Notification:
        if self.symbol:
            self.symbol = self.symbol.strip().upper()
        if self.id is None:
            self.id = _stable_id(
                "ntf",
                self.workspace_id,
                self.title,
                self.intelligence_card_id or "",
                self.created_at.isoformat(),
            )
        return self


class AlertFingerprint(BaseModel):
    workspace_id: str
    fingerprint: str
    intelligence_card_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
