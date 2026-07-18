"""Validation for source data and deterministic chart specifications."""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from .chart_selector import select_chart_spec
from .chart_spec import ChartSpec, ChartTemplate
from .visualization_intent import VisualizationIntent


@dataclass(frozen=True)
class ValidationResult:
    """Result of validating a chart before it is serialized for the browser."""

    valid: bool
    errors: list[str] = field(default_factory=list)


def validate_chart_spec(
    spec: ChartSpec,
    intent: VisualizationIntent,
    data: pd.DataFrame | None = None,
) -> ValidationResult:
    """Validate supported template selection, inputs, and scenario semantics."""
    errors: list[str] = []
    selected = select_chart_spec(intent, units=spec.units)
    if spec.template is not selected.template:
        errors.append(
            f"template {spec.template.value!r} does not match "
            f"{intent.analytical_question.value!r}"
        )
    if data is not None:
        if data.empty:
            errors.append("chart data is empty")
        elif len(data) < spec.minimum_samples:
            errors.append(f"chart needs at least {spec.minimum_samples} samples")
        if not data.index.is_monotonic_increasing:
            errors.append("chart dates must be in chronological order")
    if (
        spec.template is ChartTemplate.SCENARIO_BAND
        and spec.target is not None
        and spec.stop is not None
        and spec.target <= spec.stop
    ):
        errors.append("scenario target must exceed stop")
    return ValidationResult(valid=not errors, errors=errors)
