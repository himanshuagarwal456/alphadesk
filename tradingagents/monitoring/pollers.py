"""Monitoring event pollers.

Network-backed pollers are optional; alpha defaults to ingest + demo events so
tests and offline desks stay deterministic.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime, timezone

from tradingagents.monitoring.schemas import DetectedEvent
from tradingagents.observability.circuit import CircuitBreaker, CircuitOpenError

EventPoller = Callable[[str, Sequence[str]], list[DetectedEvent]]


def demo_events_for_symbols(
    workspace_id: str, symbols: Sequence[str]
) -> list[DetectedEvent]:
    """Deterministic sample events for empty ticks / onboarding."""
    now = datetime.now(timezone.utc)
    out: list[DetectedEvent] = []
    for symbol in symbols:
        out.append(
            DetectedEvent(
                workspace_id=workspace_id,
                symbol=symbol,
                source="demo",
                event_type="fundamentals",
                title=f"{symbol} gross margin improved on richer mix",
                summary=(
                    f"Reported gross margin for {symbol} expanded versus the prior quarter. "
                    "Review pricing power and whether the living thesis needs an update."
                ),
                evidence_id=f"ev_demo_{symbol.lower()}_gm",
                occurred_at=now,
                payload={"demo": True},
            )
        )
    return out


class StaticPoller:
    """Returns a fixed list of events (tests / injected fixtures)."""

    def __init__(self, events: Sequence[DetectedEvent] | None = None):
        self._events = list(events or [])

    def __call__(self, workspace_id: str, symbols: Sequence[str]) -> list[DetectedEvent]:
        wanted = {s.upper() for s in symbols}
        return [
            e
            for e in self._events
            if e.workspace_id == workspace_id and e.symbol.upper() in wanted
        ]


def guarded_poller(
    poller: EventPoller, breaker: CircuitBreaker
) -> EventPoller:
    def _wrapped(workspace_id: str, symbols: Sequence[str]) -> list[DetectedEvent]:
        breaker.before_call()
        try:
            result = poller(workspace_id, symbols)
            breaker.record_success()
            return result
        except CircuitOpenError:
            raise
        except Exception:
            breaker.record_failure()
            raise

    return _wrapped
