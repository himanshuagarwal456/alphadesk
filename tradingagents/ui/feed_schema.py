"""The feed contract: ``Feed`` -> ``Narrative`` -> ``Card``.

This is the stable hand-off between the Python side (agents generate knowledge,
the deck builder turns it into cards) and the front-end (renders a swipeable
feed). Everything the UI needs is here and JSON-serialisable, so the renderer —
today a self-contained HTML page, tomorrow a React app — only ever consumes this
contract.

Layout maps directly onto the two-axis UX:

- **Vertical scroll = narratives.** ``Feed.narratives`` is ordered by
  ``dominance`` (highest first), so the loudest story leads.
- **Horizontal scroll = cards.** ``Narrative.cards`` is the album/carousel that
  builds one story as an arc: hook -> evidence -> tension -> verdict.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field

from tradingagents.evidence import Evidence

from .chart_spec import ChartSpec
from .visualization_intent import VisualizationIntent


class CardKind(str, Enum):
    """Where a card sits in the narrative arc (drives styling + ordering)."""

    HOOK = "hook"          # the narrative in one visual — the scroll-stopper
    CONTEXT = "context"    # supporting backdrop (e.g. the price chart)
    EVIDENCE = "evidence"  # an analyst finding that supports the thesis
    TENSION = "tension"    # bull vs bear / risk — the conflict
    VERDICT = "verdict"    # the decision + what it means for your book


class Card(BaseModel):
    """One swipeable panel: a visual and/or a one–two line hook."""

    id: str
    kind: CardKind
    title: str = Field(description="Short label, e.g. 'Market', 'Sentiment', 'Verdict'.")
    headline: str = Field(description="The 1–2 line hook shown large on the card.")
    body: str = Field(default="", description="Longer text revealed on expand/tap.")
    badges: list[str] = Field(
        default_factory=list,
        description="Short chips, e.g. 'Underweight', '18% of book', 'Risk-Off'.",
    )
    chart: dict | None = Field(
        default=None,
        description="A Plotly figure as a plain dict (figure.to_dict()); None for text-only cards.",
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


class Narrative(BaseModel):
    """A single story (v1: one per name) rendered as a horizontal album of cards."""

    id: str
    symbol: str
    title: str = Field(description="Headline of the narrative, e.g. 'NVDA — verdict: Underweight'.")
    summary: str = Field(default="", description="One-liner describing the story.")
    dominance: float = Field(
        default=0.0,
        description="Vertical-rank score; higher surfaces earlier in the feed.",
    )
    badges: list[str] = Field(default_factory=list)
    cards: list[Card] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict, description="trade_date, stance, held, etc.")


class Feed(BaseModel):
    """The whole feed: narratives ordered by dominance (loudest first)."""

    as_of: str | None = None
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    narratives: list[Narrative] = Field(default_factory=list)

    def ranked(self) -> Feed:
        """Return a copy with narratives sorted by dominance descending (stable)."""
        ordered = sorted(self.narratives, key=lambda n: n.dominance, reverse=True)
        return self.model_copy(update={"narratives": ordered})
