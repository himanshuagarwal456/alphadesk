"""Living thesis schemas, snapshots, and graph persistence hook."""

from __future__ import annotations

import pytest

from tradingagents.agents.schemas import PortfolioDecision, PortfolioRating
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.thesis import LivingThesisStore, ThesisStatus, build_thesis_update


def _decision(rating=PortfolioRating.BUY):
    return PortfolioDecision(
        rating=rating,
        executive_summary="Accumulate on weakness.",
        investment_thesis="Demand remains durable.",
        price_target=200,
        time_horizon="12 months",
    )


@pytest.mark.unit
def test_thesis_update_creates_linked_revision_chain():
    first, head = build_thesis_update(
        symbol="nvda", trade_date="2026-01-15", stance="initiate",
        decision=_decision(), evidence_ids=["ev_a"], prior=None,
    )
    second, updated = build_thesis_update(
        symbol="NVDA", trade_date="2026-02-15", stance="manage",
        decision=_decision(PortfolioRating.HOLD), evidence_ids=["ev_b"], prior=head,
    )
    assert first.symbol == "NVDA"
    assert second.prior_snapshot_id == first.snapshot_id
    assert updated.snapshot_ids == [first.snapshot_id, second.snapshot_id]
    assert updated.status is ThesisStatus.WEAKENED


@pytest.mark.unit
def test_thesis_store_round_trip_and_snapshot_dates(tmp_path):
    snapshot, head = build_thesis_update(
        symbol="NVDA", trade_date="2026-01-15", stance="",
        decision=_decision(), evidence_ids=[], prior=None,
    )
    store = LivingThesisStore(tmp_path)
    store.upsert_run(head, snapshot)
    assert store.load("nvda").current_snapshot_id == snapshot.snapshot_id
    assert store.load_snapshot("NVDA", "2026-01-15").rating is PortfolioRating.BUY
    assert store.snapshot_dates("NVDA") == ["2026-01-15"]


@pytest.mark.unit
def test_graph_thesis_hook_persists_structured_decision(tmp_path):
    graph = object.__new__(TradingAgentsGraph)
    graph.config = {"thesis_persist_enabled": True, "thesis_store_dir": str(tmp_path)}
    graph._persist_living_thesis("NVDA", "2026-01-15", {
        "position_stance": "manage",
        "portfolio_decision_struct": _decision().model_dump(mode="json"),
        "evidence": [{"id": "ev_news"}, {"id": "ev_macro"}],
    })
    thesis = LivingThesisStore(tmp_path).load("NVDA")
    assert thesis is not None
    assert thesis.current.evidence_ids == ["ev_macro", "ev_news"]
