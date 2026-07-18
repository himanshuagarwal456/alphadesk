"""Atomic JSON persistence for immutable evidence snapshots."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schemas import Evidence


class EvidenceStore:
    """Persist one deduplicated evidence snapshot per completed run."""

    def __init__(self, directory: str | Path):
        self._directory = Path(directory).expanduser()

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(text, encoding="utf-8")
        os.replace(temporary, path)

    @staticmethod
    def _deduplicate(evidence: list[Evidence]) -> list[Evidence]:
        by_id = {item.id: item for item in evidence}
        return [by_id[item_id] for item_id in sorted(by_id)]

    def path_for(self, trade_date: str) -> Path:
        """Return the deterministic sidecar path for ``trade_date``."""
        return self._directory / f"evidence_{trade_date}.json"

    def save_snapshot(self, trade_date: str, evidence: list[Evidence]) -> Path:
        """Atomically save a byte-stable, ID-deduplicated evidence snapshot."""
        payload = [item.model_dump(mode="json") for item in self._deduplicate(evidence)]
        text = json.dumps(payload, indent=2, sort_keys=True)
        path = self.path_for(trade_date)
        self._atomic_write(path, text)
        return path

    def load_snapshot(self, trade_date: str) -> list[Evidence]:
        """Load a snapshot, returning an empty list when no sidecar exists."""
        path = self.path_for(trade_date)
        if not path.exists():
            return []
        data = json.loads(path.read_text(encoding="utf-8"))
        return [Evidence.model_validate(item) for item in data]
