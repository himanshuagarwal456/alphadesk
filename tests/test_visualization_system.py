from __future__ import annotations

import pandas as pd
import pytest

from tradingagents.ui import chart_adapters, chart_wrappers, charts
from tradingagents.ui.chart_registry import register_builtin_charts
from tradingagents.ui.chart_runtime import render_chart
from tradingagents.ui.chart_spec import ChartAnnotation, ChartSpec, ChartType
from tradingagents.ui.chart_validator import validate_declarative_spec
from tradingagents.ui.visualization_tokens import theme_tokens


@pytest.fixture()
def series_data() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": pd.date_range("2026-01-01", periods=4),
            "portfolio": [100, 104, 102, 110],
            "benchmark": [100, 102, 103, 106],
        }
    )


def test_chart_spec_keeps_legacy_template_alias() -> None:
    spec = ChartSpec(chart_type=ChartType.LINE)
    assert spec.template is ChartType.LINE
    assert ChartSpec(template=ChartType.CANDLESTICK).chart_type is ChartType.CANDLESTICK


def test_registry_contains_initial_chart_types() -> None:
    supported = set(register_builtin_charts().supported_types())
    assert {
        ChartType.LINE, ChartType.AREA, ChartType.BAR, ChartType.STACKED_BAR,
        ChartType.DONUT, ChartType.WATERFALL, ChartType.HEATMAP,
        ChartType.SCATTER, ChartType.DRAWDOWN, ChartType.EVENT_TIMELINE,
    } <= supported


def test_time_series_adapter_sorts_and_coerces() -> None:
    result = chart_adapters.time_series(
        [{"when": "2026-02-01", "value": "2"}, {"when": "2026-01-01", "value": "1"}],
        date_field="when", value_fields=["value"],
    )
    assert result["value"].tolist() == [1, 2]
    assert pd.api.types.is_datetime64_any_dtype(result["when"])


def test_drawdown_adapter() -> None:
    result = chart_adapters.drawdown_series(
        [{"date": "2026-01-01", "value": 100}, {"date": "2026-01-02", "value": 80}],
        date_field="date", value_field="value",
    )
    assert result["drawdown"].tolist() == [0.0, pytest.approx(-0.2)]


def test_wrappers_are_declarative() -> None:
    performance = chart_wrappers.portfolio_performance()
    allocation = chart_wrappers.portfolio_allocation()
    assert performance.benchmark.field == "benchmark"
    assert performance.interactions.zoom
    assert allocation.chart_type is ChartType.DONUT


@pytest.mark.parametrize("theme", ["light", "dark", "unknown"])
def test_visualization_tokens(theme: str) -> None:
    tokens = theme_tokens(theme)
    assert tokens["positive"] != tokens["negative"]
    assert tokens["series"]


def test_line_area_and_event_renderers(series_data: pd.DataFrame) -> None:
    line = chart_wrappers.portfolio_performance()
    assert len(charts.time_series_chart(series_data, spec=line).data) == 2
    area = line.model_copy(update={"chart_type": ChartType.AREA, "template": ChartType.AREA})
    assert charts.time_series_chart(series_data, spec=area).data[0].fill == "tozeroy"
    event = ChartSpec(
        chart_type=ChartType.EVENT_TIMELINE, x_field="date", y_fields=["portfolio"],
        annotations=[ChartAnnotation(x="2026-01-02", label="Earnings")],
    )
    assert len(charts.event_annotated_price_chart(series_data, spec=event).layout.shapes) >= 1


def test_bar_stacked_donut_and_waterfall() -> None:
    frame = pd.DataFrame({"name": ["A", "B"], "one": [2, -1], "two": [1, 3]})
    bar = ChartSpec(chart_type=ChartType.BAR, x_field="name", y_fields=["one", "two"])
    assert charts.bar_chart(frame, spec=bar).layout.barmode == "group"
    stacked = bar.model_copy(update={"chart_type": ChartType.STACKED_BAR, "template": ChartType.STACKED_BAR})
    assert charts.bar_chart(frame, spec=stacked).layout.barmode == "stack"
    donut = ChartSpec(chart_type=ChartType.DONUT, category_field="name", y_fields=["one"])
    assert charts.donut_chart(frame, spec=donut).data[0].hole == 0.58
    waterfall = ChartSpec(chart_type=ChartType.WATERFALL, x_field="name", y_fields=["one"])
    assert charts.waterfall_chart(frame, spec=waterfall).data[0].type == "waterfall"


def test_heatmap_scatter_and_drawdown(series_data: pd.DataFrame) -> None:
    matrix = series_data[["portfolio", "benchmark"]].corr()
    heatmap = ChartSpec(chart_type=ChartType.HEATMAP)
    assert charts.correlation_heatmap(matrix, spec=heatmap).data[0].type == "heatmap"
    scatter_data = pd.DataFrame({"risk": [0.1, 0.2], "return": [0.05, 0.12], "symbol": ["A", "B"]})
    scatter = ChartSpec(chart_type=ChartType.SCATTER, x_field="risk", y_fields=["return"], category_field="symbol")
    assert list(charts.risk_return_scatter(scatter_data, spec=scatter).data[0].text) == ["A", "B"]
    drawdown = ChartSpec(chart_type=ChartType.DRAWDOWN, x_field="date", y_fields=["portfolio"])
    assert charts.drawdown_chart(series_data, spec=drawdown).data[0].fill == "tozeroy"


def test_declarative_validation(series_data: pd.DataFrame) -> None:
    good = chart_wrappers.portfolio_performance()
    assert validate_declarative_spec(good, series_data).valid
    bad = ChartSpec(chart_type=ChartType.LINE, x_field="missing", y_fields=["portfolio"])
    result = validate_declarative_spec(bad, series_data)
    assert not result.valid
    assert "missing" in result.errors[0]


def test_shared_runtime_includes_interactions_table_and_accessibility(series_data: pd.DataFrame) -> None:
    payload = render_chart(chart_wrappers.portfolio_performance(), series_data)
    assert payload["status"] == "ready"
    assert payload["config"]["responsive"]
    assert "fullscreen" in payload["actions"]
    assert payload["table"][0]["portfolio"] == 100
    assert payload["accessibility"]["table_available"]


def test_shared_runtime_has_consistent_empty_state() -> None:
    spec = chart_wrappers.portfolio_allocation()
    spec.empty_state = "No holdings yet."
    payload = render_chart(spec, pd.DataFrame())
    assert payload == {"status": "empty", "message": "No holdings yet.", "spec": spec.model_dump(mode="json")}
