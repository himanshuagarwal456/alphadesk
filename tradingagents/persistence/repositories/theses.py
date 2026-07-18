"""Living-thesis repository (workspace-scoped)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from tradingagents.thesis.schemas import LivingThesis, ThesisSnapshot
from tradingagents.thesis.workflow import ProposedRevision, RevisionStatus

from ..models import ThesisProposalRow, ThesisRow, ThesisSnapshotRow
from .workspaces import WorkspaceRepository


class ThesisRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert(
        self,
        thesis: LivingThesis,
        snapshot: ThesisSnapshot | None = None,
        *,
        workspace_id: str,
    ) -> LivingThesis:
        WorkspaceRepository(self._session).ensure(workspace_id)
        symbol = thesis.symbol.upper()
        row = self._session.scalars(
            select(ThesisRow).where(
                ThesisRow.workspace_id == workspace_id,
                ThesisRow.symbol == symbol,
            )
        ).first()
        payload = thesis.model_dump(mode="json")
        if row is None:
            self._session.add(
                ThesisRow(
                    workspace_id=workspace_id,
                    symbol=symbol,
                    status=thesis.status.value,
                    current_snapshot_id=thesis.current_snapshot_id,
                    payload=payload,
                )
            )
        else:
            row.status = thesis.status.value
            row.current_snapshot_id = thesis.current_snapshot_id
            row.payload = payload
        if snapshot is not None:
            self._save_snapshot(workspace_id, snapshot)
        self._session.flush()
        return thesis

    def _save_snapshot(self, workspace_id: str, snapshot: ThesisSnapshot) -> None:
        existing = self._session.scalars(
            select(ThesisSnapshotRow).where(
                ThesisSnapshotRow.workspace_id == workspace_id,
                ThesisSnapshotRow.snapshot_id == snapshot.snapshot_id,
            )
        ).first()
        payload = snapshot.model_dump(mode="json")
        if existing is None:
            self._session.add(
                ThesisSnapshotRow(
                    snapshot_id=snapshot.snapshot_id,
                    workspace_id=workspace_id,
                    symbol=snapshot.symbol.upper(),
                    as_of=snapshot.as_of,
                    payload=payload,
                    created_at=snapshot.created_at,
                )
            )
        else:
            existing.payload = payload

    def get(self, workspace_id: str, symbol: str) -> LivingThesis | None:
        row = self._session.scalars(
            select(ThesisRow).where(
                ThesisRow.workspace_id == workspace_id,
                ThesisRow.symbol == symbol.strip().upper(),
            )
        ).first()
        if row is None:
            return None
        return LivingThesis.model_validate(row.payload)

    def get_snapshot(self, workspace_id: str, snapshot_id: str) -> ThesisSnapshot | None:
        row = self._session.scalars(
            select(ThesisSnapshotRow).where(
                ThesisSnapshotRow.workspace_id == workspace_id,
                ThesisSnapshotRow.snapshot_id == snapshot_id,
            )
        ).first()
        if row is None:
            return None
        return ThesisSnapshot.model_validate(row.payload)

    def list_snapshots(self, workspace_id: str, symbol: str) -> list[ThesisSnapshot]:
        stmt = (
            select(ThesisSnapshotRow)
            .where(
                ThesisSnapshotRow.workspace_id == workspace_id,
                ThesisSnapshotRow.symbol == symbol.strip().upper(),
            )
            .order_by(ThesisSnapshotRow.as_of.asc(), ThesisSnapshotRow.created_at.asc())
        )
        return [
            ThesisSnapshot.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]

    def list(self, workspace_id: str, *, limit: int = 100) -> list[LivingThesis]:
        stmt = (
            select(ThesisRow)
            .where(ThesisRow.workspace_id == workspace_id)
            .order_by(ThesisRow.updated_at.desc())
            .limit(limit)
        )
        return [LivingThesis.model_validate(row.payload) for row in self._session.scalars(stmt)]

    def save_proposal(
        self,
        proposal: ProposedRevision,
        *,
        workspace_id: str,
    ) -> ProposedRevision:
        WorkspaceRepository(self._session).ensure(workspace_id)
        data = proposal.model_dump(mode="json")
        row = self._session.scalars(
            select(ThesisProposalRow).where(
                ThesisProposalRow.workspace_id == workspace_id,
                ThesisProposalRow.id == proposal.id,
            )
        ).first()
        now = datetime.now(timezone.utc)
        if row is None:
            self._session.add(
                ThesisProposalRow(
                    id=proposal.id,
                    workspace_id=workspace_id,
                    symbol=proposal.symbol.upper(),
                    status=proposal.status.value,
                    payload=data,
                    created_at=proposal.created_at,
                    updated_at=now,
                )
            )
        else:
            row.status = proposal.status.value
            row.payload = data
            row.updated_at = now
        self._session.flush()
        return proposal

    def get_proposal(
        self, workspace_id: str, proposal_id: str
    ) -> ProposedRevision | None:
        row = self._session.scalars(
            select(ThesisProposalRow).where(
                ThesisProposalRow.workspace_id == workspace_id,
                ThesisProposalRow.id == proposal_id,
            )
        ).first()
        if row is None:
            return None
        return ProposedRevision.model_validate(row.payload)

    def list_proposals(
        self,
        workspace_id: str,
        symbol: str,
        *,
        status: RevisionStatus | None = None,
        limit: int = 100,
    ) -> list[ProposedRevision]:
        stmt = select(ThesisProposalRow).where(
            ThesisProposalRow.workspace_id == workspace_id,
            ThesisProposalRow.symbol == symbol.strip().upper(),
        )
        if status is not None:
            stmt = stmt.where(ThesisProposalRow.status == status.value)
        stmt = stmt.order_by(ThesisProposalRow.created_at.desc()).limit(limit)
        return [
            ProposedRevision.model_validate(row.payload)
            for row in self._session.scalars(stmt)
        ]
