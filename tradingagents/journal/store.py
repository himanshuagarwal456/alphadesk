"""Atomic append-only JSON persistence for decision entries."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schemas import DecisionJournalEntry


class DecisionJournalStore:
    def __init__(self, base_dir: str | Path):
        self._path = Path(base_dir).expanduser() / "entries.json"

    def load(self) -> list[DecisionJournalEntry]:
        if not self._path.exists():
            return []
        return [DecisionJournalEntry.model_validate(item) for item in json.loads(self._path.read_text())]

    def append(self, entry: DecisionJournalEntry) -> None:
        entries = {item.id: item for item in self.load()}
        entries[entry.id] = entry
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(".tmp")
        temporary.write_text(
            json.dumps(
                [item.model_dump(mode="json") for item in entries.values()],
                indent=2,
                sort_keys=True,
            )
        )
        os.replace(temporary, self._path)
