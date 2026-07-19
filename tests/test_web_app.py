"""Phase 9 persistent web app is served from the API process."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("ALPHADESK_OBJECT_STORE_DIR", str(tmp_path / "objects"))
    return TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'web.db'}"))


@pytest.mark.server
def test_web_app_served(client: TestClient) -> None:
    root = client.get("/", follow_redirects=False)
    assert root.status_code in {307, 302}
    assert root.headers["location"].endswith("/app/")

    page = client.get("/app/")
    assert page.status_code == 200
    assert "AlphaDesk" in page.text
    assert "/app/app.js" in page.text
    assert "Run research" in page.text

    js = client.get("/app/app.js")
    assert js.status_code == 200
    assert "X-Workspace-Id" in js.text
    assert "/v1/runs/start" in js.text
    assert js.headers.get("cache-control", "").startswith("no-store")

    css = client.get("/app/styles.css")
    assert css.status_code == 200
    assert "--accent" in css.text
