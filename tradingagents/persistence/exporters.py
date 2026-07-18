"""Export durable DB records back to the legacy JSON / Markdown file layouts.

Existing CLI consumers (`AnalysisRunStore`, evidence sidecars, thesis dirs)
keep working during the migration by writing the same filenames the graph and
feed already understand.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

from tradingagents.domain.schemas import AnalysisRun
from tradingagents.evidence.schemas import Evidence
from tradingagents.journal.schemas import DecisionJournalEntry
from tradingagents.thesis.schemas import LivingThesis, ThesisSnapshot


class CompatibilityExporter:
    """Write domain objects into the historical on-disk shapes."""

    def __init__(self, results_dir: str | Path):
        self.results_dir = Path(results_dir).expanduser()

    def export_analysis_run(self, run: AnalysisRun, *, symbol: str | None = None) -> Path:
        ticker = (symbol or run.symbol).upper()
        directory = self.results_dir / ticker / run.trade_date
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"analysis_run_{run.trade_date}.json"
        _atomic_json(path, run.model_dump(mode="json"))
        return path

    def export_evidence(
        self,
        evidence: list[Evidence],
        *,
        symbol: str,
        trade_date: str,
    ) -> Path:
        directory = self.results_dir / symbol.upper() / trade_date
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f"evidence_{trade_date}.json"
        _atomic_json(path, [item.model_dump(mode="json") for item in evidence])
        return path

    def export_thesis(
        self,
        thesis: LivingThesis,
        snapshot: ThesisSnapshot | None = None,
        *,
        thesis_dir: str | Path,
    ) -> Path:
        root = Path(thesis_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{thesis.symbol.upper()}.json"
        _atomic_json(path, thesis.model_dump(mode="json"))
        if snapshot is not None:
            snap_path = root / "snapshots" / f"{snapshot.snapshot_id}.json"
            snap_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_json(snap_path, snapshot.model_dump(mode="json"))
        return path

    def export_journal_entry(
        self,
        entry: DecisionJournalEntry,
        *,
        journal_dir: str | Path,
    ) -> Path:
        root = Path(journal_dir).expanduser()
        root.mkdir(parents=True, exist_ok=True)
        path = root / f"{entry.id}.json"
        _atomic_json(path, entry.model_dump(mode="json"))
        return path

    def export_run_markdown(
        self,
        *,
        symbol: str,
        trade_date: str,
        sections: dict[str, str],
    ) -> Path:
        """Write the classic per-section Markdown reports used by the CLI."""
        directory = self.results_dir / symbol.upper() / trade_date / "reports"
        directory.mkdir(parents=True, exist_ok=True)
        written = directory
        for name, body in sections.items():
            path = directory / f"{name}.md"
            temporary = path.with_suffix(path.suffix + ".tmp")
            temporary.write_text(body, encoding="utf-8")
            os.replace(temporary, path)
        return written


def _atomic_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    os.replace(temporary, path)
