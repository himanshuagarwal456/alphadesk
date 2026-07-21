"""Monitoring / material-change intelligence package."""

from tradingagents.monitoring.schemas import (
    CardStatus,
    DetectedEvent,
    MaterialityVerdict,
    MonitorDefinition,
    MonitorRun,
    Notification,
)

__all__ = [
    "CardStatus",
    "DetectedEvent",
    "MaterialityVerdict",
    "MonitorDefinition",
    "MonitorRun",
    "MonitoringService",
    "Notification",
]


def __getattr__(name: str):
    if name == "MonitoringService":
        from tradingagents.monitoring.service import MonitoringService

        return MonitoringService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
