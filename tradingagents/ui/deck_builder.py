"""Turn a completed agent run into a feed narrative (v1: one per name).

The agents already emit their knowledge into the run's ``final_state`` (analyst
reports, the bull/bear debate, the risk debate, the Portfolio Manager's rating).
This module reads that structured knowledge, extracts the few hard signals worth
visualising (rating, sentiment score, price target/stop), and assembles the
narrative arc:

    hook -> market -> sentiment -> fundamentals -> tension (bull/bear) -> verdict

Each card carries a Plotly figure (as a JSON-safe dict) and a one–two line hook.
Portfolio awareness threads through as framing ("18% of book") and as the
dominance score that ranks the vertical feed. Everything here is pure: given the
same ``final_state`` (+ portfolio + OHLCV) it produces the same narrative.
"""

from __future__ import annotations

import json
import re
from typing import Any

import plotly.graph_objects as go

from . import charts
from .feed_schema import Card, CardKind, Feed, Narrative

_RATING_VALUE = {"sell": 0, "underweight": 1, "hold": 2, "overweight": 3, "buy": 4}


def _fig_to_dict(fig: go.Figure) -> dict:
    """JSON-safe plain dict (handles numpy/pandas via plotly's encoder)."""
    return json.loads(fig.to_json())


def parse_rating(text: str) -> str | None:
    """Extract a 5-tier rating from PM/verdict markdown."""
    if not text:
        return None
    m = re.search(r"\*\*Rating\*\*:\s*([A-Za-z]+)", text)
    if not m:
        m = re.search(r"\bRating\b:?\s*\*{0,2}(Buy|Overweight|Hold|Underweight|Sell)", text, re.I)
    if not m:
        m = re.search(r"FINAL TRANSACTION PROPOSAL:\s*\*{0,2}(BUY|HOLD|SELL)", text, re.I)
    if not m:
        return None
    word = m.group(1).strip().capitalize()
    return word if word.lower() in _RATING_VALUE else None


def parse_sentiment(text: str) -> tuple[float | None, str | None]:
    """Extract (score 0–10, band) from a rendered sentiment report."""
    if not text:
        return None, None
    score = None
    m = re.search(r"Score:\s*([0-9]+(?:\.[0-9]+)?)\s*/\s*10", text)
    if m:
        score = float(m.group(1))
    band = None
    b = re.search(r"Overall Sentiment:\*{0,2}\s*\*{0,2}([A-Za-z ]+?)\*{0,2}\s*\(", text)
    if b:
        band = b.group(1).strip()
    return score, band


def _parse_money(text: str, label: str) -> float | None:
    if not text:
        return None
    m = re.search(rf"{label}\*{{0,2}}:?\s*\*{{0,2}}\$?\s*([0-9]+(?:,[0-9]{{3}})*(?:\.[0-9]+)?)", text, re.I)
    if not m:
        return None
    try:
        return float(m.group(1).replace(",", ""))
    except ValueError:
        return None


def _first_sentence(text: str, limit: int = 160) -> str:
    """A compact hook from a report body."""
    if not text:
        return ""
    # Drop markdown headers/bold markers for a clean one-liner.
    cleaned = re.sub(r"[#*`>]", "", text).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    m = re.search(r"(.+?[.!?])(\s|$)", cleaned)
    sentence = m.group(1) if m else cleaned
    return sentence[:limit].strip()


def compute_dominance(
    *,
    rating: str | None,
    sentiment_score: float | None,
    portfolio_weight: float | None,
    held: bool,
) -> float:
    """Vertical-rank score: signal magnitude + portfolio impact.

    - Conviction: distance of the rating from Hold (0..2).
    - Sentiment extremity: distance of the score from neutral 5 (0..~1).
    - Portfolio impact: held names are boosted, weighted by book weight.
    """
    conviction = abs(_RATING_VALUE.get((rating or "").lower(), 2) - 2)  # 0..2
    extremity = abs((sentiment_score if sentiment_score is not None else 5.0) - 5.0) / 5.0  # 0..1
    impact = (1.0 + 4.0 * (portfolio_weight or 0.0)) if held else 0.0
    return round(conviction + extremity + impact, 4)


