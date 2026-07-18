"""Phase 5 portfolio API: import, current book, watchlists, coverage."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app

FIXTURES = Path(__file__).parent / "fixtures" / "portfolios"


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(database_url=f"sqlite:///{tmp_path / 'p5.db'}")
    return TestClient(app)


def _headers(workspace: str = "ws_p5") -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


@pytest.mark.server
def test_import_preview_confirm_and_summary(client: TestClient):
    content = (FIXTURES / "unusual_headers.csv").read_text(encoding="utf-8")
    preview = client.post(
        "/v1/portfolios/import/preview",
        headers=_headers(),
        json={
            "content": content,
            "as_of": "2026-07-18",
            "column_map": {
                "symbol": "Equity Name",
                "quantity": "Units Owned",
                "avg_cost": "Paid Per Unit",
                "current_price": "Latest Quote",
            },
        },
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["can_confirm"] is True
    assert body["research_only"] is True

    confirm = client.post(
        "/v1/portfolios/import/confirm",
        headers=_headers(),
        json={"portfolio": body["portfolio"], "snapshot_id": "current"},
    )
    assert confirm.status_code == 201
    assert confirm.json()["id"] == "current"
    assert confirm.json()["research_only"] is True

    current = client.get("/v1/portfolios/current", headers=_headers())
    assert current.status_code == 200
    assert {p["symbol"] for p in current.json()["portfolio"]["positions"]} == {
        "BRKB",
        "LLY",
    }

    summary = client.get("/v1/portfolios/current/summary", headers=_headers())
    assert summary.status_code == 200
    assert summary.json()["open_positions"] == 2
    assert summary.json()["research_only"] is True


@pytest.mark.server
def test_manual_position_edit_and_watchlist_coverage(client: TestClient):
    client.post(
        "/v1/portfolios/import/confirm",
        headers=_headers(),
        json={
            "portfolio": {
                "as_of": "2026-07-18",
                "cash": 1000,
                "positions": [
                    {"symbol": "NVDA", "quantity": 10, "current_price": 100},
                    {"symbol": "AAPL", "quantity": 5, "current_price": 200},
                ],
            }
        },
    )
    edited = client.post(
        "/v1/portfolios/current/positions",
        headers=_headers(),
        json={"position": {"symbol": "MSFT", "quantity": 3, "current_price": 300}},
    )
    assert edited.status_code == 200
    assert any(p["symbol"] == "MSFT" for p in edited.json()["portfolio"]["positions"])

    removed = client.delete(
        "/v1/portfolios/current/positions/AAPL",
        headers=_headers(),
    )
    assert removed.status_code == 200
    assert not any(
        p["symbol"] == "AAPL" for p in removed.json()["portfolio"]["positions"]
    )

    wl = client.post(
        "/v1/watchlists",
        headers=_headers(),
        json={
            "name": "Core",
            "items": [
                {"symbol": "NVDA", "monitoring_enabled": True},
                {"symbol": "MSFT", "monitoring_enabled": False},
            ],
        },
    )
    assert wl.status_code == 201
    assert wl.json()["items"][0]["symbol"] in {"MSFT", "NVDA"}

    client.put(
        "/v1/theses/NVDA",
        headers=_headers(),
        json={
            "thesis": {
                "symbol": "NVDA",
                "status": "active",
                "current_snapshot_id": "th_NVDA_2026-07-18",
                "opened_at": "2026-07-18",
                "updated_at": "2026-07-18",
                "snapshot_ids": ["th_NVDA_2026-07-18"],
                "confidence_history": [],
                "current": {
                    "snapshot_id": "th_NVDA_2026-07-18",
                    "symbol": "NVDA",
                    "as_of": "2026-07-18",
                    "rating": "Buy",
                    "executive_summary": "Buy",
                    "investment_thesis": "AI",
                },
            }
        },
    )
    coverage = client.get(
        "/v1/portfolios/current/thesis-coverage",
        headers=_headers(),
    )
    assert coverage.status_code == 200
    payload = coverage.json()
    assert payload["with_thesis"] == 1
    assert payload["without_thesis"] >= 1

    detail = client.get(
        "/v1/portfolios/current/positions/NVDA",
        headers=_headers(),
    )
    assert detail.status_code == 200
    assert detail.json()["price_status"] == "priced"
    assert detail.json()["has_thesis"] is True
    assert detail.json()["research_only"] is True

    paused = client.put(
        "/v1/portfolios/controls",
        headers=_headers(),
        json={"monitoring_enabled": False},
    )
    assert paused.status_code == 200
    assert paused.json()["monitoring_enabled"] is False
    assert paused.json()["research_only"] is True


@pytest.mark.server
def test_workspace_isolation_for_current_book(client: TestClient):
    client.post(
        "/v1/portfolios/import/confirm",
        headers=_headers("ws_owner"),
        json={
            "portfolio": {
                "positions": [{"symbol": "AAPL", "quantity": 1, "current_price": 10}]
            }
        },
    )
    assert (
        client.get("/v1/portfolios/current", headers=_headers("ws_owner")).status_code
        == 200
    )
    assert (
        client.get("/v1/portfolios/current", headers=_headers("ws_other")).status_code
        == 404
    )
