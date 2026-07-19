"""Tests for the portfolio-aware feed ("FinTok") layer.

Indicators, chart builders, run-knowledge -> narrative arc, dominance ranking,
the saved-run loader, and HTML rendering — all deterministic, no network/LLM.
"""

import json

import plotly.graph_objects as go

from tradingagents.ui import charts, deck_builder, indicators
from tradingagents.ui.feed_schema import CardKind, Feed
from tradingagents.ui.render import render_feed_html
from tradingagents.ui.runs import load_saved_runs
from tradingagents.ui.sample import sample_feed, sample_final_state, sample_ohlcv

# --- indicators -----------------------------------------------------------

def test_indicators_shapes_and_bounds():
    df = sample_ohlcv(days=60)
    close = df["Close"]
    assert len(indicators.sma(close, 20)) == len(close)
    assert len(indicators.ema(close, 20)) == len(close)
    rsi = indicators.rsi(close).dropna()
    assert ((rsi >= 0) & (rsi <= 100)).all()
    macd = indicators.macd(close)
    assert set(macd.columns) == {"macd", "signal", "hist"}
    bb = indicators.bollinger(close)
    tail = bb.dropna().iloc[-1]
    assert tail["lower"] <= tail["mid"] <= tail["upper"]


# --- charts ---------------------------------------------------------------

def test_price_chart_has_candles_and_levels():
    fig = charts.price_chart(sample_ohlcv(), levels=[{"label": "T", "value": 150, "color": "#0f0"}])
    assert isinstance(fig, go.Figure)
    kinds = {type(t).__name__ for t in fig.data}
    assert "Candlestick" in kinds


def test_gauge_and_dial_are_indicators():
    assert isinstance(charts.sentiment_gauge(3.2, "Bearish"), go.Figure)
    dial = charts.rating_dial("Underweight")
    assert dial.data[0].value == 1  # Underweight -> 1 on the 0..4 scale


def test_scenario_bands_has_close_line():
    fig = charts.scenario_bands(sample_ohlcv(), entry=140, target=160, stop=130)
    assert any(getattr(t, "mode", None) == "lines" for t in fig.data)


def test_book_impact_bars():
    fig = charts.book_impact_bars(
        [
            {"symbol": "NVDA", "weight": 0.22, "rating": "Underweight"},
            {"symbol": "AAPL", "weight": 0.0, "rating": "Buy"},
        ]
    )
    assert isinstance(fig, go.Figure)
    assert fig.data[0].orientation == "h"


# --- parsers --------------------------------------------------------------

def test_parse_rating_variants():
    assert deck_builder.parse_rating("**Rating**: Underweight\n...") == "Underweight"
    assert deck_builder.parse_rating("FINAL TRANSACTION PROPOSAL: **SELL**") == "Sell"
    assert deck_builder.parse_rating("no rating here") is None


def test_parse_sentiment_and_money():
    score, band = deck_builder.parse_sentiment("**Overall Sentiment:** **Bearish** (Score: 3.2/10)")
    assert score == 3.2 and band == "Bearish"
    assert deck_builder._parse_money("**Price Target**: $1,234.50", "Price Target") == 1234.50


# --- narrative building + ranking ----------------------------------------

class _Book:
    def holds(self, s):
        return s.upper() == "NVDA"

    def weights(self):
        return {"NVDA": 0.22}


def test_build_narrative_arc_and_framing():
    nrv = deck_builder.build_narrative(
        sample_final_state("NVDA"), portfolio=_Book(), ohlcv=sample_ohlcv()
    )
    kinds = [c.kind for c in nrv.cards]
    assert kinds[0] is CardKind.HOOK
    assert CardKind.VERDICT in kinds
    assert CardKind.TENSION in kinds
    # portfolio framing present
    assert any("of book" in b for b in nrv.badges)
    assert nrv.meta["held"] is True and nrv.meta["stance"] == "manage"
    # hook card carries a chart (price with thesis levels)
    assert nrv.cards[0].chart is not None
    assert nrv.cards[0].chart_spec is not None
    assert nrv.cards[0].chart_spec.validated is True
    news_card = next(card for card in nrv.cards if card.title == "News")
    assert news_card.evidence_ids
    assert all(item.provider_id == "yfinance" for item in news_card.evidence)
    macro_card = next(card for card in nrv.cards if card.title == "Macro")
    assert macro_card.evidence_ids
    assert all(item.provider_id == "fred" for item in macro_card.evidence)
    assert "22.0% of portfolio" in news_card.portfolio_impact


def test_compute_dominance_boosts_held_names():
    held = deck_builder.compute_dominance(rating="Buy", sentiment_score=8.0, portfolio_weight=0.3, held=True)
    not_held = deck_builder.compute_dominance(rating="Buy", sentiment_score=8.0, portfolio_weight=None, held=False)
    assert held > not_held


def test_sample_feed_desk_brief_then_themes():
    feed = sample_feed()
    assert isinstance(feed, Feed)
    assert len(feed.narratives) >= 2
    lead = feed.narratives[0]
    assert lead.meta.get("story_kind") == "desk_brief"
    assert "NVDA" in lead.symbols and "AAPL" in lead.symbols
    assert lead.cards[0].kind is CardKind.HOOK
    # Theme stories still surface both names across the feed
    all_syms = {s for n in feed.narratives for s in n.symbols}
    assert {"NVDA", "AAPL"} <= all_syms


# --- rendering ------------------------------------------------------------

def test_render_feed_html_embeds_deck():
    html = render_feed_html(sample_feed())
    assert "<!doctype html>" in html.lower()
    assert "plotly" in html.lower()
    assert "NVDA" in html
    assert "Desk brief" in html
    assert "Affected" in html or "affected" in html.lower()
    # the embedded FEED json parses
    start = html.index("const FEED = ") + len("const FEED = ")
    end = html.index(";\n", start)
    data = json.loads(html[start:end])
    assert len(data["narratives"]) >= 2
    assert data["narratives"][0]["symbols"]
    assert "Sources (" in html
    assert "finance.yahoo.com" in html
    assert "fred.stlouisfed.org" in html


# --- saved-run loader -----------------------------------------------------

def test_load_saved_runs_normalises_trader_key(tmp_path):
    log_dir = tmp_path / "NVDA" / "TradingAgentsStrategy_logs"
    log_dir.mkdir(parents=True)
    payload = {
        "company_of_interest": "NVDA",
        "trade_date": "2026-01-15",
        "final_trade_decision": "**Rating**: Hold",
        "trader_investment_decision": "FINAL TRANSACTION PROPOSAL: **HOLD**",
    }
    (log_dir / "full_states_log_2026-01-15.json").write_text(json.dumps(payload), encoding="utf-8")

    runs = load_saved_runs(tmp_path)
    assert len(runs) == 1
    assert runs[0]["company_of_interest"] == "NVDA"
    assert runs[0]["trader_investment_plan"].startswith("FINAL TRANSACTION")


def test_load_saved_runs_empty_dir(tmp_path):
    assert load_saved_runs(tmp_path / "nope") == []
