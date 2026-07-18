"""Watchlist and portfolio-product controls (Phase 5)."""

from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256

from pydantic import BaseModel, Field, field_validator


class WatchlistItem(BaseModel):
    symbol: str
    monitoring_enabled: bool = True
    notes: str = ""

    @field_validator("symbol")
    @classmethod
    def _normalize(cls, value: str) -> str:
        normalized = (value or "").strip().upper()
        if not normalized:
            raise ValueError("symbol must be non-empty")
        return normalized


class Watchlist(BaseModel):
    id: str | None = None
    name: str = Field(min_length=1)
    workspace_id: str | None = None
    items: list[WatchlistItem] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    schema_version: int = 1

    def model_post_init(self, __context) -> None:
        # Deduplicate by symbol, last write wins.
        by_symbol = {item.symbol: item for item in self.items}
        self.items = sorted(by_symbol.values(), key=lambda item: item.symbol)
        if self.id is None:
            seed = f"{self.workspace_id or ''}|{self.name.strip().lower()}"
            self.id = f"wl_{sha256(seed.encode()).hexdigest()[:20]}"


class PortfolioControls(BaseModel):
    """Product-level switches for the workspace book.

    Alpha portfolios are research-only: they never execute transactions.
    """

    monitoring_enabled: bool = True
    research_only: bool = True
    current_snapshot_id: str | None = None
