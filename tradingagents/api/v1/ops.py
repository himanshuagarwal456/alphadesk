"""Ops, usage, readiness, audit, and dead-letter endpoints (Phase 11)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_app_state, get_db_session, get_workspace_id
from tradingagents.observability.circuit import CircuitBreaker
from tradingagents.observability.pricing import PRICING_TABLE_VERSION
from tradingagents.observability.schemas import (
    AuditEvent,
    DeadLetterRecord,
    DeadLetterStatus,
    UsageRecord,
    UsageSummary,
)
from tradingagents.persistence.repositories.ops import OpsRepository
from tradingagents.persistence.repositories.runs import AnalysisRunRepository

router = APIRouter(prefix="/ops")

# Process-local breakers exposed for health/diagnostics.
PROVIDER_BREAKERS = {
    "sec": CircuitBreaker("sec"),
    "news": CircuitBreaker("news"),
    "macro": CircuitBreaker("macro"),
}


class ExportResponse(BaseModel):
    workspace_id: str
    runs: int
    usage_records: int
    audit_events: int
    dead_letters: int
    backup_hints: list[str]


@router.get("/ready")
def ready(request: Request) -> dict:
    state = get_app_state(request)
    try:
        with state.session_factory.session_scope() as session:
            session.execute(text("SELECT 1"))
        db_ok = True
        detail = "ok"
    except Exception as exc:  # pragma: no cover - defensive
        db_ok = False
        detail = str(exc)
    return {
        "status": "ready" if db_ok else "not_ready",
        "database": detail,
        "pricing_version": PRICING_TABLE_VERSION,
    }


@router.get("/usage", response_model=UsageSummary)
def usage_summary(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> UsageSummary:
    return OpsRepository(session).summarize_usage(workspace_id)


@router.get("/usage/records", response_model=list[UsageRecord])
def usage_records(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    limit: int = 100,
) -> list[UsageRecord]:
    return OpsRepository(session).list_usage(workspace_id, limit=limit)


@router.get("/audit", response_model=list[AuditEvent])
def list_audit(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    limit: int = 100,
) -> list[AuditEvent]:
    return OpsRepository(session).list_audit(workspace_id, limit=limit)


@router.get("/dead-letters", response_model=list[DeadLetterRecord])
def list_dead_letters(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
    status: DeadLetterStatus | None = None,
    limit: int = 50,
) -> list[DeadLetterRecord]:
    return OpsRepository(session).list_dead_letters(
        workspace_id, status=status, limit=limit
    )


@router.get("/circuits")
def circuit_status() -> dict:
    return {name: breaker.status() for name, breaker in PROVIDER_BREAKERS.items()}


@router.get("/export", response_model=ExportResponse)
def export_workspace_manifest(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> ExportResponse:
    """Return a backup/export manifest for the workspace (operator assist)."""
    runs = AnalysisRunRepository(session).list(workspace_id, limit=500)
    ops = OpsRepository(session)
    usage = ops.list_usage(workspace_id, limit=500)
    audit = ops.list_audit(workspace_id, limit=500)
    dead = ops.list_dead_letters(workspace_id, limit=500)
    return ExportResponse(
        workspace_id=workspace_id,
        runs=len(runs),
        usage_records=len(usage),
        audit_events=len(audit),
        dead_letters=len(dead),
        backup_hints=[
            "Snapshot the configured SQL database (ALPHADESK_DATABASE_URL).",
            "Copy ALPHADESK_OBJECT_STORE_DIR for private research blobs.",
            "Retain usage_records and audit_events for cost/compliance review.",
        ],
    )
