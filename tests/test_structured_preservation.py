"""Canonical structured outputs are preserved in state, saved runs, and the feed.

Alpha PR 3: no new consumer should have to parse markdown for data that the
agents produced as typed objects.
"""

from __future__ import annotations

import json
from unittest import mock

import pytest

from tradingagents.agents.schemas import (
    PortfolioDecision,
    ResearchPlan,
    SentimentReport,
    TraderProposal,
)
from tradingagents.agents.utils.structured import invoke_structured_with_payload
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.ui.deck_builder import build_narrative
from tradingagents.ui.runs import load_saved_runs
from tradingagents.ui.sample import sample_final_state, sample_ohlcv


class _StructuredLLM:
    def __init__(self, result):
        self._result = result

    def invoke(self, _prompt):
        return self._result


class _PlainLLM:
    def invoke(self, _prompt):
        return mock.Mock(content="free text fallback")


@pytest.mark.unit
def test_payload_returned_alongside_markdown():
    plan = ResearchPlan(
        recommendation="Hold", rationale="Balanced.", strategic_actions="Wait."
    )
    markdown, payload = invoke_structured_with_payload(
        _StructuredLLM(plan), _PlainLLM(), "prompt", lambda p: "rendered", "Test"
    )
    assert markdown == "rendered"
    assert payload["recommendation"] == "Hold"
    # payload is JSON-safe
    json.dumps(payload)


@pytest.mark.unit
def test_payload_none_on_freetext_fallback():
    markdown, payload = invoke_structured_with_payload(
        _StructuredLLM(None), _PlainLLM(), "prompt", lambda p: "rendered", "Test"
    )
    assert markdown == "free text fallback"
    assert payload is None


def _structured_state(symbol="NVDA"):
    state = sample_final_state(symbol)
    state["portfolio_decision_struct"] = PortfolioDecision(
        rating="Overweight",
        executive_summary="Add on weakness.",
        investment_thesis="Structured thesis.",
        price_target=250.0,
    ).model_dump(mode="json")
    state["trader_proposal_struct"] = TraderProposal(
        action="Buy", reasoning="Momentum.", entry_price=210.0, stop_loss=195.0
    ).model_dump(mode="json")
    state["sentiment_report_struct"] = SentimentReport(
        overall_band="Mildly Bullish",
        overall_score=6.0,
        confidence="high",
        narrative="Structured narrative.",
    ).model_dump(mode="json")
    return state


@pytest.mark.unit
def test_deck_builder_prefers_structured_over_regex():
    # The sample markdown says Underweight/bearish; the structs must win.
    narrative = build_narrative(_structured_state(), ohlcv=sample_ohlcv())
    assert "Overweight" in narrative.title
    sentiment_card = next(c for c in narrative.cards if c.title == "Sentiment")
    assert "6.0/10" in sentiment_card.headline
    assert "Mildly Bullish" in sentiment_card.headline


@pytest.mark.unit
def test_deck_builder_falls_back_to_regex_for_legacy_runs():
    narrative = build_narrative(sample_final_state("NVDA"), ohlcv=sample_ohlcv())
    assert "Underweight" in narrative.title  # parsed from markdown


@pytest.mark.unit
def test_saved_run_round_trips_structured_payloads(tmp_path):
    graph = object.__new__(TradingAgentsGraph)
    graph.log_states_dict = {}
    graph.config = {"results_dir": str(tmp_path)}
    graph.ticker = "NVDA"
    state = _structured_state()
    state["investment_debate_state"]["history"] = ""
    state["investment_debate_state"]["current_response"] = ""
    state["risk_debate_state"]["history"] = ""
    graph._log_state("2026-01-15", state)

    runs = load_saved_runs(tmp_path)
    assert runs[0]["portfolio_decision_struct"]["rating"] == "Overweight"
    assert runs[0]["trader_proposal_struct"]["stop_loss"] == 195.0
    assert runs[0]["sentiment_report_struct"]["overall_score"] == 6.0
