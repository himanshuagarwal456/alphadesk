"""Typed chart specifications, separate from renderer-specific Plotly JSON."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .visualization_intent import AnalyticalQuestion


class ChartTemplate(str, Enum):
    """Chart templates supported by the current feed renderer."""

    CANDLESTICK = "candlestick"
    GAUGE = "gauge"
    SCENARIO_BAND = "scenario_band"


class ChartSpec(BaseModel):
    """Selection metadata and source-data assumptions for a rendered chart."""

    template: ChartTemplate
    analytical_question: AnalyticalQuestion
    units: str = ""
    minimum_samples: int = Field(default=1, ge=1)
    target: float | None = None
    stop: float | None = None
    validated: bool = False
