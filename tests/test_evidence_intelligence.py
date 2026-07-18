"""Evidence provenance and chart-governance tests without network or LLM calls."""

from __future__ import annotations

import json

import pytest

from tradingagents.dataflows.yfinance_news import normalize_news_article
from tradingagents.evidence import Evidence, EvidenceStore
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.ui.chart_selector import select_chart_spec
from tradingagents.ui.chart_spec import ChartTemplate
from tradingagents.ui.chart_validator import validate_chart_spec
from tradingagents.ui.deck_builder import evidence_rank_factors
from tradingagents.ui.runs import load_saved_runs
from tradingagents.ui.sample import sample_final_state, sample_ohlcv
from tradingagents.ui.visualization_intent import AnalyticalQuestion, VisualizationIntent


@pytest.mark.unit
def test_evidence_id_is_stable_and_store_round_trips(tmp_path):
    evidence = Evidence(
        provider_id="yfinance",
        title="Earnings outlook",
        source_url="https://example.test/article",
        publisher="Example",
        published_at="2026-01-15T12:00:00Z",
        summary="A bounded summary.",
    )
    same_source = Evidence(
        provider_id="yfinance",
        title="Earnings outlook",
        source_url="https://example.test/article",
        publisher="Example",
        published_at="2026-01-15T12:00:00Z",
        summary="A revised bounded summary.",
    )
    assert evidence.id == same_source.id

    store = EvidenceStore(tmp_path)
    path = store.save_snapshot("2026-01-15", [same_source, evidence])
    assert path.name == "evidence_2026-01-15.json"
    loaded = store.load_snapshot("2026-01-15")
    assert len(loaded) == 1
    assert loaded[0].id == evidence.id


@pytest.mark.unit
def test_yfinance_article_normalizes_nested_metadata():
    article = {
        "content": {
            "title": "Company update",
            "summary": "A source summary.",
            "provider": {"displayName": "Yahoo Finance"},
            "canonicalUrl": {"url": "https://example.test/company-update"},
            "pubDate": "2026-01-15T12:00:00Z",
        }
    }
    evidence = normalize_news_article(article)
    assert evidence.provider_id == "yfinance"
    assert evidence.publisher == "Yahoo Finance"
    assert str(evidence.source_url) == "https://example.test/company-update"
    assert evidence.published_at is not None


@pytest.mark.unit
@pytest.mark.parametrize(
    ("question", "template"),
    [
        (AnalyticalQuestion.TREND, ChartTemplate.CANDLESTICK),
        (AnalyticalQuestion.RISK, ChartTemplate.GAUGE),
        (AnalyticalQuestion.SCENARIO, ChartTemplate.SCENARIO_BAND),
    ],
)
def test_chart_selector_is_deterministic(question, template):
    intent = VisualizationIntent(analytical_question=question)
    assert select_chart_spec(intent).template is template


@pytest.mark.unit
def test_chart_validator_rejects_unordered_dates_and_wrong_template():
    intent = VisualizationIntent(analytical_question=AnalyticalQuestion.TREND)
    spec = select_chart_spec(intent)
    unordered = sample_ohlcv(days=5).iloc[::-1]
    result = validate_chart_spec(spec, intent, unordered)
    assert not result.valid
    assert "chronological" in result.errors[0]

    wrong_spec = spec.model_copy(update={"template": ChartTemplate.GAUGE})
    assert not validate_chart_spec(wrong_spec, intent, sample_ohlcv()).valid


@pytest.mark.unit
def test_chart_validator_rejects_invalid_scenario():
    intent = VisualizationIntent(analytical_question=AnalyticalQuestion.SCENARIO)
    spec = select_chart_spec(intent).model_copy(update={"target": 90.0, "stop": 100.0})
    result = validate_chart_spec(spec, intent, sample_ohlcv())
    assert not result.valid
    assert "scenario target must exceed stop" in result.errors


@pytest.mark.unit
def test_evidence_rank_factors_reward_authoritative_fresh_sources():
    fresh_fred = Evidence(
        provider_id="fred",
        source_type="macro",
        title="CPI",
        source_url="https://fred.stlouisfed.org/series/CPIAUCSL",
        published_at="2026-01-14T00:00:00Z",
        source_quality_score=0.95,
    )
    quality, freshness = evidence_rank_factors([fresh_fred], "2026-01-15")
    assert quality == 0.95
    assert freshness > 0.98


@pytest.mark.unit
def test_run_log_persists_evidence_sidecar_and_loader_recovers_it(tmp_path):
    graph = object.__new__(TradingAgentsGraph)
    graph.log_states_dict = {}
    graph.config = {"results_dir": str(tmp_path)}
    graph.ticker = "NVDA"
    final_state = sample_final_state("NVDA")
    final_state["investment_debate_state"]["history"] = ""
    final_state["investment_debate_state"]["current_response"] = ""
    final_state["risk_debate_state"]["history"] = ""
    graph._log_state("2026-01-15", final_state)

    log_dir = tmp_path / "NVDA" / "TradingAgentsStrategy_logs"
    payload = json.loads((log_dir / "full_states_log_2026-01-15.json").read_text())
    assert payload["evidence_ids"]
    assert (log_dir / "evidence_2026-01-15.json").exists()

    runs = load_saved_runs(tmp_path)
    assert len(runs) == 1
    assert runs[0]["evidence"][0]["id"] == payload["evidence_ids"][0]