def build_narrative(
    final_state: dict[str, Any],
    *,
    portfolio: Any = None,
    ohlcv=None,
) -> Narrative:
    """Assemble the single-name narrative arc from one run's ``final_state``."""
    symbol = (final_state.get("company_of_interest") or "?").upper()
    trade_date = final_state.get("trade_date", "")

    verdict_md = final_state.get("final_trade_decision", "") or ""
    trader_md = final_state.get("trader_investment_plan", "") or ""
    rating = parse_rating(verdict_md) or parse_rating(trader_md)
    target = _parse_money(verdict_md, "Price Target") or _parse_money(trader_md, "Entry Price")
    stop = _parse_money(trader_md, "Stop Loss")
    sent_score, sent_band = parse_sentiment(final_state.get("sentiment_report", ""))

    # Portfolio framing.
    held = bool(portfolio is not None and getattr(portfolio, "holds", lambda _s: False)(symbol))
    weight = None
    badges: list[str] = []
    if rating:
        badges.append(rating)
    if held:
        weight = portfolio.weights().get(symbol)
        if weight is not None:
            badges.append(f"{weight * 100:.0f}% of book")
        badges.append("Held")

    cards: list[Card] = []

    # --- HOOK: price chart with the thesis drawn on it + the verdict headline ---
    levels = []
    if target is not None:
        levels.append({"label": f"Target {target:g}", "value": target, "color": "#2ca02c"})
    if stop is not None:
        levels.append({"label": f"Stop {stop:g}", "value": stop, "color": "#d62728"})
    hook_headline = _verdict_hook(symbol, rating, verdict_md, held, weight)
    hook_chart = None
    if ohlcv is not None:
        hook_chart = _fig_to_dict(
            charts.price_chart(ohlcv, title=f"{symbol} — {trade_date}", levels=levels)
        )
    cards.append(Card(
        id=f"{symbol}-hook", kind=CardKind.HOOK, title=symbol,
        headline=hook_headline, badges=badges, chart=hook_chart,
    ))

    # --- EVIDENCE: market / technical ---
    if final_state.get("market_report"):
        chart = None
        if ohlcv is not None:
            chart = _fig_to_dict(charts.price_chart(ohlcv, bollinger=True, sma_windows=(20,)))
        cards.append(Card(
            id=f"{symbol}-market", kind=CardKind.EVIDENCE, title="Market",
            headline=_first_sentence(final_state["market_report"]),
            body=final_state["market_report"], chart=chart,
        ))

    # --- EVIDENCE: sentiment (gauge when we parsed a score) ---
    if final_state.get("sentiment_report"):
        chart = _fig_to_dict(charts.sentiment_gauge(sent_score, sent_band or "")) if sent_score is not None else None
        headline = (
            f"Sentiment: {sent_band} ({sent_score:.1f}/10)"
            if sent_score is not None and sent_band
            else _first_sentence(final_state["sentiment_report"])
        )
        cards.append(Card(
            id=f"{symbol}-sentiment", kind=CardKind.EVIDENCE, title="Sentiment",
            headline=headline, body=final_state["sentiment_report"], chart=chart,
        ))

    # --- EVIDENCE: fundamentals ---
    if final_state.get("fundamentals_report"):
        cards.append(Card(
            id=f"{symbol}-fundamentals", kind=CardKind.EVIDENCE, title="Fundamentals",
            headline=_first_sentence(final_state["fundamentals_report"]),
            body=final_state["fundamentals_report"],
        ))

    # --- EVIDENCE: news ---
    if final_state.get("news_report"):
        cards.append(Card(
            id=f"{symbol}-news", kind=CardKind.EVIDENCE, title="News",
            headline=_first_sentence(final_state["news_report"]),
            body=final_state["news_report"],
        ))

    # --- TENSION: bull vs bear, framed as a risk/reward band when priced ---
    debate = final_state.get("investment_debate_state") or {}
    if debate.get("bull_history") or debate.get("bear_history"):
        chart = None
        if ohlcv is not None and (target is not None or stop is not None):
            entry = float(charts._col(ohlcv, "close").iloc[-1])
            chart = _fig_to_dict(
                charts.scenario_bands(ohlcv, entry=entry, target=target, stop=stop,
                                      title="Risk / reward")
            )
        body = "\n\n".join(
            part for part in (
                f"**Bull**\n{debate.get('bull_history', '')}".strip(),
                f"**Bear**\n{debate.get('bear_history', '')}".strip(),
            ) if part
        )
        cards.append(Card(
            id=f"{symbol}-tension", kind=CardKind.TENSION, title="Bull vs Bear",
            headline="Where the bulls and bears disagree", body=body, chart=chart,
        ))

    # --- VERDICT: the decision dial + what it means for the book ---
    if verdict_md:
        cards.append(Card(
            id=f"{symbol}-verdict", kind=CardKind.VERDICT, title="Verdict",
            headline=hook_headline, body=verdict_md, badges=badges,
            chart=_fig_to_dict(charts.rating_dial(rating or "Hold")),
        ))

    dominance = compute_dominance(
        rating=rating, sentiment_score=sent_score, portfolio_weight=weight, held=held,
    )
    stance = "manage" if held else "initiate"
    return Narrative(
        id=f"{symbol}-{trade_date}", symbol=symbol,
        title=f"{symbol} — {rating}" if rating else symbol,
        summary=_first_sentence(verdict_md) or f"Latest read on {symbol}",
        dominance=dominance, badges=badges, cards=cards,
        meta={"trade_date": trade_date, "stance": stance, "held": held},
    )


def _verdict_hook(symbol, rating, verdict_md, held, weight) -> str:
    lead = _first_sentence(_strip_rating_line(verdict_md))
    if rating and lead:
        base = f"{symbol}: {rating}. {lead}"
    elif rating:
        base = f"{symbol}: {rating}."
    else:
        base = lead or f"Latest read on {symbol}"
    if held and weight is not None:
        base = f"{base}  (you hold {weight * 100:.0f}% of book here)"
    return base[:220]


def _strip_rating_line(text: str) -> str:
    """Drop the leading '**Rating**: X' line so the hook uses the summary prose."""
    return re.sub(r"\*\*Rating\*\*:.*?(\n|$)", "", text, count=1)


def build_feed(
    runs: list[dict[str, Any]],
    *,
    portfolio: Any = None,
    ohlcv_map: dict[str, Any] | None = None,
    as_of: str | None = None,
) -> Feed:
    """Build a dominance-ranked feed from one or more completed runs."""
    ohlcv_map = ohlcv_map or {}
    narratives = [
        build_narrative(
            state, portfolio=portfolio,
            ohlcv=ohlcv_map.get((state.get("company_of_interest") or "").upper()),
        )
        for state in runs
    ]
    return Feed(as_of=as_of, narratives=narratives).ranked()
