"""Turn completed agent runs into a social-style story feed.

Each vertical post is a distinguishable story (desk brief or multi-name theme),
not one feed item per symbol. The horizontal album opens with high-level
commentary, then walks evidence/tension/verdict while naming every affected
ticker.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

import plotly.graph_objects as go

from tradingagents.evidence import Evidence
from tradingagents.thesis import LivingThesisStore, diff_or_none

from . import charts
from .chart_selector import select_chart_spec
from .chart_validator import validate_chart_spec
from .feed_schema import Card, CardKind, Feed, Narrative
from .visualization_intent import AnalyticalQuestion, VisualizationIntent

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
    evidence: list[Evidence] | None = None,
    as_of: str | None = None,
) -> float:
    """Vertical-rank score: signal, portfolio impact, and evidence quality.

    - Conviction: distance of the rating from Hold (0..2).
    - Sentiment extremity: distance of the score from neutral 5 (0..~1).
    - Portfolio impact: held names are boosted, weighted by book weight.
    - Evidence: additive, bounded provider-quality and freshness bonuses.
    """
    conviction = abs(_RATING_VALUE.get((rating or "").lower(), 2) - 2)  # 0..2
    extremity = abs((sentiment_score if sentiment_score is not None else 5.0) - 5.0) / 5.0  # 0..1
    impact = (1.0 + 4.0 * (portfolio_weight or 0.0)) if held else 0.0
    source_quality, freshness = evidence_rank_factors(evidence or [], as_of)
    return round(conviction + extremity + impact + 0.25 * source_quality + 0.25 * freshness, 4)


def evidence_rank_factors(evidence: list[Evidence], as_of: str | None) -> tuple[float, float]:
    """Return mean provider quality and recency scores for transparent ranking."""
    if not evidence:
        return 0.0, 0.0
    reference = _as_of_datetime(as_of)
    quality = []
    freshness = []
    provider_defaults = {"fred": 0.95, "sec": 0.98, "yfinance": 0.70}
    for item in evidence:
        quality.append(
            item.source_quality_score
            if item.source_quality_score is not None
            else provider_defaults.get(item.provider_id.lower(), 0.50)
        )
        if item.published_at is None:
            freshness.append(0.0)
            continue
        published = item.published_at
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_days = max(0.0, (reference - published).total_seconds() / 86_400)
        freshness.append(max(0.0, 1.0 - age_days / 90.0))
    return round(sum(quality) / len(quality), 4), round(sum(freshness) / len(freshness), 4)


def _as_of_datetime(as_of: str | None) -> datetime:
    if as_of:
        return datetime.strptime(as_of, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc)


def build_narrative(
    final_state: dict[str, Any],
    *,
    portfolio: Any = None,
    ohlcv=None,
    thesis_store: LivingThesisStore | None = None,
) -> Narrative:
    """Assemble the single-name narrative arc from one run's ``final_state``."""
    symbol = (final_state.get("company_of_interest") or "?").upper()
    trade_date = final_state.get("trade_date", "")

    verdict_md = final_state.get("final_trade_decision", "") or ""
    trader_md = final_state.get("trader_investment_plan", "") or ""

    # Structured payloads are canonical when the run carries them; the regex
    # parsers remain only as a fallback for legacy saved runs without structs.
    pm_struct = final_state.get("portfolio_decision_struct") or {}
    trader_struct = final_state.get("trader_proposal_struct") or {}
    sentiment_struct = final_state.get("sentiment_report_struct") or {}

    rating = pm_struct.get("rating") or parse_rating(verdict_md) or parse_rating(trader_md)
    target = (
        pm_struct.get("price_target")
        or trader_struct.get("entry_price")
        or _parse_money(verdict_md, "Price Target")
        or _parse_money(trader_md, "Entry Price")
    )
    stop = trader_struct.get("stop_loss") or _parse_money(trader_md, "Stop Loss")
    if sentiment_struct.get("overall_score") is not None:
        sent_score = float(sentiment_struct["overall_score"])
        sent_band = sentiment_struct.get("overall_band")
    else:
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
    portfolio_impact = _portfolio_impact(held, weight)
    evidence = _coerce_evidence(final_state.get("evidence", []))
    news_evidence = [item for item in evidence if item.source_type == "news"]
    macro_evidence = [item for item in evidence if item.source_type == "macro"]
    filing_evidence = [item for item in evidence if item.source_type == "filing"]
    source_quality, freshness = evidence_rank_factors(evidence, trade_date or None)

    cards: list[Card] = []

    # --- HOOK: price chart with the thesis drawn on it + the verdict headline ---
    levels = []
    if target is not None:
        levels.append({"label": f"Target {target:g}", "value": target, "color": "#2ca02c"})
    if stop is not None:
        levels.append({"label": f"Stop {stop:g}", "value": stop, "color": "#d62728"})
    hook_headline = _verdict_hook(symbol, rating, verdict_md, held, weight)
    hook_chart = None
    hook_intent = None
    hook_spec = None
    if ohlcv is not None:
        hook_intent = VisualizationIntent(
            analytical_question=AnalyticalQuestion.TREND,
            entities=[symbol],
            metrics=["price"],
            time_window=trade_date or None,
            explanation="Show price trend and decision levels.",
        )
        hook_spec = select_chart_spec(hook_intent, units="price")
        validation = validate_chart_spec(hook_spec, hook_intent, ohlcv)
        hook_spec.validated = validation.valid
        if validation.valid:
            hook_chart = _fig_to_dict(
                charts.price_chart(ohlcv, title=f"{symbol} — {trade_date}", levels=levels)
            )
    cards.append(Card(
        id=f"{symbol}-hook", kind=CardKind.HOOK, title=symbol,
        headline=hook_headline, badges=badges, chart=hook_chart,
        card_type="portfolio_impact", portfolio_impact=portfolio_impact,
        visualization_intent=hook_intent, chart_spec=hook_spec,
    ))
    thesis_card = _thesis_change_card(
        thesis_store, symbol, trade_date, portfolio_impact
    )
    if thesis_card is not None:
        cards.append(thesis_card)

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
            card_type="explanation",
            evidence_ids=[item.id for item in filing_evidence],
            evidence=filing_evidence,
            portfolio_impact=portfolio_impact,
            source_quality_score=source_quality,
            freshness_score=freshness,
        ))

    # --- EVIDENCE: macro backdrop (official FRED observations) ---
    if macro_evidence:
        cards.append(Card(
            id=f"{symbol}-macro", kind=CardKind.EVIDENCE, title="Macro",
            headline=f"Macro backdrop: {len(macro_evidence)} FRED series",
            body="\n".join(item.summary for item in macro_evidence),
            card_type="explanation",
            evidence_ids=[item.id for item in macro_evidence],
            evidence=macro_evidence,
            portfolio_impact=portfolio_impact,
            source_quality_score=source_quality,
            freshness_score=freshness,
        ))

    # --- EVIDENCE: news ---
    if final_state.get("news_report"):
        cards.append(Card(
            id=f"{symbol}-news", kind=CardKind.EVIDENCE, title="News",
            headline=_first_sentence(final_state["news_report"]),
            body=final_state["news_report"], card_type="event",
            evidence_ids=[item.id for item in news_evidence],
            evidence=news_evidence, portfolio_impact=portfolio_impact,
            source_quality_score=source_quality,
            freshness_score=freshness,
        ))

    # --- TENSION: bull vs bear, framed as a risk/reward band when priced ---
    debate = final_state.get("investment_debate_state") or {}
    if debate.get("bull_history") or debate.get("bear_history"):
        chart = None
        if ohlcv is not None and (target is not None or stop is not None):
            entry = float(charts.close_series(ohlcv).iloc[-1])
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
            card_type="portfolio_impact", portfolio_impact=portfolio_impact,
        ))

    dominance = compute_dominance(
        rating=rating, sentiment_score=sent_score, portfolio_weight=weight, held=held,
        evidence=evidence, as_of=trade_date or None,
    )
    stance = "manage" if held else "initiate"
    return Narrative(
        id=f"{symbol}-{trade_date}",
        symbol=symbol,
        symbols=[symbol],
        title=f"{symbol} — {rating}" if rating else symbol,
        summary=_first_sentence(verdict_md) or f"Latest read on {symbol}",
        dominance=dominance,
        badges=badges,
        cards=cards,
        meta={
            "trade_date": trade_date,
            "stance": stance,
            "held": held,
            "story_kind": "single_name",
            "source_quality_score": source_quality,
            "freshness_score": freshness,
        },
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


def _portfolio_impact(held: bool, weight: float | None) -> str:
    """Explain what the card means for the current book, even when unheld."""
    if held and weight is not None:
        return f"Held position: {weight * 100:.1f}% of portfolio; review sizing and thesis."
    if held:
        return "Held position: review sizing and thesis."
    return "Watchlist candidate: no current portfolio exposure."


def _thesis_change_card(
    store: LivingThesisStore | None,
    symbol: str,
    trade_date: str,
    portfolio_impact: str,
) -> Card | None:
    if store is None or not trade_date:
        return None
    current = store.load_snapshot(symbol, trade_date)
    if current is None or not current.prior_snapshot_id:
        return None
    prior_date = current.prior_snapshot_id.rsplit("_", 1)[-1]
    diff = diff_or_none(store.load_snapshot(symbol, prior_date), current)
    if diff is None:
        return None
    return Card(
        id=f"{symbol}-thesis-{trade_date}",
        kind=CardKind.CONTEXT,
        title="Thesis change",
        headline=diff.headline,
        badges=["Thesis", f"{diff.rating_delta:+d} rating step"],
        card_type="thesis_change",
        evidence_ids=diff.evidence_added,
        portfolio_impact=portfolio_impact,
        materiality_score=diff.materiality_score,
        chart=_fig_to_dict(charts.rating_dial(current.rating.value)),
    )


def _coerce_evidence(items: list[Any]) -> list[Evidence]:
    """Accept persisted JSON or model instances while ignoring malformed records."""
    evidence = []
    for item in items:
        try:
            evidence.append(item if isinstance(item, Evidence) else Evidence.model_validate(item))
        except (TypeError, ValueError):
            continue
    by_id = {item.id: item for item in evidence}
    return [by_id[item_id] for item_id in sorted(by_id)]


def _strip_rating_line(text: str) -> str:
    """Drop the leading '**Rating**: X' line so the hook uses the summary prose."""
    return re.sub(r"\*\*Rating\*\*:.*?(\n|$)", "", text, count=1)


def build_feed(
    runs: list[dict[str, Any]],
    *,
    portfolio: Any = None,
    ohlcv_map: dict[str, Any] | None = None,
    as_of: str | None = None,
    thesis_store: LivingThesisStore | None = None,
) -> Feed:
    """Build a story feed: desk brief first, then multi-symbol theme arcs.

    Vertical posts are distinguishable stories (not one-per-ticker). Each story
    opens with high-level commentary, then horizontal cards walk the evidence
    and list every affected symbol.
    """
    ohlcv_map = ohlcv_map or {}
    units = [
        build_narrative(
            state,
            portfolio=portfolio,
            ohlcv=ohlcv_map.get((state.get("company_of_interest") or "").upper()),
            thesis_store=thesis_store,
        )
        for state in runs
    ]
    if not units:
        return Feed(as_of=as_of, narratives=[])

    stories = [_build_desk_brief(units, portfolio=portfolio, as_of=as_of)]

    trim = [
        u for u in units if u.meta.get("held") and _unit_rating(u) in {"Sell", "Underweight"}
    ]
    add = [u for u in units if _unit_rating(u) in {"Buy", "Overweight"}]
    watch = [u for u in units if u not in trim and u not in add]

    if trim:
        stories.append(
            _build_theme_story(
                units=trim,
                story_id="theme-trim",
                title="Protect the book",
                kind="trim",
                lead="Held names where the desk is cutting risk.",
                as_of=as_of,
            )
        )
    if add:
        stories.append(
            _build_theme_story(
                units=add,
                story_id="theme-add",
                title="Where conviction leans bullish",
                kind="opportunity",
                lead="Names the desk wants more of — held or new.",
                as_of=as_of,
            )
        )
    if watch and not (trim or add):
        # Only emit a quiet hold story when nothing else clustered.
        stories.append(
            _build_theme_story(
                units=watch,
                story_id="theme-hold",
                title="Steady book",
                kind="hold",
                lead="No aggressive re-rating — monitor and keep powder dry.",
                as_of=as_of,
            )
        )
    elif watch and len(watch) >= 2:
        stories.append(
            _build_theme_story(
                units=watch,
                story_id="theme-monitor",
                title="Watchlist / holds",
                kind="monitor",
                lead="Secondary names with less urgent action.",
                as_of=as_of,
            )
        )

    return Feed(as_of=as_of, narratives=stories).ranked()


def _unit_rating(unit: Narrative) -> str | None:
    for badge in unit.badges:
        if badge.lower() in _RATING_VALUE:
            return badge.capitalize() if badge.lower() != "underweight" else "Underweight"
    # badges may already be Title case
    for badge in unit.badges:
        if badge in {"Buy", "Overweight", "Hold", "Underweight", "Sell"}:
            return badge
    return None


def _impact_rows(units: list[Narrative]) -> list[dict]:
    rows = []
    for unit in units:
        weight = None
        for badge in unit.badges:
            if "of book" in badge:
                try:
                    weight = float(badge.split("%")[0]) / 100.0
                except ValueError:
                    weight = None
        rows.append(
            {
                "symbol": unit.symbol or (unit.symbols[0] if unit.symbols else "?"),
                "weight": weight if unit.meta.get("held") else 0.0,
                "rating": _unit_rating(unit),
            }
        )
    # Sort held/heavier first
    return sorted(rows, key=lambda r: (-(r["weight"] or 0.0), r["symbol"]))


def _build_desk_brief(
    units: list[Narrative],
    *,
    portfolio: Any,
    as_of: str | None,
) -> Narrative:
    rows = _impact_rows(units)
    symbols = [r["symbol"] for r in rows]
    held_n = sum(1 for u in units if u.meta.get("held"))
    trim_n = sum(1 for u in units if _unit_rating(u) in {"Sell", "Underweight"})
    buy_n = sum(1 for u in units if _unit_rating(u) in {"Buy", "Overweight"})
    book_pct = sum((r["weight"] or 0.0) for r in rows if (r["weight"] or 0) > 0)

    headline = (
        f"{len(units)} names researched · {held_n} held · "
        f"{trim_n} risk-off · {buy_n} bullish"
    )
    body_lines = [
        f"As of {as_of or 'today'}: desk brief across the latest runs.",
        f"Covered symbols: {', '.join(symbols)}.",
    ]
    if portfolio is not None and book_pct > 0:
        body_lines.append(
            f"Affected held exposure ≈ {book_pct * 100:.0f}% of the book."
        )
    for r in rows:
        tag = "held" if (r["weight"] or 0) > 0 else "watch"
        body_lines.append(
            f"- {r['symbol']}: {r['rating'] or 'n/a'} ({tag}"
            + (f", {r['weight']*100:.0f}% of book)" if r["weight"] else ")")
        )

    chart = _fig_to_dict(charts.book_impact_bars(rows, title="Book impact by name"))
    cards = [
        Card(
            id="desk-hook",
            kind=CardKind.HOOK,
            title="Desk brief",
            headline=headline,
            body="\n".join(body_lines),
            badges=["Desk", f"{len(symbols)} symbols"],
            symbols=symbols,
            chart=chart,
            card_type="portfolio_impact",
            portfolio_impact=(
                f"{held_n} held names in this brief"
                + (f"; ~{book_pct*100:.0f}% of book" if book_pct else "")
            ),
        ),
        Card(
            id="desk-affected",
            kind=CardKind.CONTEXT,
            title="Affected",
            headline="Who this brief touches",
            body="\n".join(
                (
                    f"{r['symbol']}: {r['rating'] or '—'} · "
                    + (
                        f"held {r['weight'] * 100:.0f}%"
                        if r["weight"]
                        else "not held"
                    )
                )
                for r in rows
            ),
            badges=symbols,
            symbols=symbols,
            chart=chart,
        ),
        Card(
            id="desk-verdict",
            kind=CardKind.VERDICT,
            title="Next",
            headline=(
                "Swipe the stories below for full arcs — "
                "trim themes first when risk-off names are held."
                if trim_n
                else "Swipe into theme stories for the full evidence arc."
            ),
            badges=[f"{trim_n} trim", f"{buy_n} add"],
            symbols=symbols,
            portfolio_impact="Start with the highest-dominance theme post.",
        ),
    ]
    return Narrative(
        id=f"desk-brief-{as_of or 'latest'}",
        title="Desk brief",
        summary=headline,
        symbols=symbols,
        dominance=100.0,  # always lead the feed
        badges=["Overview", f"{len(symbols)} names"],
        cards=cards,
        meta={"story_kind": "desk_brief", "trade_date": as_of, "held_count": held_n},
    )


def _build_theme_story(
    *,
    units: list[Narrative],
    story_id: str,
    title: str,
    kind: str,
    lead: str,
    as_of: str | None,
) -> Narrative:
    rows = _impact_rows(units)
    symbols = [r["symbol"] for r in rows]
    dominance = max((u.dominance for u in units), default=0.0) + 0.5 * len(units)

    hook = Card(
        id=f"{story_id}-hook",
        kind=CardKind.HOOK,
        title="Story",
        headline=f"{title}: {', '.join(symbols)}",
        body=lead + "\n\n" + "\n".join(
            f"- {u.symbol}: {u.summary or u.title}" for u in units
        ),
        badges=[kind.capitalize(), f"{len(symbols)} names"],
        symbols=symbols,
        chart=_fig_to_dict(charts.book_impact_bars(rows, title=title)),
        portfolio_impact=f"{len(symbols)} symbols in this story",
    )
    affected = Card(
        id=f"{story_id}-affected",
        kind=CardKind.CONTEXT,
        title="Affected",
        headline="Symbols in this arc",
        body="\n".join(
            f"{r['symbol']} — {r['rating'] or 'n/a'}"
            + (f" · {r['weight']*100:.0f}% of book" if r.get("weight") else "")
            for r in rows
        ),
        badges=symbols,
        symbols=symbols,
        chart=_fig_to_dict(charts.book_impact_bars(rows, title="Exposure")),
    )

    cards: list[Card] = [hook, affected]

    # Prefer news/macro evidence slides; fall back to market/fundamentals.
    for unit in units:
        sym = unit.symbol or "?"
        evidence_cards = [
            c
            for c in unit.cards
            if c.kind is CardKind.EVIDENCE and c.title in {"News", "Macro", "Market", "Fundamentals"}
        ]
        preferred = sorted(
            evidence_cards,
            key=lambda c: {"News": 0, "Macro": 1, "Market": 2, "Fundamentals": 3}.get(
                c.title, 9
            ),
        )
        if preferred:
            for card in preferred[:2]:
                cards.append(
                    card.model_copy(
                        update={
                            "id": f"{story_id}-{sym}-{card.id}",
                            "title": f"{sym} · {card.title}",
                            "symbols": [sym],
                            "badges": list(dict.fromkeys([sym, *card.badges])),
                        }
                    )
                )
        tension = next((c for c in unit.cards if c.kind is CardKind.TENSION), None)
        if tension:
            cards.append(
                tension.model_copy(
                    update={
                        "id": f"{story_id}-{sym}-tension",
                        "title": f"{sym} · Debate",
                        "symbols": [sym],
                        "badges": list(dict.fromkeys([sym, *tension.badges])),
                    }
                )
            )
        verdict = next((c for c in unit.cards if c.kind is CardKind.VERDICT), None)
        if verdict:
            cards.append(
                verdict.model_copy(
                    update={
                        "id": f"{story_id}-{sym}-verdict",
                        "title": f"{sym} · Verdict",
                        "symbols": [sym],
                        "badges": list(dict.fromkeys([sym, *verdict.badges])),
                    }
                )
            )

    # Cap album length so horizontal swipe stays scannable
    if len(cards) > 10:
        cards = cards[:2] + cards[2:10]

    return Narrative(
        id=f"{story_id}-{as_of or 'latest'}",
        title=title,
        summary=lead,
        symbols=symbols,
        dominance=dominance,
        badges=[kind.capitalize(), *symbols[:4]],
        cards=cards,
        meta={
            "story_kind": kind,
            "trade_date": as_of,
            "symbol_count": len(symbols),
        },
    )
