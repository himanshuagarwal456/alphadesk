"""Central registry of supported visualization capabilities."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .chart_spec import ChartInteractions, ChartSpec, ChartType


@dataclass(frozen=True)
class ChartDefinition:
    renderer: Callable
    required_fields: tuple[str, ...]
    data_shapes: tuple[str, ...]
    config_schema: dict = field(default_factory=dict)
    interactions: ChartInteractions = field(default_factory=ChartInteractions)
    default_format: str = "auto"
    accessibility: str = "Chart includes a descriptive label and data-table alternative."


class ChartRegistry:
    def __init__(self) -> None:
        self._definitions: dict[ChartType, ChartDefinition] = {}

    def register(self, chart_type: ChartType, definition: ChartDefinition) -> None:
        if chart_type in self._definitions:
            raise ValueError(f"chart type {chart_type.value!r} is already registered")
        self._definitions[chart_type] = definition

    def get(self, chart_type: ChartType | str) -> ChartDefinition:
        key = chart_type if isinstance(chart_type, ChartType) else ChartType(chart_type)
        try:
            return self._definitions[key]
        except KeyError as exc:
            raise KeyError(f"unregistered chart type: {key.value}") from exc

    def supported_types(self) -> tuple[ChartType, ...]:
        return tuple(self._definitions)

    def validate_fields(self, spec: ChartSpec) -> list[str]:
        definition = self.get(spec.chart_type)
        return [name for name in definition.required_fields if not getattr(spec, name)]

    def render(self, spec: ChartSpec, data, **kwargs):
        missing = self.validate_fields(spec)
        if missing:
            raise ValueError(f"missing required chart fields: {', '.join(missing)}")
        return self.get(spec.chart_type).renderer(data, spec=spec, **kwargs)


registry = ChartRegistry()


def register_builtin_charts() -> ChartRegistry:
    """Idempotently install built-ins without introducing import cycles."""
    if registry.supported_types():
        return registry
    from . import charts

    definitions = {
        ChartType.LINE: (charts.time_series_chart, ("x_field", "y_fields"), ("timeseries",)),
        ChartType.AREA: (charts.time_series_chart, ("x_field", "y_fields"), ("timeseries",)),
        ChartType.BAR: (charts.bar_chart, ("x_field", "y_fields"), ("categorical", "timeseries")),
        ChartType.STACKED_BAR: (charts.bar_chart, ("x_field", "y_fields"), ("categorical", "timeseries")),
        ChartType.DONUT: (charts.donut_chart, ("category_field", "y_fields"), ("categorical",)),
        ChartType.WATERFALL: (charts.waterfall_chart, ("x_field", "y_fields"), ("categorical",)),
        ChartType.HEATMAP: (charts.correlation_heatmap, (), ("matrix", "wide")),
        ChartType.SCATTER: (charts.risk_return_scatter, ("x_field", "y_fields"), ("points",)),
        ChartType.DRAWDOWN: (charts.drawdown_chart, ("x_field", "y_fields"), ("timeseries",)),
        ChartType.EVENT_TIMELINE: (charts.event_annotated_price_chart, ("x_field", "y_fields"), ("timeseries",)),
    }
    for kind, (renderer, fields, shapes) in definitions.items():
        registry.register(kind, ChartDefinition(renderer, fields, shapes))
    return registry
