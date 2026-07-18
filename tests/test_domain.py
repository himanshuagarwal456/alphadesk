"""Canonical domain records: IDs, normalization, serialization, run persistence."""

from __future__ import annotations

import json

import pytest

from tradingagents.domain import (
    AnalysisRun,
    AnalysisRunStore,
    Claim,
    Instrument,
    OwnershipClass,
    RunStatus,
    SourceRecord,
)
from tradingagents.evidence import Evidence
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.ui.sample import sample_final_state


@pytest.mark.unit
def test_instrument_normalizes_and_derives_stable_id():
    a = Instrument(symbol=" aapl ", exchange="NASDAQ")
    b = Instrument(symbol="AAPL", exchange="NASDAQ")
    assert a.symbol == "AAPL"
    assert a.id == b.id
    assert a.id != Instrument(symbol="AAPL", exchange="NYSE").id


@pytest.mark.unit
def test_source_record_ownership_and_id():
    record = SourceRecord(
        provider_id="upload",
        source_type="document",
        title="Q2 channel checks",
        ownership=OwnershipClass.PRIVATE,
        workspace_id="ws_1",
    )
    assert record.ownership is OwnershipClass.PRIVATE
    assert record.id.startswith("sr_")
    # round-trips through JSON
    restored = SourceRecord.model_validate(json.loads(record.model_dump_json()))
    assert restored == record


@pytest.mark.unit
def test_claim_supported_flag_and_sorted_evidence():
    unsupported = Claim(text="Margins are at peak.")
    supported = Claim(text="Margins are at peak.", evidence_ids=["ev_b", "ev_a", "ev_a"])
    assert not unsupported.supported
    assert supported.supported
    assert supported.evidence_ids == ["ev_a", "ev_b"]
    assert unsupported.id != supported.id


@pytest.mark.unit
def test_evidence_ownership_defaults_public():
    record = Evidence(provider_id="yfinance", title="Article")
    assert record.ownership == "public"
    private = Evidence(provider_id="upload", title="My note", ownership="private")
    assert private.ownership == "private"


@pytest.mark.unit
def test_analysis_run_store_round_trip(tmp_path):
    run = AnalysisRun(
        symbol="nvda",
        trade_date="2026-01-15",
        status=RunStatus.COMPLETED,
        evidence_ids=["ev_2", "ev_1"],
        final_rating="Hold",
    )
    store = AnalysisRunStore(tmp_path)
    store.save(run)
    loaded = store.load("2026-01-15")
    assert loaded.symbol == "NVDA"
    assert loaded.evidence_ids == ["ev_1", "ev_2"]
    assert loaded.status is RunStatus.COMPLETED
    assert store.load("1999-01-01") is None


@pytest.mark.unit
def test_log_state_writes_analysis_run_record(tmp_path):
    graph = object.__new__(TradingAgentsGraph)
    graph.log_states_dict = {}
    graph.config = {"results_dir": str(tmp_path)}
    graph.ticker = "NVDA"
    state = sample_final_state("NVDA")
    state["investment_debate_state"]["history"] = ""
    state["investment_debate_state"]["current_response"] = ""
    state["risk_debate_state"]["history"] = ""
    graph._log_state("2026-01-15", state)

    log_dir = tmp_path / "NVDA" / "TradingAgentsStrategy_logs"
    run = AnalysisRunStore(log_dir).load("2026-01-15")
    assert run is not None
    assert run.symbol == "NVDA"
    assert run.final_rating == "Underweight"
    assert run.evidence_ids  # sample state carries evidence
