"""Shared browser/export payload for every declarative chart."""

from __future__ import annotations

import json

import pandas as pd
import plotly.graph_objects as go

from .chart_registry import register_builtin_charts
from .chart_spec import ChartSpec
from .chart_validator import validate_declarative_spec


def render_chart(spec: ChartSpec, data: pd.DataFrame, *, theme: str = "light") -> dict:
    """Validate and render a chart with unified interaction and table metadata."""
    validation = validate_declarative_spec(spec, data)
    if not validation.valid:
        return {
            "status": "empty" if data.empty else "error",
            "message": spec.empty_state if data.empty else "; ".join(validation.errors),
            "spec": spec.model_dump(mode="json"),
        }
    figure: go.Figure = register_builtin_charts().render(spec, data, theme=theme)
    interactions = spec.interactions
    config = {
        "responsive": True,
        "displaylogo": False,
        "scrollZoom": interactions.zoom,
        "displayModeBar": interactions.fullscreen or interactions.zoom,
        "modeBarButtonsToRemove": [] if interactions.fullscreen else ["toImage"],
    }
    actions = [
        name
        for name, enabled in (
            ("fullscreen", interactions.fullscreen),
            ("data_table", interactions.data_table),
            ("save_to_research", interactions.save_to_research),
            ("attach_to_journal", interactions.attach_to_journal),
            ("attach_to_thesis", interactions.attach_to_thesis),
        )
        if enabled
    ]
    return {
        "status": "ready",
        "figure": json.loads(figure.to_json()),
        "config": config,
        "actions": actions,
        "table": data.where(pd.notna(data), None).to_dict(orient="records")
        if interactions.data_table
        else None,
        "accessibility": {
            "label": spec.description or spec.title or f"{spec.chart_type.value} chart",
            "table_available": interactions.data_table,
        },
        "spec": spec.model_dump(mode="json"),
    }
