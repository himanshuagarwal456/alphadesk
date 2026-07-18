"""Atomic persistence for current living theses and dated revisions."""

from __future__ import annotations

import json
import os
from pathlib import Path

from .schemas import LivingThesis, ThesisSnapshot


class LivingThesisStore:
    def __init__(self, base_dir: str | Path):
        self._base = Path(base_dir).expanduser()

    def _head_path(self, symbol: str) -> Path:
        return self._base / f"{symbol.upper()}.json"

    def _snapshot_path(self, symbol: str, as_of: str) -> Path:
        return self._base / "snapshots" / f"{symbol.upper()}_{as_of}.json"

    @staticmethod
    def _write(path: Path, model) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + ".tmp")
        temporary.write_text(
            json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        os.replace(temporary, path)
        return path

    def load(self, symbol: str) -> LivingThesis | None:
        path = self._head_path(symbol)
        return LivingThesis.model_validate_json(path.read_text()) if path.exists() else None

    def save(self, thesis: LivingThesis) -> Path:
        return self._write(self._head_path(thesis.symbol), thesis)

    def snapshot(self, snapshot: ThesisSnapshot) -> Path:
        return self._write(self._snapshot_path(snapshot.symbol, snapshot.as_of), snapshot)

    def load_snapshot(self, symbol: str, as_of: str) -> ThesisSnapshot | None:
        path = self._snapshot_path(symbol, as_of)
        return ThesisSnapshot.model_validate_json(path.read_text()) if path.exists() else None

    def snapshot_dates(self, symbol: str) -> list[str]:
        directory = self._base / "snapshots"
        if not directory.exists():
            return []
        prefix = f"{symbol.upper()}_"
        return sorted(path.stem.removeprefix(prefix) for path in directory.glob(f"{prefix}*.json"))

    def upsert_run(self, thesis: LivingThesis, snapshot: ThesisSnapshot) -> None:
        self.snapshot(snapshot)
        self.save(thesis)

    # --- Proposed revisions (audit history, including rejected ones) ---

    def _proposal_path(self, symbol: str, proposal_id: str) -> Path:
        return self._base / "proposals" / f"{symbol.upper()}_{proposal_id}.json"

    def save_proposal(self, proposal) -> Path:
        return self._write(self._proposal_path(proposal.symbol, proposal.id), proposal)

    def load_proposals(self, symbol: str) -> list:
        from .workflow import ProposedRevision

        directory = self._base / "proposals"
        if not directory.exists():
            return []
        prefix = f"{symbol.upper()}_"
        return sorted(
            (
                ProposedRevision.model_validate_json(path.read_text())
                for path in directory.glob(f"{prefix}*.json")
            ),
            key=lambda item: item.created_at,
        )
