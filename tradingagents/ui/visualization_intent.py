"""Typed analytical intent that precedes deterministic chart selection."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class AnalyticalQuestion(str, Enum):
    """Questions supported by the first chart-governance slice."""

    TREND = "trend"
    RISK = "risk"
    SCENARIO = "scenario"


class VisualizationIntent(BaseModel):
    """Describe the question and data before a chart template is selected."""

    analytical_question: AnalyticalQuestion
    entities: list[str] = Field(default_factory=list)
    metrics: list[str] = Field(default_factory=list)
    time_window: str | None = None
    explanation: str | None = None
