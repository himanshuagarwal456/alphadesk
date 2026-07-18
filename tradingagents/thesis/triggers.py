"""Deterministic lifecycle triggers derived from thesis revisions."""

from __future__ import annotations

from enum import Enum

from .diff import ThesisDiff
from .schemas import ThesisStatus


class ThesisTrigger(str, Enum):
    RATING_DOWNGRADE = "rating_downgrade"
    RATING_UPGRADE = "rating_upgrade"
    EVIDENCE_SHIFT = "evidence_shift"


def evaluate_triggers(diff: ThesisDiff) -> list[ThesisTrigger]:
    triggers = []
    if diff.rating_delta < 0:
        triggers.append(ThesisTrigger.RATING_DOWNGRADE)
    elif diff.rating_delta > 0:
        triggers.append(ThesisTrigger.RATING_UPGRADE)
    if diff.evidence_added or diff.evidence_removed:
        triggers.append(ThesisTrigger.EVIDENCE_SHIFT)
    return triggers


def apply_invalidation_status(triggered: bool, status: ThesisStatus) -> ThesisStatus:
    """Promote an explicit invalidation flag without overriding a closed thesis."""
    if triggered and status is not ThesisStatus.CLOSED:
        return ThesisStatus.INVALIDATED
    return status
