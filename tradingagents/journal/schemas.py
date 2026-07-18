"""Decision-journal domain objects."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field, field_validator


class DecisionType(str, Enum):
    OPEN = "open"
    ADD = "add"
    TRIM = "trim"
    HOLD = "hold"
    CLOSE = "close"
    WATCH = "watch"
    HEDGE = "hedge"
    AVOID = "avoid"


class DecisionJournalEntry(BaseModel):
    id: str | None = None
    symbol: str
    trade_date: str
    decision_type: DecisionType
    rationale: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    expected_horizon: str | None = None
    thesis_snapshot_id: str | None = None
    portfolio_snapshot_id: str | None = None
    analysis_run_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    catalyst_ids: list[str] = Field(default_factory=list)
    invalidation_condition_ids: list[str] = Field(default_factory=list)
    allow_lesson_reuse: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("symbol")
    @classmethod
    def _normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    def model_post_init(self, __context) -> None:
        if self.id is None:
            value = (
                f"{self.symbol}|{self.trade_date}|{self.decision_type.value}|"
                f"{self.thesis_snapshot_id or ''}|"
                f"{self.portfolio_snapshot_id or ''}"
            )
            self.id = f"dj_{sha256(value.encode()).hexdigest()[:20]}"


class OutcomeReview(BaseModel):
    """Post-decision review with optional benchmark-relative results."""

    id: str | None = None
    journal_entry_id: str
    workspace_id: str | None = None
    reviewed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    as_of: str
    outcome_summary: str
    lesson: str = ""
    allow_lesson_reuse: bool = True
    absolute_return_pct: float | None = None
    benchmark_ticker: str | None = "SPY"
    benchmark_return_pct: float | None = None
    relative_return_pct: float | None = None
    schema_version: int = 1

    def model_post_init(self, __context) -> None:
        if (
            self.relative_return_pct is None
            and self.absolute_return_pct is not None
            and self.benchmark_return_pct is not None
        ):
            self.relative_return_pct = self.absolute_return_pct - self.benchmark_return_pct
        if self.id is None:
            digest = sha256(
                f"{self.journal_entry_id}|{self.as_of}|{self.reviewed_at.isoformat()}".encode()
            ).hexdigest()[:20]
            self.id = f"or_{digest}"
