"""Phase 3 FastAPI /v1 integration tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.domain.schemas import RunStatus


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(database_url=f"sqlite:///{tmp_path / 'api.db'}")
    return TestClient(app)


def _headers(workspace: str) -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


@pytest.mark.server
def test_health(client: TestClient):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.server
def test_run_lifecycle_and_event_stream(client: TestClient):
    created = client.post(
        "/v1/runs",
        json={"symbol": "msft", "trade_date": "2026-04-01"},
        headers=_headers("ws_api"),
    )
    assert created.status_code == 201
    run = created.json()
    assert run["symbol"] == "MSFT"
    assert run["status"] == RunStatus.QUEUED.value
    run_id = run["id"]

    status = client.post(
        f"/v1/runs/{run_id}/status",
        json={"status": RunStatus.RUNNING.value, "message": "started"},
        headers=_headers("ws_api"),
    )
    assert status.status_code == 200
    assert status.json()["status"] == RunStatus.RUNNING.value

    event = client.post(
        f"/v1/runs/{run_id}/events",
        json={"event_type": "analyst.news", "message": "fetching"},
        headers=_headers("ws_api"),
    )
    assert event.status_code == 201

    done = client.post(
        f"/v1/runs/{run_id}/status",
        json={"status": RunStatus.COMPLETED.value},
        headers=_headers("ws_api"),
    )
    assert done.json()["status"] == RunStatus.COMPLETED.value

    events = client.get(
        f"/v1/runs/{run_id}/events",
        headers=_headers("ws_api"),
    ).json()
    types = [item["event_type"] for item in events]
    assert "run.created" in types
    assert "run.status" in types
    assert "analyst.news" in types


@pytest.mark.server
def test_cross_workspace_isolation(client: TestClient):
    created = client.post(
        "/v1/runs",
        json={"symbol": "AAPL", "trade_date": "2026-04-02"},
        headers=_headers("ws_owner"),
    )
    run_id = created.json()["id"]

    assert (
        client.get(f"/v1/runs/{run_id}", headers=_headers("ws_owner")).status_code
        == 200
    )
    assert (
        client.get(f"/v1/runs/{run_id}", headers=_headers("ws_intruder")).status_code
        == 404
    )
    assert client.get("/v1/runs", headers=_headers("ws_intruder")).json() == []


@pytest.mark.server
def test_evidence_and_portfolio_round_trip(client: TestClient):
    evidence = client.post(
        "/v1/evidence",
        json=[
            {
                "provider_id": "sec",
                "title": "Form 10-Q",
                "source_type": "filing",
                "summary": "Revenue up",
            }
        ],
        headers=_headers("ws_api"),
    )
    assert evidence.status_code == 201
    assert evidence.json()[0]["id"].startswith("ev_")

    portfolio = client.post(
        "/v1/portfolios",
        json={
            "portfolio": {
                "as_of": "2026-04-02",
                "positions": [{"symbol": "aapl", "quantity": 5, "current_price": 200}],
            }
        },
        headers=_headers("ws_api"),
    )
    assert portfolio.status_code == 201
    snapshot_id = portfolio.json()["id"]
    fetched = client.get(
        f"/v1/portfolios/{snapshot_id}",
        headers=_headers("ws_api"),
    )
    assert fetched.status_code == 200
    assert fetched.json()["portfolio"]["positions"][0]["symbol"] == "AAPL"
