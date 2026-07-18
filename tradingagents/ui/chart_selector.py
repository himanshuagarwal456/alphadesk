"""Deterministic mapping from analytical question to feed chart template."""

from __future__ import annotations

from .chart_spec import ChartSpec, ChartTemplate
from .visualization_intent import AnalyticalQuestion, VisualizationIntent

_TEMPLATES = {
    AnalyticalQuestion.TREND: ChartTemplate.CANDLESTICK,
    AnalyticalQuestion.RISK: ChartTemplate.GAUGE,
    AnalyticalQuestion.SCENARIO: ChartTemplate.SCENARIO_BAND,
}


def select_chart_spec(intent: VisualizationIntent, *, units: str = "") -> ChartSpec:
    """Choose the only supported chart template for a typed analytical question."""
    return ChartSpec(
        template=_TEMPLATES[intent.analytical_question],
        analytical_question=intent.analytical_question,
        units=units,
        minimum_samples=2 if intent.analytical_question is not AnalyticalQuestion.RISK else 1,
    )
