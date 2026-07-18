"""Atomic JSON persistence for analysis-run records."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schemas import AnalysisRun


class AnalysisRunStore:
    """One JSON record per (symbol, trade_date) run, next to the run logs."""

    def __init__(self, directory: str | Path):
        self._directory = Path(directory).expanduser()

    def path_for(self, trade_date: str) -> Path:
        return self._directory / f"analysis_run_{trade_date}.json"

    def save(self, run: AnalysisRun) -> Path:
        path = self.path_for(run.trade_date)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(run.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return path

    def load(self, trade_date: str) -> AnalysisRun | None:
        path = self.path_for(trade_date)
        if not path.exists():
            return None
        return AnalysisRun.model_validate_json(path.read_text(encoding="utf-8"))
