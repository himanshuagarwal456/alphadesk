"""Versioned LLM pricing estimates (USD per 1M tokens).

Unknown models return ``None`` rather than a fake zero cost.
"""

from __future__ import annotations

from tradingagents.observability.usage import UsageStats

# Approximate public list prices; operators can override via config later.
# Keys are lowercase substrings matched against model ids.
PRICING_TABLE_VERSION = "pricing-v1"

_MODEL_RATES_USD_PER_1M: dict[str, tuple[float, float]] = {
    # (input, output)
    "gpt-4o-mini": (0.15, 0.60),
    "gpt-4o": (2.50, 10.00),
    "gpt-4.1-mini": (0.40, 1.60),
    "gpt-4.1": (2.00, 8.00),
    "o3-mini": (1.10, 4.40),
    "o4-mini": (1.10, 4.40),
    "claude-3-5-haiku": (0.80, 4.00),
    "claude-3-5-sonnet": (3.00, 15.00),
    "claude-sonnet-4": (3.00, 15.00),
    "claude-opus-4": (15.00, 75.00),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-2.5-flash": (0.15, 0.60),
    "gemini-2.5-pro": (1.25, 10.00),
    "deepseek-chat": (0.27, 1.10),
    "deepseek-reasoner": (0.55, 2.19),
}


def _rates_for_model(model: str | None) -> tuple[float, float] | None:
    if not model:
        return None
    needle = model.strip().lower()
    for key, rates in _MODEL_RATES_USD_PER_1M.items():
        if key in needle:
            return rates
    return None


def estimate_llm_cost_usd(
    *,
    tokens_in: int,
    tokens_out: int,
    model: str | None = None,
    deep_think_llm: str | None = None,
    quick_think_llm: str | None = None,
) -> float | None:
    """Estimate USD cost from token counts.

    Prefers an explicit ``model``. Otherwise blends deep/quick models when both
    are known; if only one is priced, that rate is used for all tokens.
    """
    primary = _rates_for_model(model)
    if primary is not None:
        inn, out = primary
        return round((tokens_in / 1_000_000) * inn + (tokens_out / 1_000_000) * out, 6)

    deep = _rates_for_model(deep_think_llm)
    quick = _rates_for_model(quick_think_llm)
    if deep is None and quick is None:
        return None
    if deep is None:
        inn, out = quick  # type: ignore[misc]
    elif quick is None:
        inn, out = deep
    else:
        # Split roughly 60/40 deep/quick when both are configured.
        inn = deep[0] * 0.6 + quick[0] * 0.4
        out = deep[1] * 0.6 + quick[1] * 0.4
    return round((tokens_in / 1_000_000) * inn + (tokens_out / 1_000_000) * out, 6)


def attach_cost_estimate(
    stats: UsageStats,
    *,
    deep_think_llm: str | None = None,
    quick_think_llm: str | None = None,
) -> UsageStats:
    cost = estimate_llm_cost_usd(
        tokens_in=stats.tokens_in,
        tokens_out=stats.tokens_out,
        deep_think_llm=deep_think_llm,
        quick_think_llm=quick_think_llm,
    )
    stats.estimated_cost_usd = cost
    return stats
