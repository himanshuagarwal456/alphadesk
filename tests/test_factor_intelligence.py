"""Batch 1 Portfolio Factor Intelligence tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tradingagents.factor_intelligence.catalog import active_model_version
from tradingagents.factor_intelligence.characteristics import (
    compute_characteristics,
    standardize,
    winsorize,
)
from tradingagents.factor_intelligence.exposures import (
    aggregate_portfolio_exposures,
    build_security_exposures,
)
from tradingagents.factor_intelligence.fixtures import fixture_universe
from tradingagents.portfolio.schemas import Portfolio, Position

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app


def test_characteristics_and_standardization_are_deterministic() -> None:
    snaps = fixture_universe(["AAPL", "AMD", "JPM", "XOM"], as_of="2026-07-21")
    model = active_model_version(as_of="2026-07-21")
    chars = compute_characteristics(snaps[0], model_version_id=model.id or "m")
    assert any(c.descriptor_code == "LOG_MARKET_CAP" and c.raw_value for c in chars)

    values = [10.0, 11.0, 12.0, 1000.0, 9.0, 10.5, 11.5, 10.2, 10.1, 10.3]
    clipped = winsorize(values, pct=0.10)
    assert max(v for v in clipped if v is not None) < 1000.0
    z = standardize(clipped)
    assert abs(sum(v for v in z if v is not None)) < 1e-8


def test_security_and_portfolio_exposures_reconcile() -> None:
    as_of = "2026-07-21"
    snaps = fixture_universe(
        ["AAPL", "MSFT", "AMD", "NVDA", "JPM", "XOM", "NEE", "SPY"], as_of=as_of
    )
    model = active_model_version(as_of=as_of)
    sec = build_security_exposures(snaps, model=model)
    assert sec
    assert any(e.factor_code == "MOMENTUM" for e in sec)
    assert any(e.factor_code == "SECTOR_TECHNOLOGY" and e.normalized_exposure == 1.0 for e in sec)

    book = Portfolio(
        as_of=as_of,
        positions=[
            Position(symbol="AAPL", quantity=10, current_price=200),
            Position(symbol="AMD", quantity=20, current_price=160),
            Position(symbol="JPM", quantity=5, current_price=200),
        ],
    )
    portfolio_secs = [e for e in sec if e.symbol in {"AAPL", "AMD", "JPM"}]
    exposures, coverage, unmodeled = aggregate_portfolio_exposures(
        portfolio=book,
        security_exposures=portfolio_secs,
        model=model,
        workspace_id="ws_test",
        portfolio_id="current",
        effective_date=as_of,
    )
    assert coverage == pytest.approx(1.0)
    assert unmodeled == []
    by_code = {e.factor_code: e.portfolio_exposure for e in exposures}
    assert "MARKET" in by_code
    assert "SIZE" in by_code
    # Tech overweight expected from AAPL+AMD
    assert by_code.get("SECTOR_TECHNOLOGY", 0) > by_code.get("SECTOR_FINANCIALS", 0)


@pytest.fixture()
def client(tmp_path: Path) -> TestClient:
    return TestClient(create_app(database_url=f"sqlite:///{tmp_path / 'fi.db'}"))


def _headers(workspace: str = "ws_fi") -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


@pytest.mark.server
def test_factor_model_and_portfolio_exposure_api(client: TestClient) -> None:
    factors = client.get("/v1/factor-models/factors", headers=_headers())
    assert factors.status_code == 200, factors.text
    codes = {f["code"] for f in factors.json()}
    assert {"SIZE", "VALUE", "GROWTH", "MOMENTUM", "QUALITY"}.issubset(codes)

    models = client.get("/v1/factor-models", headers=_headers())
    assert models.status_code == 200
    assert models.json()
    version_id = models.json()[0]["id"]
    got = client.get(f"/v1/factor-models/{version_id}", headers=_headers())
    assert got.status_code == 200

    missing = client.get("/v1/portfolios/current/factor-exposures", headers=_headers())
    assert missing.status_code == 404

    # Create current book
    save = client.post(
        "/v1/portfolios",
        headers=_headers(),
        json={
            "activate": True,
            "portfolio": {
                "as_of": "2026-07-21",
                "base_currency": "USD",
                "positions": [
                    {"symbol": "AAPL", "quantity": 10, "current_price": 200},
                    {"symbol": "AMD", "quantity": 15, "current_price": 160},
                    {"symbol": "NEE", "quantity": 40, "current_price": 75},
                ],
            },
        },
    )
    assert save.status_code in {200, 201}, save.text

    report = client.get("/v1/portfolios/current/factor-exposures", headers=_headers())
    assert report.status_code == 200, report.text
    body = report.json()
    assert body["coverage"] > 0
    assert body["exposures"]
    assert "AlphaDesk" in body["methodology_note"]
    assert any(e["factor_code"] == "MOMENTUM" for e in body["exposures"])
    assert body["security_exposures"]
