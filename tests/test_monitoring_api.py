"""Phase 8 monitoring and material-change intelligence."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.monitoring.materiality import classify_materiality
from tradingagents.monitoring.schemas import DetectedEvent


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'mon.db'}"))


def _headers(workspace: str = "ws_mon") -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


@pytest.mark.server
def test_materiality_classifier_filing_vs_chatter() -> None:
    filing = DetectedEvent(
        workspace_id="ws",
        symbol="AMD",
        source="sec",
        event_type="filing",
        title="AMD files 8-K",
        summary="Item 2.02 results",
        payload={"form": "8-K"},
    )
    chatter = DetectedEvent(
        workspace_id="ws",
        symbol="AMD",
        source="news",
        event_type="news",
        title="Premarket movers and market wrap",
        summary="What to watch overnight",
    )
    assert classify_materiality(filing).material is True
    assert classify_materiality(chatter).material is False


@pytest.mark.server
def test_ingest_creates_card_notification_and_dedups(client: TestClient) -> None:
    event = {
        "workspace_id": "ws_mon",
        "symbol": "AMD",
        "source": "sec",
        "event_type": "filing",
        "title": "AMD files 8-K on gross margin",
        "summary": "Gross margin improved versus prior quarter.",
        "evidence_id": "ev_amd_8k_1",
        "payload": {"form": "8-K"},
    }
    first = client.post(
        "/v1/monitoring/events",
        headers=_headers(),
        json={"events": [event]},
    )
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["events_material"] == 1
    assert body["cards_created"] == 1
    assert body["duplicates_skipped"] == 0

    second = client.post(
        "/v1/monitoring/events",
        headers=_headers(),
        json={"events": [event]},
    )
    assert second.status_code == 200
    assert second.json()["duplicates_skipped"] == 1
    assert second.json()["cards_created"] == 0

    cards = client.get("/v1/cards", headers=_headers())
    assert cards.status_code == 200
    assert len(cards.json()) == 1
    card_id = cards.json()[0]["id"]
    assert cards.json()[0]["status"] == "new"
    assert cards.json()[0]["evidence_ids"]

    reviewed = client.post(
        f"/v1/cards/{card_id}/status",
        headers=_headers(),
        json={"status": "reviewed"},
    )
    assert reviewed.status_code == 200
    assert reviewed.json()["status"] == "reviewed"

    notes = client.get("/v1/monitoring/notifications", headers=_headers())
    assert notes.status_code == 200
    assert len(notes.json()) == 1
    note_id = notes.json()[0]["id"]
    marked = client.post(
        f"/v1/monitoring/notifications/{note_id}",
        headers=_headers(),
        json={"status": "read"},
    )
    assert marked.status_code == 200
    assert marked.json()["status"] == "read"

    health = client.get("/v1/monitoring/health", headers=_headers())
    assert health.status_code == 200
    assert health.json()["monitoring_enabled"] is True


@pytest.mark.server
def test_monitoring_pause_skips_ingest(client: TestClient) -> None:
    paused = client.put(
        "/v1/monitoring/controls",
        headers=_headers("ws_pause"),
        json={"monitoring_enabled": False},
    )
    assert paused.status_code == 200
    assert paused.json()["monitoring_enabled"] is False

    result = client.post(
        "/v1/monitoring/events",
        headers=_headers("ws_pause"),
        json={
            "events": [
                {
                    "workspace_id": "ws_pause",
                    "symbol": "AMD",
                    "source": "sec",
                    "event_type": "filing",
                    "title": "AMD 8-K",
                    "payload": {"form": "8-K"},
                }
            ]
        },
    )
    assert result.status_code == 200
    assert result.json()["status"] == "skipped"
    assert client.get("/v1/cards", headers=_headers("ws_pause")).json() == []


@pytest.mark.server
def test_immaterial_news_does_not_create_card(client: TestClient) -> None:
    result = client.post(
        "/v1/monitoring/events",
        headers=_headers("ws_imm"),
        json={
            "events": [
                {
                    "workspace_id": "ws_imm",
                    "symbol": "AMD",
                    "source": "news",
                    "event_type": "news",
                    "title": "Market wrap: stocks to watch",
                    "summary": "Premarket movers chatter",
                }
            ]
        },
    )
    assert result.status_code == 200
    assert result.json()["cards_created"] == 0
    assert result.json()["events_material"] == 0
