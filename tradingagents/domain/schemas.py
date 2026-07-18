"""Canonical domain records shared by the product layers.

These are the stable contracts from ``docs/alpha-release.md`` §6 that every
later feature (persistence, monitoring, the web app) builds on. They follow
the repo's evidence-layer conventions: immutable-by-convention Pydantic
records, stable content-derived IDs, explicit ``schema_version`` fields, and
JSON-safe serialization. Markdown remains a presentation format only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, model_validator


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


class OwnershipClass(str, Enum):
    """Who may see a record; propagates from source to derived content."""

    PUBLIC = "public"
    PRIVATE = "private"
    LICENSED = "licensed"


class Instrument(BaseModel):
    """A tradeable security identity, independent of any one vendor's symbol."""

    id: str | None = None
    symbol: str = Field(min_length=1)
    name: str | None = None
    asset_type: str = "stock"
    exchange: str | None = None
    currency: str = "USD"
    cik: str | None = Field(default=None, description="SEC CIK when US-listed.")
    schema_version: int = 1

    @model_validator(mode="after")
    def _normalize(self) -> Instrument:
        self.symbol = self.symbol.strip().upper()
        if self.id is None:
            self.id = _stable_id("in", self.symbol, self.exchange or "", self.asset_type)
        return self


class SourceRecord(BaseModel):
    """A raw retrieval event: what was fetched, from where, when, and who owns it.

    ``Evidence`` is the normalized excerpt; a ``SourceRecord`` is the retrieval
    provenance it derives from. Providers that already emit ``Evidence`` can
    attach one via ``evidence.raw_content_ref`` until they migrate fully.
    """

    id: str | None = None
    provider_id: str
    source_type: str = "news"
    source_url: str | None = None
    title: str | None = None
    content_hash: str | None = Field(
        default=None, description="SHA-256 of retrieved content, for deduplication."
    )
    ownership: OwnershipClass = OwnershipClass.PUBLIC
    workspace_id: str | None = Field(
        default=None, description="Owning workspace for private sources; None = shared."
    )
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> SourceRecord:
        if self.id is None:
            self.id = _stable_id(
                "sr",
                self.provider_id.strip().lower(),
                str(self.source_url or ""),
                self.content_hash or (self.title or ""),
            )
        return self


class Claim(BaseModel):
    """One material assertion, always traceable to supporting evidence."""

    id: str | None = None
    text: str = Field(min_length=1)
    evidence_ids: list[str] = Field(
        default_factory=list,
        description="Supporting Evidence IDs. Empty means the claim is unsupported.",
    )
    confidence: float | None = Field(default=None, ge=0, le=1)
    analysis_run_id: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @property
    def supported(self) -> bool:
        return bool(self.evidence_ids)

    @model_validator(mode="after")
    def _assign_id(self) -> Claim:
        self.evidence_ids = sorted(set(self.evidence_ids))
        if self.id is None:
            self.id = _stable_id("cl", self.text.strip().lower(), *self.evidence_ids)
        return self


class RunStatus(str, Enum):
    """Durable research-job lifecycle (alpha brief, Phase 3)."""

    QUEUED = "queued"
    RUNNING = "running"
    PARTIAL = "partially_completed"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AnalysisRun(BaseModel):
    """A durable record of one research run over one instrument."""

    id: str | None = None
    symbol: str = Field(min_length=1)
    trade_date: str
    status: RunStatus = RunStatus.COMPLETED
    selected_analysts: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    final_rating: str | None = None
    thesis_snapshot_id: str | None = None
    # Structured / rendered decision retained so theses can be created from a
    # completed run without re-invoking the graph (Phase 6).
    portfolio_decision_struct: dict | None = None
    final_trade_decision: str | None = None
    bull_case: str = ""
    bear_case: str = ""
    risks: list[str] = Field(default_factory=list)
    # Model / prompt governance (Phase 10) — recorded on every durable run.
    model_provider: str | None = None
    deep_think_llm: str | None = None
    quick_think_llm: str | None = None
    prompt_version: str | None = None
    eval_suite_version: str | None = None
    error: str | None = None
    workspace_id: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _normalize(self) -> AnalysisRun:
        self.symbol = self.symbol.strip().upper()
        self.evidence_ids = sorted(set(self.evidence_ids))
        if self.id is None:
            self.id = _stable_id("ar", self.symbol, self.trade_date)
        return self


class RunEvent(BaseModel):
    """One progress / lifecycle event for a durable analysis run."""

    id: str | None = None
    analysis_run_id: str
    workspace_id: str
    sequence: int = Field(ge=0)
    event_type: str = Field(min_length=1)
    message: str = ""
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> RunEvent:
        if self.id is None:
            self.id = _stable_id(
                "re",
                self.workspace_id,
                self.analysis_run_id,
                str(self.sequence),
                self.event_type,
            )
        return self


class Workspace(BaseModel):
    """Tenant boundary for all user-owned product records."""

    id: str
    name: str = Field(min_length=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1


class IntelligenceCardRecord(BaseModel):
    """Persisted intelligence card projection (workspace-scoped)."""

    id: str
    workspace_id: str
    symbol: str | None = None
    card_type: str | None = None
    title: str = ""
    headline: str = ""
    body: str = ""
    evidence_ids: list[str] = Field(default_factory=list)
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1
