"""Phase 6 thesis + journal product API tests."""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("fastapi")
pytest.importorskip("sqlalchemy")

from fastapi.testclient import TestClient

from tradingagents.api.app import create_app


@pytest.fixture
def client(tmp_path: Path) -> TestClient:
    app = create_app(database_url=f"sqlite:///{tmp_path / 'p6.db'}")
    return TestClient(app)


def _headers(workspace: str = "ws_p6") -> dict[str, str]:
    return {"X-Workspace-Id": workspace}


def _seed_completed_run(client: TestClient, workspace: str = "ws_p6") -> str:
    created = client.post(
        "/v1/runs",
        headers=_headers(workspace),
        json={
            "symbol": "NVDA",
            "trade_date": "2026-07-18",
            "status": "completed",
        },
    )
    assert created.status_code == 201
    run_id = created.json()["id"]
    # Enrich the durable run with structured decision fields via save.
    from tradingagents.domain.schemas import AnalysisRun, RunStatus
    from tradingagents.persistence.repositories import AnalysisRunRepository

    app = client.app
    factory = app.state.alphadesk.session_factory
    with factory.session_scope() as session:
        run = AnalysisRun(
            id=run_id,
            symbol="NVDA",
            trade_date="2026-07-18",
            status=RunStatus.COMPLETED,
            evidence_ids=["ev_a", "ev_b"],
            final_rating="Buy",
            portfolio_decision_struct={
                "rating": "Buy",
                "executive_summary": "Accumulate on dips.",
                "investment_thesis": "AI demand remains durable.",
                "price_target": 200.0,
                "time_horizon": "6-12 months",
                "catalysts": ["Earnings beat"],
                "invalidation_conditions": ["Gross margin collapse"],
                "invalidation_triggered": False,
            },
            bull_case="Accelerating data-center spend.",
            bear_case="Customer capex pause.",
            risks=["Export controls"],
            workspace_id=workspace,
        )
        AnalysisRunRepository(session).save(run, workspace_id=workspace)
    return run_id


