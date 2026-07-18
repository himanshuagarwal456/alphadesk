"""Phase 3 persistence: repositories, object store, exporters, migrations."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

pytest.importorskip("sqlalchemy")
# Import a submodule so a stray local ``alembic/`` directory cannot mask the
# real library the way ``importorskip("alembic")`` would.
pytest.importorskip("alembic.config")

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect, text

from tradingagents.agents.schemas import PortfolioRating
from tradingagents.domain.schemas import AnalysisRun, IntelligenceCardRecord, RunStatus
from tradingagents.evidence.schemas import Evidence
from tradingagents.journal.schemas import DecisionJournalEntry, DecisionType
from tradingagents.persistence.exporters import CompatibilityExporter
from tradingagents.persistence.object_store import LocalObjectStore
from tradingagents.persistence.repositories import (
    AnalysisRunRepository,
    EvidenceRepository,
    IntelligenceCardRepository,
    JournalRepository,
    PortfolioRepository,
    RunEventRepository,
    ThesisRepository,
    WorkspaceRepository,
)
from tradingagents.persistence.session import SessionFactory, create_engine_from_url
from tradingagents.portfolio.schemas import Portfolio, Position
from tradingagents.thesis.schemas import LivingThesis, ThesisSnapshot, ThesisStatus


@pytest.fixture
def db(tmp_path: Path) -> SessionFactory:
    url = f"sqlite:///{tmp_path / 'phase3.db'}"
    factory = SessionFactory(create_engine_from_url(url))
    factory.create_all()
    return factory


@pytest.mark.unit
@pytest.mark.server
def test_workspace_isolation_for_runs(db: SessionFactory):
    with db.session_scope() as session:
        runs = AnalysisRunRepository(session)
        a = runs.save(
            AnalysisRun(symbol="AAPL", trade_date="2026-01-15", status=RunStatus.QUEUED),
            workspace_id="ws_a",
        )
        b = runs.save(
            AnalysisRun(symbol="MSFT", trade_date="2026-01-15", status=RunStatus.QUEUED),
            workspace_id="ws_b",
        )
        assert runs.get("ws_a", a.id) is not None
        assert runs.get("ws_b", a.id) is None
        assert runs.get("ws_a", b.id) is None
        assert [r.symbol for r in runs.list("ws_a")] == ["AAPL"]
        assert [r.symbol for r in runs.list("ws_b")] == ["MSFT"]


@pytest.mark.unit
@pytest.mark.server
def test_run_status_and_event_stream_survive_new_session(db: SessionFactory, tmp_path: Path):
    with db.session_scope() as session:
        runs = AnalysisRunRepository(session)
        events = RunEventRepository(session)
        run = runs.save(
            AnalysisRun(symbol="NVDA", trade_date="2026-02-01", status=RunStatus.QUEUED),
            workspace_id="ws_1",
        )
        events.append(
            workspace_id="ws_1",
            analysis_run_id=run.id,
            event_type="stage.started",
            message="market analyst",
        )
        runs.update_status("ws_1", run.id, RunStatus.RUNNING)
        events.append(
            workspace_id="ws_1",
            analysis_run_id=run.id,
            event_type="stage.completed",
            message="market analyst",
        )
        runs.update_status("ws_1", run.id, RunStatus.COMPLETED)
        run_id = run.id

    # New session = process-restart equivalent for SQLite file durability.
    with db.session_scope() as session:
        restored = AnalysisRunRepository(session).get("ws_1", run_id)
        assert restored is not None
        assert restored.status is RunStatus.COMPLETED
        assert restored.started_at is not None
        assert restored.completed_at is not None
        stream = RunEventRepository(session).list_for_run("ws_1", run_id)
        assert [e.event_type for e in stream] == ["stage.started", "stage.completed"]
        assert [e.sequence for e in stream] == [0, 1]


@pytest.mark.unit
@pytest.mark.server
def test_persist_evidence_thesis_journal_portfolio_cards(db: SessionFactory):
    with db.session_scope() as session:
        EvidenceRepository(session).save_many(
            [Evidence(provider_id="sec", title="10-K", source_type="filing")],
            workspace_id="ws_1",
        )
        snapshot = ThesisSnapshot(
            snapshot_id="th_NVDA_2026-02-01",
            symbol="NVDA",
            as_of="2026-02-01",
            rating=PortfolioRating.BUY,
            executive_summary="Buy",
            investment_thesis="AI demand",
        )
        thesis = LivingThesis(
            symbol="NVDA",
            status=ThesisStatus.ACTIVE,
            current_snapshot_id=snapshot.snapshot_id,
            opened_at="2026-02-01",
            updated_at="2026-02-01",
            snapshot_ids=[snapshot.snapshot_id],
            confidence_history=[],
            current=snapshot,
        )
        ThesisRepository(session).upsert(thesis, snapshot, workspace_id="ws_1")
        JournalRepository(session).save(
            DecisionJournalEntry(
                symbol="NVDA",
                trade_date="2026-02-01",
                decision_type=DecisionType.ADD,
                rationale="Add on weakness",
            ),
            workspace_id="ws_1",
        )
        PortfolioRepository(session).save(
            Portfolio(
                as_of="2026-02-01",
                positions=[Position(symbol="NVDA", quantity=10, current_price=100.0)],
            ),
            workspace_id="ws_1",
        )
        IntelligenceCardRepository(session).save(
            IntelligenceCardRecord(
                id="card_1",
                workspace_id="ws_1",
                symbol="NVDA",
                card_type="thesis_change",
                title="Thesis updated",
                headline="Conviction up",
            ),
            workspace_id="ws_1",
        )

    with db.session_scope() as session:
        assert EvidenceRepository(session).list("ws_1")
        assert ThesisRepository(session).get("ws_1", "NVDA") is not None
        assert JournalRepository(session).list("ws_1", symbol="NVDA")
        assert PortfolioRepository(session).list("ws_1")
        assert IntelligenceCardRepository(session).get("ws_1", "card_1") is not None
        assert EvidenceRepository(session).list("ws_other") == []


@pytest.mark.unit
@pytest.mark.server
def test_object_store_and_compatibility_exporter(tmp_path: Path):
    store = LocalObjectStore(tmp_path / "objects")
    stored = store.put("ws_1/raw/a.txt", b"hello", content_type="text/plain")
    assert stored.content_hash
    assert store.get("ws_1/raw/a.txt") == b"hello"
    with pytest.raises(ValueError):
        store.put("../escape.txt", b"nope")

    exporter = CompatibilityExporter(tmp_path / "results")
    run = AnalysisRun(
        symbol="AAPL",
        trade_date="2026-03-01",
        status=RunStatus.COMPLETED,
        evidence_ids=["ev_1"],
    )
    path = exporter.export_analysis_run(run)
    assert path.exists()
    evidence_path = exporter.export_evidence(
        [Evidence(provider_id="yfinance", title="News")],
        symbol="AAPL",
        trade_date="2026-03-01",
    )
    assert evidence_path.exists()
    md_dir = exporter.export_run_markdown(
        symbol="AAPL",
        trade_date="2026-03-01",
        sections={"final_trade_decision": "# Hold"},
    )
    assert (md_dir / "final_trade_decision.md").read_text(encoding="utf-8") == "# Hold"


@pytest.mark.unit
@pytest.mark.server
def test_alembic_upgrade_and_downgrade(tmp_path: Path):
    db_path = tmp_path / "migrate.db"
    url = f"sqlite:///{db_path}"
    os.environ["ALPHADESK_DATABASE_URL"] = url
    try:
        cfg = Config(str(Path(__file__).resolve().parents[1] / "alembic.ini"))
        cfg.set_main_option("sqlalchemy.url", url)
        command.upgrade(cfg, "head")
        engine = create_engine(url)
        tables = set(inspect(engine).get_table_names())
        assert "workspaces" in tables
        assert "analysis_runs" in tables
        assert "run_events" in tables
        with engine.connect() as conn:
            conn.execute(text("SELECT 1 FROM alembic_version"))
        command.downgrade(cfg, "base")
        tables_after = set(inspect(engine).get_table_names())
        assert "workspaces" not in tables_after
        assert tables_after <= {"alembic_version"} or "alembic_version" in tables_after
    finally:
        os.environ.pop("ALPHADESK_DATABASE_URL", None)


@pytest.mark.unit
@pytest.mark.server
def test_workspace_repository_ensure(db: SessionFactory):
    with db.session_scope() as session:
        repo = WorkspaceRepository(session)
        ws = repo.ensure("ws_x", name="Example")
        again = repo.ensure("ws_x", name="Ignored")
        assert ws.id == again.id
        assert repo.get("ws_x").name == "Example"
