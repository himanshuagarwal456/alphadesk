"""Usage, audit, and dead-letter persistence."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.observability.schemas import (
    AuditEvent,
    DeadLetterRecord,
    DeadLetterStatus,
    UsageRecord,
    UsageSummary,
)

from ..models import AuditEventRow, DeadLetterRow, UsageRecordRow
from .workspaces import WorkspaceRepository


class OpsRepository:
    def __init__(self, session: Session):
        self._session = session

    def save_usage(self, record: UsageRecord) -> UsageRecord:
        WorkspaceRepository(self._session).ensure(record.workspace_id)
        data = record.model_dump(mode="json")
        self._session.add(
            UsageRecordRow(
                id=record.id,
                workspace_id=record.workspace_id,
                analysis_run_id=record.analysis_run_id,
                kind=record.kind,
                estimated_cost_usd=record.estimated_cost_usd,
                payload=data,
                created_at=record.created_at,
            )
        )
        self._session.flush()
        return record

    def list_usage(self, workspace_id: str, *, limit: int = 100) -> list[UsageRecord]:
        stmt = (
            select(UsageRecordRow)
            .where(UsageRecordRow.workspace_id == workspace_id)
            .order_by(UsageRecordRow.created_at.desc())
            .limit(limit)
        )
        return [
            UsageRecord.model_validate(row.payload) for row in self._session.scalars(stmt)
        ]

    def summarize_usage(self, workspace_id: str, *, limit: int = 500) -> UsageSummary:
        records = self.list_usage(workspace_id, limit=limit)
        summary = UsageSummary(workspace_id=workspace_id)
        for rec in records:
            summary.runs += 1
            summary.llm_calls += rec.llm_calls
            summary.tool_calls += rec.tool_calls
            summary.tokens_in += rec.tokens_in
            summary.tokens_out += rec.tokens_out
            summary.provider_calls += rec.provider_calls
            summary.provider_errors += rec.provider_errors
            if rec.estimated_cost_usd is not None:
                summary.estimated_cost_usd = round(
                    summary.estimated_cost_usd + rec.estimated_cost_usd, 6
                )
            if rec.duration_ms:
                summary.duration_ms += rec.duration_ms
        return summary

    def save_audit(self, event: AuditEvent) -> AuditEvent:
        WorkspaceRepository(self._session).ensure(event.workspace_id)
        data = event.model_dump(mode="json")
        self._session.add(
            AuditEventRow(
                id=event.id,
                workspace_id=event.workspace_id,
                action=event.action,
                resource_type=event.resource_type,
                resource_id=event.resource_id,
                payload=data,
                created_at=event.created_at,
            )
        )
        self._session.flush()
        return event

    def list_audit(self, workspace_id: str, *, limit: int = 100) -> list[AuditEvent]:
        stmt = (
            select(AuditEventRow)
            .where(AuditEventRow.workspace_id == workspace_id)
            .order_by(AuditEventRow.created_at.desc())
            .limit(limit)
        )
        return [
            AuditEvent.model_validate(row.payload) for row in self._session.scalars(stmt)
        ]

    def save_dead_letter(self, record: DeadLetterRecord) -> DeadLetterRecord:
        WorkspaceRepository(self._session).ensure(record.workspace_id)
        data = record.model_dump(mode="json")
        row = self._session.scalars(
            select(DeadLetterRow).where(
                DeadLetterRow.workspace_id == record.workspace_id,
                DeadLetterRow.id == record.id,
            )
        ).first()
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                DeadLetterRow(
                    id=record.id,
                    workspace_id=record.workspace_id,
                    analysis_run_id=record.analysis_run_id,
                    status=record.status.value,
                    payload=data,
                    created_at=record.created_at,
                    updated_at=now,
                )
            )
        else:
            row.status = record.status.value
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return record

    def list_dead_letters(
        self,
        workspace_id: str,
        *,
        status: DeadLetterStatus | None = None,
        limit: int = 50,
    ) -> list[DeadLetterRecord]:
        stmt = select(DeadLetterRow).where(DeadLetterRow.workspace_id == workspace_id)
        if status is not None:
            stmt = stmt.where(DeadLetterRow.status == status.value)
        stmt = stmt.order_by(DeadLetterRow.updated_at.desc()).limit(limit)
        return [
            DeadLetterRecord.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]
