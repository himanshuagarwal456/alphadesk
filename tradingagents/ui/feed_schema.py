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


class LearnMoreBrief(BaseModel):
    """Card-first Learn More briefing — explains *this* card, then optional terms."""

    title: str = Field(description="Card title shown in the drawer header.")
    headline: str = Field(default="", description="The claim or hook on the card.")
    what_this_means: str = Field(
        description="Plain-language unpacking of the card content itself."
    )
    why_it_matters: str = Field(
        description="Why this card matters for the symbol, thesis, or book."
    )
    what_to_check: str = Field(
        default="",
        description="Concrete next questions so the user can act on the card.",
    )
    agent_takeaways: list[str] = Field(
        default_factory=list,
        description="Short quotes from the most relevant agent comments.",
    )
    concepts: list[LearnMoreItem] = Field(
        default_factory=list,
        description="Supporting glossary terms found in the card language.",
    )


class AgentComment(BaseModel):
    """A short agent take shown in the Facebook-style comment thread on a card."""

    agent: str = Field(description="Display name, e.g. 'Market Analyst'.")
    text: str = Field(description="One or two sentences attributed to this agent.")
    role: str = Field(
        default="",
        description="Optional role chip, e.g. 'Bull', 'Bear', 'PM'.",
    )


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
    body: str = Field(default="", description="Longer text retained for APIs; UI prefers comments.")
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
    comments: list[AgentComment] = Field(
        default_factory=list,
        description="Most relevant agent takes for this card (not every agent).",
    )
    learn_brief: LearnMoreBrief | None = Field(
        default=None,
        description="Card-first Learn More briefing (content unpack + optional terms).",
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
        description="Legacy concept list; prefer learn_brief.concepts when present.",
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
