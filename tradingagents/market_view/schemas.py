"""Structured top-down market view: the desk's macro regime and risk posture.

Where :mod:`tradingagents.portfolio` is bottom-up (what do we hold, what is a
given name worth), the market view is the top-down lens: what regime are we in,
how much risk should the desk be taking overall, and what are the dominant
macro tailwinds and risks. It is produced once per run date (see
:mod:`.builder`) and injected as a *sizing lens* into every per-name decision.

Design mirrors :mod:`tradingagents.agents.schemas`: field descriptions double
as the model's output instructions, and a ``render`` method turns the parsed
instance back into the plain-text block the rest of the system consumes (it
flows through as the ``market_view`` string on ``propagate`` / ``run_book`` and
is wrapped into the Portfolio Manager prompt by
``tradingagents.portfolio.context.render_market_view``).
"""

from __future__ import annotations

from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class MarketRegime(str, Enum):
    """Coarse read on the prevailing market environment."""

    RISK_ON = "Risk-On"
    NEUTRAL = "Neutral"
    RISK_OFF = "Risk-Off"


class SizingBias(str, Enum):
    """How aggressively the desk should size new/added risk given the regime."""

    AGGRESSIVE = "Aggressive"  # lean into new risk
    NEUTRAL = "Neutral"        # size normally
    DEFENSIVE = "Defensive"    # trim / smaller sizing / raise cash


class MarketView(BaseModel):
    """A dated, top-down view of the market used as a sizing lens.

    The analytic fields are filled by the builder's LLM call; ``as_of`` is set
    by the system after parsing (the model is told to leave it null), so the
    date is always authoritative rather than hallucinated.
    """

    as_of: str | None = Field(
        default=None,
        description="Run date (YYYY-MM-DD). Leave null — the system sets this.",
    )
    regime: MarketRegime = Field(
        description=(
            "Overall market regime. Exactly one of Risk-On / Neutral / Risk-Off, "
            "based on the macro data and headlines provided."
        ),
    )
    sizing_bias: SizingBias = Field(
        description=(
            "How the desk should size risk in this regime. Exactly one of "
            "Aggressive / Neutral / Defensive. Risk-Off usually implies "
            "Defensive, Risk-On usually Aggressive, but justify from the data."
        ),
    )
    confidence: Literal["low", "medium", "high"] = Field(
        description=(
            "Confidence in this view given data quality and signal agreement. "
            "'low' when data was sparse or conflicting, 'high' when macro and "
            "news align clearly."
        ),
    )
    narrative: str = Field(
        description=(
            "The macro narrative: 3–6 sentences tying the rates, inflation, "
            "growth, and volatility picture together with the day's headlines "
            "into a coherent story about where the market is and why."
        ),
    )
    key_risks: list[str] = Field(
        default_factory=list,
        description="Bullet list of the dominant downside risks / things that could break the view.",
    )
    tailwinds: list[str] = Field(
        default_factory=list,
        description="Bullet list of supportive factors currently favouring risk assets.",
    )

    def render(self) -> str:
        """Render to the plain-text block passed as the ``market_view`` string.

        Deterministic given the field values, so a persisted view renders
        identically across runs (reproducibility requirement).
        """
        lines = [
            f"Regime: {self.regime.value} | Sizing bias: {self.sizing_bias.value} "
            f"| Confidence: {self.confidence}",
        ]
        if self.as_of:
            lines.append(f"As of: {self.as_of}")
        lines.append("")
        lines.append(self.narrative.strip())
        if self.tailwinds:
            lines.append("")
            lines.append("Tailwinds:")
            lines.extend(f"- {t}" for t in self.tailwinds)
        if self.key_risks:
            lines.append("")
            lines.append("Key risks:")
            lines.extend(f"- {r}" for r in self.key_risks)
        return "\n".join(lines).strip()
