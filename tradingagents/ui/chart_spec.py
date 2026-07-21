"""Declarative, renderer-independent chart contracts.

The legacy feed used ``template`` for three chart choices.  ``ChartSpec`` keeps
that field as a compatibility alias while making ``chart_type`` the canonical
name for new consumers.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, model_validator

from .visualization_intent import AnalyticalQuestion


class ChartType(str, Enum):
    LINE = "line"
    AREA = "area"
    BAR = "bar"
    STACKED_BAR = "stacked_bar"
    DONUT = "donut"
    SCATTER = "scatter"
    HEATMAP = "heatmap"
    TREEMAP = "treemap"
    WATERFALL = "waterfall"
    CANDLESTICK = "candlestick"
    DRAWDOWN = "drawdown"
    EVENT_TIMELINE = "event_timeline"
    GAUGE = "gauge"
    SCENARIO_BAND = "scenario_band"


# Public compatibility name used by the feed and third-party callers.
ChartTemplate = ChartType


class ChartAnnotation(BaseModel):
    x: Any | None = None
    y: float | None = None
    label: str
    description: str = ""
    kind: str = "event"


class BenchmarkSpec(BaseModel):
    field: str
    label: str = "Benchmark"


class ChartInteractions(BaseModel):
    hover_tooltip: bool = True
    legend_toggle: bool = True
    date_range: bool = False
    zoom: bool = False
    crosshair: bool = False
    fullscreen: bool = True
    data_table: bool = True
    save_to_research: bool = False
    attach_to_journal: bool = False
    attach_to_thesis: bool = False


class SourceMetadata(BaseModel):
    provider: str = ""
    source_url: str | None = None
    as_of: str | None = None
    retrieved_at: str | None = None


class ChartSpec(BaseModel):
    """What to show, independent of Plotly or any future renderer."""

    id: str = ""
    chart_type: ChartType | None = None
    # Deprecated input/output retained during incremental feed migration.
    template: ChartType | None = None
    title: str = ""
    subtitle: str = ""
    description: str = ""
    data_source: str = ""
    x_field: str | None = None
    y_fields: list[str] = Field(default_factory=list)
    category_field: str | None = None
    series: list[str] = Field(default_factory=list)
    number_format: str = "auto"
    time_granularity: str | None = None
    annotations: list[ChartAnnotation] = Field(default_factory=list)
    benchmark: BenchmarkSpec | None = None
    interactions: ChartInteractions = Field(default_factory=ChartInteractions)
    empty_state: str = "No data available for this chart."
    source_metadata: SourceMetadata | None = None
    analytical_question: AnalyticalQuestion | None = None
    units: str = ""
    minimum_samples: int = Field(default=1, ge=1)
    target: float | None = None
    stop: float | None = None
    validated: bool = False
    config: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _synchronize_type_alias(self) -> ChartSpec:
        selected = self.chart_type or self.template
        if selected is None:
            raise ValueError("chart_type is required")
        if (
            self.chart_type is not None
            and self.template is not None
            and self.chart_type is not self.template
        ):
            raise ValueError("chart_type and template must match")
        self.chart_type = selected
        self.template = selected
        return self
