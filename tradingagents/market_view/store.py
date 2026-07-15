"""Deterministic, date-aware persistence for the market view.

Mirrors :class:`tradingagents.portfolio.store.PortfolioStore`: a ``current.json``
holding the latest view plus dated copies under ``snapshots/`` keyed by
``as_of``. Persisting the view (not just the book) is what lets a backtest
replay a date with the exact top-down lens that was in force then, so lifecycle
decisions are reproducible end to end.

All writes are atomic and serialise with sorted keys for byte-stable output.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schemas import MarketView


class MarketViewStore:
    """JSON-backed store for the current market view and dated snapshots."""

    _CURRENT_FILE = "current.json"
    _SNAPSHOT_DIR = "snapshots"

    def __init__(self, base_dir: str | Path):
        """Args:
        base_dir: Directory for ``current.json`` and ``snapshots/``. Created on
            first write. Typically ``~/.tradingagents/market_view``.
        """
        self._base = Path(base_dir).expanduser()

    @property
    def current_path(self) -> Path:
        return self._base / self._CURRENT_FILE

    def _snapshot_path(self, as_of: str) -> Path:
        return self._base / self._SNAPSHOT_DIR / f"{as_of}.json"

    @staticmethod
    def _dump(view: MarketView) -> str:
        return json.dumps(view.model_dump(mode="json"), indent=2, sort_keys=True)

    @staticmethod
    def _atomic_write(path: Path, text: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(text, encoding="utf-8")
        os.replace(tmp, path)

    def save(self, view: MarketView) -> Path:
        """Persist ``view`` as the current market view. Returns the written path."""
        self._atomic_write(self.current_path, self._dump(view))
        return self.current_path

    def load(self) -> MarketView | None:
        """Load the current view, or None when nothing has been saved yet."""
        if not self.current_path.exists():
            return None
        return MarketView.model_validate_json(self.current_path.read_text(encoding="utf-8"))

    def snapshot(self, view: MarketView) -> Path:
        """Persist a dated copy keyed by ``view.as_of``.

        Raises:
            ValueError: ``view.as_of`` is unset (a snapshot needs a date).
        """
        if not view.as_of:
            raise ValueError("cannot snapshot a market view without an 'as_of' date")
        path = self._snapshot_path(view.as_of)
        self._atomic_write(path, self._dump(view))
        return path

    def load_snapshot(self, as_of: str) -> MarketView | None:
        """Load the snapshot for ``as_of``, or None when absent."""
        path = self._snapshot_path(as_of)
        if not path.exists():
            return None
        return MarketView.model_validate_json(path.read_text(encoding="utf-8"))

    def snapshot_dates(self) -> list[str]:
        """All snapshot dates present, ascending (chronological replay order)."""
        snap_dir = self._base / self._SNAPSHOT_DIR
        if not snap_dir.exists():
            return []
        return sorted(p.stem for p in snap_dir.glob("*.json"))
