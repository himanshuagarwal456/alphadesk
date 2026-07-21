"""Tests for web-triggered research runs (mocked graph)."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.api.run_worker import (
    analysis_run_from_final_state,
    execute_research_job,
    queue_research_run,
)
from tradingagents.domain.schemas import AnalysisRun, RunStatus
from tradingagents.evidence.schemas import Evidence


class _FakeGraph:
    def __init__(self, selected_analysts, config=None, debug=False, callbacks=None):
        self.selected_analysts = selected_analysts
        self.config = config or {}
        self.debug = debug
        self.callbacks = callbacks or []

    def propagate(self, symbol, trade_date, asset_type="stock", portfolio=None, market_view=""):
        evidence = Evidence(
            provider_id="test",
            source_type="news",
            title=f"{symbol} held context",
            summary="Synthetic evidence for worker test.",
            ownership="public",
        )
        final_state = {
            "portfolio_decision_struct": {
                "rating": "Hold",
                "executive_summary": "Maintain exposure.",
                "investment_thesis": f"{symbol} remains core.",
                "invalidation_conditions": ["Thesis breaks on guidance cut"],
            },
            "final_trade_decision": "Rating: Hold",
            "investment_debate_state": {
                "bull_history": "Bull: durable demand.",
                "bear_history": "Bear: valuation risk.",
            },
            "evidence": [evidence],
            "had_portfolio": portfolio is not None,
            "market_view": market_view,
            "trade_date": trade_date,
            "asset_type": asset_type,
        }
        return final_state, "Hold"


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHADESK_OBJECT_STORE_DIR", str(tmp_path / "objects"))
    return TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'runs.db'}"))


def _headers(workspace: str = "ws_run") -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


def test_analysis_run_from_final_state_maps_fields() -> None:
    run = AnalysisRun(
        id="ar_test",
        symbol="NVDA",
        trade_date="2026-07-19",
        status=RunStatus.RUNNING,
    )
    completed = analysis_run_from_final_state(
        run,
        {
            "portfolio_decision_struct": {
                "rating": "Buy",
                "executive_summary": "Add",
                "investment_thesis": "AI",
                "invalidation_conditions": ["Margins roll over"],
            },
            "final_trade_decision": "Rating: Buy",
            "investment_debate_state": {
                "bull_history": "bull text",
                "bear_history": "bear text",
            },
            "evidence": [
                {
                    "id": "ev_abc",
                    "provider_id": "test",
                    "source_type": "news",
                    "title": "t",
                    "summary": "s",
                }
            ],
        },
        config={"llm_provider": "openai", "deep_think_llm": "gpt-test"},
    )
    assert completed.status is RunStatus.COMPLETED
    assert completed.final_rating == "Buy"
    assert completed.bull_case == "bull text"
    assert completed.bear_case == "bear text"
    assert "Margins roll over" in completed.risks
    assert "ev_abc" in completed.evidence_ids
    assert completed.model_provider == "openai"


@pytest.mark.server
def test_start_run_executes_with_fake_graph(client: TestClient, monkeypatch) -> None:
    from tradingagents.api import run_worker

    monkeypatch.setattr(run_worker, "TradingAgentsGraph", _FakeGraph, raising=False)

    # Inject factory via queue path used by the endpoint.
    def _queue(session_factory, **kwargs):
        kwargs["graph_factory"] = _FakeGraph
        kwargs["start_worker"] = False
        run = queue_research_run(session_factory, **kwargs)
        return execute_research_job(
            session_factory,
            workspace_id=kwargs["workspace_id"],
            run_id=run.id,
            graph_factory=_FakeGraph,
        )

    monkeypatch.setattr(
        "tradingagents.api.v1.runs.queue_research_run",
        _queue,
    )

    started = client.post(
        "/v1/runs/start",
        headers=_headers(),
        json={"symbol": "nvda", "trade_date": "2026-07-19"},
    )
    assert started.status_code == 202, started.text
    body = started.json()
    assert body["status"] == "completed"
    assert body["symbol"] == "NVDA"
    assert body["final_rating"] == "Hold"
    assert body["portfolio_decision_struct"]["investment_thesis"]
    assert body["bull_case"]
    assert body["evidence_ids"]

    events = client.get(f"/v1/runs/{body['id']}/events", headers=_headers())
    assert events.status_code == 200
    types = {e["event_type"] for e in events.json()}
    assert "run.created" in types
    assert "run.completed" in types

    # Thesis can be created from the completed durable run.
    thesis = client.post(
        "/v1/theses/from-run",
        headers=_headers(),
        json={"run_id": body["id"], "stance": "manage", "accept": True},
    )
    assert thesis.status_code == 201, thesis.text
    assert thesis.json()["status"] == "accepted"
    listed = client.get("/v1/theses", headers=_headers())
    assert any(t["symbol"] == "NVDA" for t in listed.json())
