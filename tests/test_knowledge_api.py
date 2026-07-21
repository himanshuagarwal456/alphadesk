"""Learn More / knowledge catalog API."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app
from tradingagents.knowledge.seed import load_catalog


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    app = create_app(database_url=f"sqlite:///{tmp_path / 'knowledge.db'}")
    return TestClient(app)


def _headers(workspace: str = "ws_learn") -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


@pytest.mark.server
def test_catalog_seed_loads_expected_concepts() -> None:
    concepts, resources, links = load_catalog()
    assert len(concepts) >= 20
    assert any(c.slug == "gross-margin" for c in concepts)
    assert resources
    assert links


@pytest.mark.server
def test_list_concepts_seeds_and_returns_catalog(client: TestClient) -> None:
    first = client.get("/v1/knowledge/concepts", headers=_headers())
    assert first.status_code == 200, first.text
    concepts = first.json()
    assert len(concepts) >= 20
    assert all(c.get("id") and c.get("slug") for c in concepts)

    second = client.get("/v1/knowledge/concepts", headers=_headers())
    assert second.status_code == 200
    assert len(second.json()) == len(concepts)


@pytest.mark.server
def test_context_progress_and_demo_card(client: TestClient) -> None:
    concepts = client.get("/v1/knowledge/concepts", headers=_headers()).json()
    concept = next(c for c in concepts if c["slug"] == "gross-margin")

    ctx = client.get(
        "/v1/knowledge/context",
        headers=_headers(),
        params={"concept_id": concept["id"]},
    )
    assert ctx.status_code == 200, ctx.text
    payload = ctx.json()
    assert payload["concept"]["slug"] == "gross-margin"
    assert payload["personalized_explanation"]
    assert payload["why_it_matters"]
    assert payload["portfolio_example"]
    assert payload["user_progress"]["status"] == "viewed"
    assert payload["user_progress"]["view_count"] >= 1

    progress = client.post(
        f"/v1/knowledge/concepts/{concept['id']}/progress",
        headers=_headers(),
        json={"saved": True, "status": "completed"},
    )
    assert progress.status_code == 200, progress.text
    assert progress.json()["saved"] is True
    assert progress.json()["status"] == "completed"

    demo = client.post("/v1/knowledge/demo-card", headers=_headers(), json={})
    assert demo.status_code == 201, demo.text
    card = demo.json()
    assert card["symbol"] == "AMD"
    assert "margin" in (card["headline"] or "").lower() or "margin" in (
        card["title"] or ""
    ).lower()

    linked = client.get(
        f"/v1/knowledge/cards/{card['id']}/concepts",
        headers=_headers(),
    )
    assert linked.status_code == 200, linked.text
    linked_concepts = linked.json()
    assert linked_concepts
    assert any("margin" in c["slug"] or "margin" in c["title"].lower() for c in linked_concepts)

    with_card = client.get(
        "/v1/knowledge/context",
        headers=_headers(),
        params={
            "concept_id": linked_concepts[0]["id"],
            "intelligence_card_id": card["id"],
        },
    )
    assert with_card.status_code == 200, with_card.text
    assert "AMD" in with_card.json()["why_it_matters"]


@pytest.mark.server
def test_concept_lookup_by_slug_and_missing(client: TestClient) -> None:
    found = client.get("/v1/knowledge/concepts/gross-margin", headers=_headers())
    assert found.status_code == 200
    assert found.json()["slug"] == "gross-margin"

    missing = client.get("/v1/knowledge/concepts/not-a-real-concept", headers=_headers())
    assert missing.status_code == 404
