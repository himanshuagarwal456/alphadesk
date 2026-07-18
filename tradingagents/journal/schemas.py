"""Decision-journal domain objects."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from hashlib import sha256

from pydantic import BaseModel, Field


class DecisionType(str, Enum):
    OPEN = "open"
    ADD = "add"
    TRIM = "trim"
    HOLD = "hold"
    CLOSE = "close"
    WATCH = "watch"


class DecisionJournalEntry(BaseModel):
    id: str | None = None
    symbol: str
    trade_date: str
    decision_type: DecisionType
    rationale: str
    confidence: float | None = Field(default=None, ge=0, le=1)
    thesis_snapshot_id: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    catalyst_ids: list[str] = Field(default_factory=list)
    invalidation_condition_ids: list[str] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def model_post_init(self, __context) -> None:
        if self.id is None:
            value = f"{self.symbol.upper()}|{self.trade_date}|{self.decision_type.value}"
            self.id = f"dj_{sha256(value.encode()).hexdigest()[:20]}"
