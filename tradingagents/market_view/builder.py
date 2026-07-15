"""Build a :class:`MarketView` from macro data + headlines via a structured LLM call.

The builder is deliberately decoupled: it takes the LLM and a ``gather_context``
callable, so tests inject a stub LLM and canned context with no network or model
access. The default context gatherer pulls a curated set of FRED macro series
and global headlines through the same vendor-routing layer the analysts use, so
the market view honours the user's configured data vendors.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from functools import partial
from typing import Any

from tradingagents.agents.utils.agent_utils import get_language_instruction
from tradingagents.agents.utils.structured import bind_structured

from .schemas import MarketRegime, MarketView, SizingBias

logger = logging.getLogger(__name__)

# Curated macro backdrop: policy rate, curve, inflation, labor, growth, and the
# market's fear gauge. Friendly aliases resolved by get_macro_indicators.
_DEFAULT_INDICATORS: tuple[str, ...] = (
    "fed_funds_rate",
    "10y_treasury",
    "yield_curve",
    "cpi",
    "core_pce",
    "unemployment",
    "real_gdp",
    "vix",
)


def default_macro_context(
    trade_date: str,
    config: dict | None = None,  # noqa: ARG001 — kept for a stable gatherer signature
    *,
    indicators: tuple[str, ...] | None = None,
) -> str:
    """Gather the macro backdrop + global headlines as one markdown blob.

    Each fetch is isolated: a single failing indicator degrades to a note
    rather than aborting the whole view (macro/prediction categories already
    return sentinels instead of raising, this is belt-and-suspenders).
    """
    from tradingagents.dataflows.interface import route_to_vendor

    parts: list[str] = []
    for indicator in indicators or _DEFAULT_INDICATORS:
        try:
            body = route_to_vendor("get_macro_indicators", indicator, trade_date, None)
        except Exception as exc:  # noqa: BLE001
            body = f"(unavailable: {exc})"
        parts.append(f"### {indicator}\n{body}")

    try:
        news = route_to_vendor("get_global_news", trade_date, None, None)
    except Exception as exc:  # noqa: BLE001
        news = f"(unavailable: {exc})"
    parts.append(f"### Global macro headlines\n{news}")

    return "\n\n".join(parts)


def _build_prompt(trade_date: str, context: str, extra_context: str) -> str:
    extra = f"\n\nAdditional context:\n{extra_context}\n" if extra_context else ""
    return f"""You are the Chief Market Strategist forming the desk's top-down view for {trade_date}.

Synthesize the macro backdrop and headlines below into a single coherent view of
the market regime and the risk posture the desk should take. This view is a
*sizing lens*: it does not pick individual names, it sets how aggressively the
desk should add risk across the whole book today.

Ground every judgement in the data provided — cite the rate/inflation/growth/
volatility levels and the headlines that drive your read. Do not fabricate
numbers that are not present.

Macro & news context:
{context}
{extra}
Deliver the regime, sizing bias, confidence, a tight narrative, and the key
risks and tailwinds.{get_language_instruction()}"""


class MarketViewBuilder:
    """Produce a dated :class:`MarketView` from macro/news context via one LLM call."""

    def __init__(
        self,
        llm: Any,
        config: dict | None = None,
        *,
        gather_context: Callable[[str, dict | None], str] | None = None,
        indicators: tuple[str, ...] | None = None,
    ):
        self.llm = llm
        self.config = config
        self.structured_llm = bind_structured(llm, MarketView, "Market View")
        self._gather = gather_context or partial(default_macro_context, indicators=indicators)

    def build(self, trade_date: str, *, extra_context: str = "") -> MarketView:
        """Build the market view for ``trade_date``.

        Always returns a ``MarketView`` (never raises for a model/parse issue):
        a structured miss falls back to a low-confidence Neutral view carrying
        the free-text response, so a run is never blocked on the top-down layer.
        """
        context = self._gather(trade_date, self.config)
        prompt = _build_prompt(trade_date, context, extra_context)
        view = self._synthesize(prompt)
        # The system owns the date; never trust a model-supplied as_of.
        view.as_of = trade_date
        return view

    def _synthesize(self, prompt: str) -> MarketView:
        if self.structured_llm is not None:
            try:
                result = self.structured_llm.invoke(prompt)
                if result is None:
                    raise ValueError("structured output returned no parsed result")
                return result
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "Market View: structured-output invocation failed (%s); "
                    "falling back to a Neutral free-text view",
                    exc,
                )

        response = self.llm.invoke(prompt)
        narrative = getattr(response, "content", None) or str(response)
        return MarketView(
            regime=MarketRegime.NEUTRAL,
            sizing_bias=SizingBias.NEUTRAL,
            confidence="low",
            narrative=narrative.strip()[:4000] or "Market view unavailable.",
        )