@pytest.mark.server
def test_create_from_run_propose_reject_accept(client: TestClient):
    run_id = _seed_completed_run(client)
    proposed = client.post(
        "/v1/theses/from-run",
        headers=_headers(),
        json={"run_id": run_id, "stance": "initiate", "accept": False},
    )
    assert proposed.status_code == 201
    proposal = proposed.json()
    assert proposal["status"] == "proposed"
    assert proposal["snapshot"]["bull_case"]
    assert proposal["snapshot"]["author"] == "ai"
    assert proposal["snapshot"]["evidence_ids"] == ["ev_a", "ev_b"]

    # Head must not change until accept.
    assert client.get("/v1/theses/NVDA", headers=_headers()).status_code == 404

    rejected = client.post(
        f"/v1/theses/NVDA/proposals/{proposal['id']}/review",
        headers=_headers(),
        json={"accept": False, "note": "Not yet"},
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "rejected"
    assert client.get("/v1/theses/NVDA", headers=_headers()).status_code == 404

    # New proposal, accept with user edits.
    again = client.post(
        "/v1/theses/from-run",
        headers=_headers(),
        json={"run_id": run_id, "stance": "initiate", "reason": "retry", "accept": False},
    )
    proposal2 = again.json()
    edited = dict(proposal2["snapshot"])
    edited["investment_thesis"] = "User-refined thesis text."
    edited["confidence"] = 0.72
    accepted = client.post(
        f"/v1/theses/NVDA/proposals/{proposal2['id']}/review",
        headers=_headers(),
        json={"accept": True, "edited_snapshot": edited, "note": "Edited then accepted"},
    )
    assert accepted.status_code == 200
    assert accepted.json()["status"] == "accepted"
    assert accepted.json()["snapshot"]["author"] == "user"

    head = client.get("/v1/theses/NVDA", headers=_headers())
    assert head.status_code == 200
    assert head.json()["current"]["investment_thesis"] == "User-refined thesis text."
    assert head.json()["current_snapshot_id"] == edited["snapshot_id"]

    snaps = client.get("/v1/theses/NVDA/snapshots", headers=_headers())
    assert len(snaps.json()) >= 1


@pytest.mark.server
def test_revision_diff_and_evidence_selection(client: TestClient):
    run_id = _seed_completed_run(client)
    p1 = client.post(
        "/v1/theses/from-run",
        headers=_headers(),
        json={"run_id": run_id, "accept": True},
    ).json()
    assert p1["status"] == "accepted"
    # Propose a second revision with different rating/evidence.
    snapshot = dict(p1["snapshot"])
    snapshot["snapshot_id"] = "th_NVDA_2026-07-19"
    snapshot["as_of"] = "2026-07-19"
    snapshot["prior_snapshot_id"] = p1["snapshot"]["snapshot_id"]
    snapshot["rating"] = "Hold"
    snapshot["evidence_ids"] = ["ev_a", "ev_c"]
    proposed = client.post(
        "/v1/theses/NVDA/proposals",
        headers=_headers(),
        json={"snapshot": snapshot, "reason": "AI update", "author": "ai"},
    )
    assert proposed.status_code == 201
    client.post(
        f"/v1/theses/NVDA/proposals/{proposed.json()['id']}/review",
        headers=_headers(),
        json={"accept": True},
    )
    diff = client.get(
        "/v1/theses/NVDA/diff",
        headers=_headers(),
        params={
            "prior": p1["snapshot"]["snapshot_id"],
            "current": "th_NVDA_2026-07-19",
        },
    )
    assert diff.status_code == 200
    assert diff.json()["rating_downgraded"] is True
    assert "ev_c" in diff.json()["evidence_added"]

    evidence = client.post(
        "/v1/theses/NVDA/evidence",
        headers=_headers(),
        json={"evidence_ids": ["ev_a"], "reason": "Trim noise"},
    )
    assert evidence.status_code == 201
    assert evidence.json()["status"] == "proposed"


@pytest.mark.server
def test_journal_outcome_and_lesson_reuse(client: TestClient):
    # Activate a current portfolio snapshot for linkage.
    client.post(
        "/v1/portfolios/import/confirm",
        headers=_headers(),
        json={
            "portfolio": {
                "as_of": "2026-07-18",
                "positions": [{"symbol": "NVDA", "quantity": 10, "current_price": 100}],
            }
        },
    )
    entry = client.post(
        "/v1/journal",
        headers=_headers(),
        json={
            "symbol": "NVDA",
            "trade_date": "2026-07-18",
            "decision_type": "add",
            "rationale": "Add on weakness",
            "confidence": 0.7,
            "expected_horizon": "6 months",
            "thesis_snapshot_id": "th_NVDA_2026-07-18",
            "portfolio_snapshot_id": "current",
            "allow_lesson_reuse": True,
        },
    )
    assert entry.status_code == 201
    entry_id = entry.json()["id"]
    assert entry.json()["portfolio_snapshot_id"] == "current"

    # Append-only: duplicate id conflicts.
    again = client.post("/v1/journal", headers=_headers(), json=entry.json())
    assert again.status_code == 409

    outcome = client.post(
        f"/v1/journal/{entry_id}/outcomes",
        headers=_headers(),
        json={
            "as_of": "2026-10-18",
            "outcome_summary": "Outperformed on AI news.",
            "lesson": "Size faster into confirmed demand.",
            "allow_lesson_reuse": False,
            "absolute_return_pct": 18.0,
            "benchmark_ticker": "SPY",
            "benchmark_return_pct": 5.0,
        },
    )
    assert outcome.status_code == 201
    body = outcome.json()
    assert body["relative_return_pct"] == pytest.approx(13.0)
    assert body["allow_lesson_reuse"] is False

    fetched = client.get(f"/v1/journal/{entry_id}", headers=_headers())
    assert fetched.json()["allow_lesson_reuse"] is False

    outcomes = client.get(f"/v1/journal/{entry_id}/outcomes", headers=_headers())
    assert len(outcomes.json()) == 1


@pytest.mark.server
def test_cross_workspace_thesis_isolation(client: TestClient):
    run_id = _seed_completed_run(client, "ws_owner")
    proposal = client.post(
        "/v1/theses/from-run",
        headers=_headers("ws_owner"),
        json={"run_id": run_id, "accept": True},
    ).json()
    assert proposal["status"] == "accepted"
    assert client.get("/v1/theses/NVDA", headers=_headers("ws_owner")).status_code == 200
    assert client.get("/v1/theses/NVDA", headers=_headers("ws_other")).status_code == 404
