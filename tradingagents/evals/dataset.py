"""Versioned evaluation securities dataset."""

from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

DATA_DIR = Path(__file__).resolve().parent / "data"
DEFAULT_DATASET = DATA_DIR / "securities_v1.json"


class EvalCase(BaseModel):
    """One named security scenario in the evaluation set."""

    symbol: str
    name: str
    cap_bucket: str = Field(description="large | mid | small")
    profitable: bool
    news_intensity: str = Field(description="high | low")
    regime: str = Field(description="bull | bear | mixed")
    scenario: str = Field(
        description="earnings | filing | sparse_data | normal | contested"
    )
    trade_date: str
    notes: str = ""


def load_eval_dataset(path: str | Path | None = None) -> list[EvalCase]:
    target = Path(path) if path else DEFAULT_DATASET
    payload = json.loads(target.read_text(encoding="utf-8"))
    version = payload.get("version")
    if version != "evals-v1":
        raise ValueError(f"unsupported eval dataset version: {version!r}")
    return [EvalCase.model_validate(item) for item in payload["cases"]]
