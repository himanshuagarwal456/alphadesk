"""Phase 11 ops, readiness, usage, retry, and dead-letter."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.api.run_worker import (
    execute_research_job,
    queue_research_run,
    retry_research_run,
)
from tradingagents.domain.schemas import RunStatus
from tradingagents.observability.pricing import estimate_llm_cost_usd
from tradingagents.persistence.repositories import AnalysisRunRepository
from tradingagents.persistence.repositories.ops import OpsRepository


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'ops.db'}"))


def _headers(workspace: str = "ws_ops") -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


class _FakeGraph:
    def __init__(self, selected_analysts, config=None, debug=False, callbacks=None):
        self.callbacks = callbacks or []

    def propagate(self, symbol, trade_date, asset_type="stock", portfolio=None, market_view=""):
        for cb in self.callbacks:
            if hasattr(cb, "on_llm_start"):
                cb.on_llm_start({}, ["prompt"])
            if hasattr(cb, "tokens_in"):
                cb.tokens_in += 1000
                cb.tokens_out += 250
        return {
            "portfolio_decision_struct": {
                "rating": "Hold",
                "executive_summary": "ok",
                "investment_thesis": f"{symbol} thesis",
                "invalidation_conditions": [],
            },
            "final_trade_decision": "Rating: Hold",
            "investment_debate_state": {"bull_history": "b", "bear_history": "r"},
            "evidence": [],
        }, "Hold"


class _FailGraph:
    def __init__(self, *args, **kwargs):
        pass

    def propagate(self, *args, **kwargs):
        raise RuntimeError("provider timeout")


def test_estimate_llm_cost_known_and_unknown() -> None:
    cost = estimate_llm_cost_usd(
        tokens_in=1_000_000,
        tokens_out=1_000_000,
        deep_think_llm="gpt-4o-mini",
        quick_think_llm="gpt-4o-mini",
    )
    assert cost is not None and cost > 0
    assert (
        estimate_llm_cost_usd(
            tokens_in=100,
            tokens_out=100,
            deep_think_llm="totally-unknown-model-xyz",
        )
        is None
    )


@pytest.mark.server
def test_health_ready_and_trace_header(client: TestClient) -> None:
    live = client.get("/health")
    assert live.status_code == 200
    assert live.json()["status"] == "ok"

    ready = client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"

    traced = client.get("/health", headers={"X-Trace-Id": "tr_testtrace123"})
    assert traced.headers.get("X-Trace-Id") == "tr_testtrace123"


@pytest.mark.server
def test_run_persists_usage_and_ops_summary(client: TestClient) -> None:
    state = client.app.state.alphadesk
    run = queue_research_run(
        state.session_factory,
        workspace_id="ws_ops",
        symbol="AMD",
        trade_date="2026-07-21",
        start_worker=False,
        graph_factory=_FakeGraph,
    )
    completed = execute_research_job(
        state.session_factory,
        workspace_id="ws_ops",
        run_id=run.id,
        graph_factory=_FakeGraph,
    )
    assert completed.status is RunStatus.COMPLETED
    assert completed.llm_calls >= 1
    assert completed.tokens_in >= 1000
    assert completed.duration_ms is not None
    assert completed.trace_id

    usage = client.get("/v1/ops/usage", headers=_headers())
    assert usage.status_code == 200
    summary = usage.json()
    assert summary["runs"] >= 1
    assert summary["tokens_in"] >= 1000
    assert summary["llm_calls"] >= 1

    records = client.get("/v1/ops/usage/records", headers=_headers())
    assert records.status_code == 200
    assert records.json()

    export = client.get("/v1/ops/export", headers=_headers())
    assert export.status_code == 200
    assert export.json()["runs"] >= 1
    assert export.json()["backup_hints"]


@pytest.mark.server
def test_retry_and_dead_letter(client: TestClient) -> None:
    state = client.app.state.alphadesk
    run = queue_research_run(
        state.session_factory,
        workspace_id="ws_dlq",
        symbol="AMD",
        trade_date="2026-07-21",
        start_worker=False,
        max_attempts=2,
    )
    failed = execute_research_job(
        state.session_factory,
        workspace_id="ws_dlq",
        run_id=run.id,
        graph_factory=_FailGraph,
    )
    assert failed.status is RunStatus.FAILED

    retried = retry_research_run(
        state.session_factory,
        workspace_id="ws_dlq",
        run_id=run.id,
        start_worker=False,
    )
    assert retried.status is RunStatus.QUEUED
    assert retried.attempt == 2

    failed_again = execute_research_job(
        state.session_factory,
        workspace_id="ws_dlq",
        run_id=run.id,
        graph_factory=_FailGraph,
    )
    assert failed_again.status is RunStatus.FAILED
    assert failed_again.attempt == 2

    with pytest.raises(ValueError, match="max attempts"):
        retry_research_run(
            state.session_factory,
            workspace_id="ws_dlq",
            run_id=run.id,
            start_worker=False,
        )

    with state.session_factory.session_scope() as session:
        dead = OpsRepository(session).list_dead_letters("ws_dlq")
        assert dead
        audit = OpsRepository(session).list_audit("ws_dlq")
        assert any(a.action in {"run.dead_lettered", "run.retry", "run.queued"} for a in audit)
        stored = AnalysisRunRepository(session).get("ws_dlq", run.id)
        assert stored is not None and stored.status is RunStatus.FAILED

    api_retry = client.post(f"/v1/runs/{run.id}/retry", headers=_headers("ws_dlq"))
    assert api_retry.status_code == 409
