"""The feed contract: ``Feed`` -> ``Narrative`` (story) -> ``Card``.

Layout maps onto a two-axis UX inspired by social feeds:

- **Vertical scroll = stories.** Each story is a distinct post block
  (desk brief, theme, or multi-name cluster), ranked by ``dominance``.
- **Horizontal scroll = cards.** The album tells one complete arc:
  high-level commentary -> who is affected -> evidence -> tension -> verdict.

Stories are **not** one-per-symbol. A single narrative can cover several
tickers; ``symbols`` lists every name the story touches.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, model_validator

from tradingagents.evidence import Evidence

from .chart_spec import ChartSpec
from .visualization_intent import VisualizationIntent


class LearnMoreResource(BaseModel):
    title: str
    provider: str
    url: str


class LearnMoreItem(BaseModel):
    """Offline concept payload for Learn More on feed cards."""

    concept_id: str
    slug: str
    title: str
    short_definition: str
    explanation: str
    why_it_matters: str = ""
    difficulty: str = "beginner"
    estimated_read_time: int = 3
    resources: list[LearnMoreResource] = Field(default_factory=list)


class CardKind(str, Enum):
    """Where a card sits in the narrative arc (drives styling + ordering)."""

    HOOK = "hook"  # high-level commentary — the scroll-stopper
    CONTEXT = "context"  # who is affected / book framing
    EVIDENCE = "evidence"  # supporting findings
    TENSION = "tension"  # conflict / bull vs bear
    VERDICT = "verdict"  # what to do next


class Card(BaseModel):
    """One swipeable panel: a visual and/or a one–two line hook."""

    id: str
    kind: CardKind
    title: str = Field(description="Short label, e.g. 'Desk brief', 'Affected', 'Verdict'.")
    headline: str = Field(description="The 1–2 line hook shown large on the card.")
    body: str = Field(default="", description="Longer text revealed on expand/tap.")
    badges: list[str] = Field(
        default_factory=list,
        description="Short chips, e.g. 'Underweight', '18% of book', 'NVDA'.",
    )
    symbols: list[str] = Field(
        default_factory=list,
        description="Tickers this card specifically references.",
    )
    chart: dict | None = Field(
        default=None,
        description="A Plotly figure as a plain dict (figure.to_json()); None for text-only.",
    )
    card_type: str | None = Field(
        default=None,
        description="Intelligence claim type, e.g. event, risk, thesis_change.",
    )
    evidence_ids: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)
    portfolio_impact: str | None = None
    confidence: float | None = Field(default=None, ge=0, le=1)
    source_quality_score: float | None = Field(default=None, ge=0, le=1)
    freshness_score: float | None = Field(default=None, ge=0, le=1)
    materiality_score: float | None = Field(default=None, ge=0, le=1)
    novelty_score: float | None = Field(default=None, ge=0, le=1)
    visualization_intent: VisualizationIntent | None = None
    chart_spec: ChartSpec | None = None
    learn_more: list[LearnMoreItem] = Field(
        default_factory=list,
        description="Embedded Learn More concepts for deep understanding on this card.",
    )


class Narrative(BaseModel):
    """One vertical feed post: a complete story that may span many symbols."""

    id: str
    title: str = Field(description="Story headline, e.g. 'Desk brief — trim three held names'.")
    summary: str = Field(default="", description="One-liner under the title.")
    symbols: list[str] = Field(
        default_factory=list,
        description="Every ticker this story affects (chips in the post header).",
    )
    symbol: str = Field(
        default="",
        description="Primary symbol when the story is single-name; else empty.",
    )
    dominance: float = Field(
        default=0.0,
        description="Vertical-rank score; higher surfaces earlier in the feed.",
    )
    badges: list[str] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    meta: dict = Field(
        default_factory=dict,
        description="story_kind, trade_date, held_count, etc.",
    )

    @model_validator(mode="after")
    def _normalize_symbols(self) -> Narrative:
        merged = list(self.symbols)
        if self.symbol:
            merged.insert(0, self.symbol.strip().upper())
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw in merged:
            sym = str(raw).strip().upper()
            if not sym or sym in seen:
                continue
            seen.add(sym)
            cleaned.append(sym)
        self.symbols = cleaned
        if not self.symbol and len(cleaned) == 1:
            self.symbol = cleaned[0]
        return self


class Feed(BaseModel):
    """The whole feed: stories ordered by dominance (loudest first)."""

    as_of: str | None = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    narratives: list[Narrative] = Field(default_factory=list)

    def ranked(self) -> Feed:
        """Return a copy with stories sorted by dominance descending (stable)."""
        ordered = sorted(self.narratives, key=lambda n: n.dominance, reverse=True)
        return self.model_copy(update={"narratives": ordered})
