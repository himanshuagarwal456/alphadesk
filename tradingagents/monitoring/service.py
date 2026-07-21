"""Monitoring service — poll → classify → dedup → cards / notifications."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
from hashlib import sha256
from typing import Any

from sqlalchemy.orm import Session

from tradingagents.domain.schemas import IntelligenceCardRecord
from tradingagents.monitoring.materiality import classify_materiality, fingerprint_for
from tradingagents.monitoring.pollers import EventPoller, demo_events_for_symbols
from tradingagents.monitoring.schemas import (
    CardStatus,
    DetectedEvent,
    MonitorDefinition,
    MonitorKind,
    MonitorRun,
    MonitorRunStatus,
    Notification,
    NotificationStatus,
)
from tradingagents.persistence.repositories.cards import IntelligenceCardRepository
from tradingagents.persistence.repositories.monitoring import MonitoringRepository
from tradingagents.persistence.repositories.portfolios import PortfolioRepository
from tradingagents.persistence.repositories.state import (
    PortfolioStateRepository,
    WatchlistRepository,
)
from tradingagents.portfolio.service import CURRENT_SNAPSHOT_ID


class MonitoringService:
    def __init__(
        self,
        session: Session,
        *,
        workspace_id: str,
        poller: EventPoller | None = None,
        queue_analysis: Any | None = None,
    ):
        self._session = session
        self._workspace_id = workspace_id
        self._repo = MonitoringRepository(session)
        self._cards = IntelligenceCardRepository(session)
        self._poller = poller
        self._queue_analysis = queue_analysis

    def ensure_default_monitors(self) -> list[MonitorDefinition]:
        existing = self._repo.list_monitors(self._workspace_id)
        if existing:
            return existing
        defaults = [
            MonitorDefinition(
                workspace_id=self._workspace_id,
                kind=MonitorKind.SEC_FILINGS,
                name="SEC filings",
            ),
            MonitorDefinition(
                workspace_id=self._workspace_id,
                kind=MonitorKind.COMPANY_NEWS,
                name="Company news",
            ),
            MonitorDefinition(
                workspace_id=self._workspace_id,
                kind=MonitorKind.PRICE_TRIGGER,
                name="Price triggers",
                queue_targeted_analysis=True,
            ),
        ]
        return [self._repo.save_monitor(m) for m in defaults]

    def list_monitors(self) -> list[MonitorDefinition]:
        return self.ensure_default_monitors()

    def save_monitor(self, monitor: MonitorDefinition) -> MonitorDefinition:
        monitor = monitor.model_copy(update={"workspace_id": self._workspace_id})
        return self._repo.save_monitor(monitor)

    def monitored_symbols(self) -> list[str]:
        controls = PortfolioStateRepository(self._session).get_controls(self._workspace_id)
        if not controls.monitoring_enabled:
            return []

        symbols: set[str] = set()
        snapshot_id = controls.current_snapshot_id or CURRENT_SNAPSHOT_ID
        book = PortfolioRepository(self._session).get(self._workspace_id, snapshot_id)
        if book is None and snapshot_id != CURRENT_SNAPSHOT_ID:
            book = PortfolioRepository(self._session).get(
                self._workspace_id, CURRENT_SNAPSHOT_ID
            )
        if book is not None:
            for pos in book.open_positions:
                symbols.add(pos.symbol.upper())

        for watchlist in WatchlistRepository(self._session).list(self._workspace_id):
            for item in watchlist.items:
                if item.monitoring_enabled:
                    symbols.add(item.symbol.upper())

        for monitor in self.list_monitors():
            if monitor.enabled and monitor.symbols:
                symbols.update(monitor.symbols)
        return sorted(symbols)

    def ingest_events(
        self,
        events: Sequence[DetectedEvent],
        *,
        monitor_id: str | None = None,
        use_demo_if_empty: bool = False,
    ) -> MonitorRun:
        controls = PortfolioStateRepository(self._session).get_controls(self._workspace_id)
        run = MonitorRun(
            workspace_id=self._workspace_id,
            monitor_id=monitor_id,
            status=MonitorRunStatus.RUNNING,
        )
        if not controls.monitoring_enabled:
            run.status = MonitorRunStatus.SKIPPED
            run.completed_at = datetime.now(timezone.utc)
            run.payload = {"reason": "monitoring_paused"}
            return self._repo.save_run(run)

        symbols = self.monitored_symbols()
        pending = [
            e.model_copy(update={"workspace_id": self._workspace_id})
            for e in events
            if e.symbol.upper() in set(symbols) or not symbols
        ]
        if self._poller is not None:
            try:
                pending.extend(self._poller(self._workspace_id, symbols or ["SPY"]))
            except Exception as exc:
                run.errors.append(str(exc))

        if use_demo_if_empty and not pending:
            pending = demo_events_for_symbols(
                self._workspace_id, (symbols[:5] or ["SPY"])
            )

        run.events_seen = len(pending)
        created_cards: list[str] = []
        queued_runs: list[str] = []

        for event in pending:
            verdict = classify_materiality(event)
            if not verdict.material:
                continue
            run.events_material += 1
            fp = fingerprint_for(event, verdict)
            if self._repo.has_fingerprint(self._workspace_id, fp):
                run.duplicates_skipped += 1
                continue

            card = self._build_card(event, verdict)
            saved_card = self._cards.save(card, workspace_id=self._workspace_id)
            self._repo.save_fingerprint(
                self._workspace_id, fp, intelligence_card_id=saved_card.id
            )
            note = Notification(
                workspace_id=self._workspace_id,
                title=saved_card.title or saved_card.headline or event.title,
                body=verdict.reason,
                symbol=event.symbol,
                intelligence_card_id=saved_card.id,
                monitor_run_id=run.id,
                status=NotificationStatus.UNREAD,
            )
            self._repo.save_notification(note)
            created_cards.append(saved_card.id)
            run.cards_created += 1

            monitor = None
            if monitor_id:
                monitor = next(
                    (m for m in self.list_monitors() if m.id == monitor_id), None
                )
            should_queue = verdict.should_queue_analysis and (
                monitor.queue_targeted_analysis if monitor else False
            )
            if should_queue and self._queue_analysis is not None:
                try:
                    queued = self._queue_analysis(
                        symbol=event.symbol,
                        selected_analysts=["news"],
                    )
                    if queued is not None and getattr(queued, "id", None):
                        queued_runs.append(str(queued.id))
                except Exception as exc:
                    run.errors.append(f"queue_analysis:{exc}")

        run.status = (
            MonitorRunStatus.FAILED if run.errors and not created_cards else MonitorRunStatus.COMPLETED
        )
        run.completed_at = datetime.now(timezone.utc)
        run.payload = {
            "card_ids": created_cards,
            "queued_run_ids": queued_runs,
        }
        return self._repo.save_run(run)

    def tick(self, *, use_demo_if_empty: bool = True) -> MonitorRun:
        return self.ingest_events([], use_demo_if_empty=use_demo_if_empty)

    def health(self) -> dict[str, Any]:
        runs = self._repo.list_runs(self._workspace_id, limit=20)
        controls = PortfolioStateRepository(self._session).get_controls(self._workspace_id)
        failures = [r for r in runs if r.status is MonitorRunStatus.FAILED]
        return {
            "monitoring_enabled": controls.monitoring_enabled,
            "monitored_symbols": self.monitored_symbols(),
            "monitors": len(self.list_monitors()),
            "recent_runs": len(runs),
            "recent_failures": len(failures),
            "last_run": runs[0].model_dump(mode="json") if runs else None,
            "unread_notifications": len(
                self._repo.list_notifications(
                    self._workspace_id, status=NotificationStatus.UNREAD, limit=100
                )
            ),
        }

    def list_notifications(
        self, *, status: NotificationStatus | None = None, limit: int = 50
    ) -> list[Notification]:
        return self._repo.list_notifications(
            self._workspace_id, status=status, limit=limit
        )

    def mark_notification(
        self, notification_id: str, *, status: NotificationStatus
    ) -> Notification | None:
        return self._repo.update_notification_status(
            self._workspace_id, notification_id, status=status
        )

    def update_card_status(
        self, card_id: str, *, status: CardStatus
    ) -> IntelligenceCardRecord | None:
        card = self._cards.get(self._workspace_id, card_id)
        if card is None:
            return None
        updated = card.model_copy(update={"status": status.value})
        return self._cards.save(updated, workspace_id=self._workspace_id)

    def _build_card(
        self, event: DetectedEvent, verdict
    ) -> IntelligenceCardRecord:
        card_id = "card_" + sha256(
            f"{event.workspace_id}|{event.id}|{verdict.impact_key}".encode()
        ).hexdigest()[:20]
        evidence_ids = [event.evidence_id] if event.evidence_id else []
        return IntelligenceCardRecord(
            id=card_id,
            workspace_id=self._workspace_id,
            symbol=event.symbol,
            card_type=event.event_type or "monitoring",
            title=event.title,
            headline=event.title,
            body=event.summary or verdict.reason,
            evidence_ids=evidence_ids,
            status=CardStatus.NEW.value,
            materiality_score=verdict.score,
            confidence=verdict.score,
            fingerprint=fingerprint_for(event, verdict),
            payload={
                "source": event.source,
                "materiality_reason": verdict.reason,
                "impact_key": verdict.impact_key,
                "url": event.url,
                "event_id": event.id,
                "portfolio_relevance": (
                    f"{event.symbol} is on the monitored book or watchlist."
                ),
            },
        )
