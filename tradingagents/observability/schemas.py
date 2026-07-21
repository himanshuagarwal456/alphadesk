"""Ops / reliability domain records (Phase 11)."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, model_validator


def _stable_id(prefix: str, *parts: str) -> str:
    digest = sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:24]
    return f"{prefix}_{digest}"


class UsageRecord(BaseModel):
    """Persisted cost/usage sample for a research run or ops action."""

    id: str | None = None
    workspace_id: str
    analysis_run_id: str | None = None
    kind: str = "research_run"
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    provider_calls: int = 0
    provider_errors: int = 0
    estimated_cost_usd: float | None = None
    duration_ms: int | None = None
    pricing_version: str = "pricing-v1"
    model_provider: str | None = None
    deep_think_llm: str | None = None
    quick_think_llm: str | None = None
    trace_id: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> UsageRecord:
        if self.id is None:
            self.id = _stable_id(
                "usage",
                self.workspace_id,
                self.analysis_run_id or self.kind,
                self.created_at.isoformat(),
            )
        return self


class AuditEvent(BaseModel):
    id: str | None = None
    workspace_id: str
    actor: str = "system"
    action: str
    resource_type: str = ""
    resource_id: str = ""
    message: str = ""
    trace_id: str | None = None
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> AuditEvent:
        if self.id is None:
            self.id = _stable_id(
                "aud",
                self.workspace_id,
                self.action,
                self.resource_id,
                self.created_at.isoformat(),
            )
        return self


class DeadLetterStatus(str, Enum):
    OPEN = "open"
    REQUEUED = "requeued"
    DISCARDED = "discarded"


class DeadLetterRecord(BaseModel):
    id: str | None = None
    workspace_id: str
    analysis_run_id: str
    attempts: int = 0
    last_error: str = ""
    status: DeadLetterStatus = DeadLetterStatus.OPEN
    payload: dict = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    @model_validator(mode="after")
    def _assign_id(self) -> DeadLetterRecord:
        if self.id is None:
            self.id = _stable_id("dlq", self.workspace_id, self.analysis_run_id)
        return self


class UsageSummary(BaseModel):
    workspace_id: str
    runs: int = 0
    llm_calls: int = 0
    tool_calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    provider_calls: int = 0
    provider_errors: int = 0
    estimated_cost_usd: float = 0.0
    duration_ms: int = 0
    pricing_version: str = "pricing-v1"
