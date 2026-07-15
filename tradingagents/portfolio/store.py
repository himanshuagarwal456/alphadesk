"""Deterministic, date-aware persistence for the portfolio book.

Two responsibilities:

1. **Current book** — ``save`` / ``load`` the latest ``Portfolio`` as
   ``book.json``. This is what the agent graph reads to know what we hold.
2. **Dated snapshots** — ``snapshot`` / ``load_snapshot`` / ``snapshot_dates``
   persist a copy keyed by ``as_of`` date under ``snapshots/``. This is the
   foundation for a replay clock: a backtest can step through dates and load the
   exact book as of each one, so lifecycle logic (initiate / manage / exit) can
   be validated deterministically instead of against a moving live account.

All writes are atomic (temp file + ``os.replace``) and serialise with sorted
keys, so the on-disk form is byte-stable for identical input — a prerequisite
for reproducible runs and clean diffs.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schemas import Portfolio


class PortfolioStore:
    """JSON-backed store for the current book and dated snapshots."""

    _BOOK_FILE = "book.json"
    _SNAPSHOT_DIR = "snapshots"

    def __init__(self, base_dir: str | Path):
        """Args:
        base_dir: Directory to hold ``book.json`` and ``snapshots/``. Created
            on first write. Typically ``~/.tradingagents/portfolio``.
        """
        self._base = Path(base_dir).expanduser()

    # --- Paths ---

    @property
    def book_path(self) -> Path:
        return self._base / self._BOOK_FILE

    def _snapshot_path(self, as_of: str) -> Path:
        return self._base / self._SNAPSHOT_DIR / f"{as_of}.json"

    # --- Serialisation helpers ---

    @staticmethod
    def _dump(portfolio: Portfolio) -> str:
        # sort_keys for byte-stable output; the schema already symbol-sorts
        # positions, so identical books serialise identically.
        return json.dumps(
            portfolio.model_dump(mode="json"),
            indent=2,
            sort_keys=True,
        )

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    # --- Current book ---

    def save(self, portfolio: Portfolio) -> Path:
        """Persist ``portfolio`` as the current book. Returns the written path."""
        self._atomic_write(self.book_path, self._dump(portfolio))
        return self.book_path

    def load(self) -> Portfolio | None:
        """Load the current book, or None when nothing has been saved yet."""
        if not self.book_path.exists():
            return None
        data = json.loads(self.book_path.read_text(encoding="utf-8"))
        return Portfolio.model_validate(data)

    # --- Dated snapshots (replay foundation) ---

    def snapshot(self, portfolio: Portfolio) -> Path:
        """Persist a dated copy keyed by ``portfolio.as_of``.

        Raises:
            ValueError: ``portfolio.as_of`` is unset (a snapshot needs a date).
        """
        if not portfolio.as_of:
            raise ValueError("cannot snapshot a portfolio without an 'as_of' date")
        path = self._snapshot_path(portfolio.as_of)
        self._atomic_write(path, self._dump(portfolio))
        return path

    def load_snapshot(self, as_of: str) -> Portfolio | None:
        """Load the snapshot for ``as_of``, or None when absent."""
        path = self._snapshot_path(as_of)
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        return Portfolio.model_validate(data)

    def snapshot_dates(self) -> list[str]:
        """All snapshot dates present, ascending (chronological replay order)."""
        snap_dir = self._base / self._SNAPSHOT_DIR
        if not snap_dir.exists():
            return []
        return sorted(p.stem for p in snap_dir.glob("*.json"))
