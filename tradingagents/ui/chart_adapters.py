"""Domain-to-chart data adapters.

Adapters normalize data only.  They never fetch data and never choose visual
styles, which keeps renderers reusable across cards, reports, and product views.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd


def normalize_records(
    records: Iterable[Mapping[str, Any]] | pd.DataFrame,
    *,
    required_fields: Iterable[str] = (),
    date_fields: Iterable[str] = (),
) -> pd.DataFrame:
    frame = records.copy() if isinstance(records, pd.DataFrame) else pd.DataFrame(records)
    missing = [field for field in required_fields if field not in frame.columns]
    if missing:
        raise ValueError(f"missing data fields: {', '.join(missing)}")
    for field in date_fields:
        if field in frame:
            frame[field] = pd.to_datetime(frame[field], errors="coerce")
    return frame


def time_series(records, *, date_field: str, value_fields: Iterable[str]) -> pd.DataFrame:
    fields = list(value_fields)
    frame = normalize_records(
        records, required_fields=[date_field, *fields], date_fields=[date_field]
    )
    frame = frame.dropna(subset=[date_field]).sort_values(date_field)
    for field in fields:
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    return frame[[date_field, *fields]]


def categories(records, *, category_field: str, value_fields: Iterable[str]) -> pd.DataFrame:
    fields = list(value_fields)
    frame = normalize_records(records, required_fields=[category_field, *fields])
    for field in fields:
        frame[field] = pd.to_numeric(frame[field], errors="coerce")
    return frame[[category_field, *fields]]


def correlation_matrix(
    records: pd.DataFrame | Iterable[Mapping[str, Any]], *, fields: Iterable[str] | None = None
) -> pd.DataFrame:
    frame = normalize_records(records)
    selected = list(fields) if fields is not None else list(frame.select_dtypes("number").columns)
    if len(selected) < 2:
        raise ValueError("correlation matrix needs at least two numeric fields")
    return frame[selected].apply(pd.to_numeric, errors="coerce").corr()


def portfolio_allocation(positions: Iterable[Mapping[str, Any]]) -> pd.DataFrame:
    frame = normalize_records(positions)
    if "weight" not in frame and {"quantity", "price"}.issubset(frame.columns):
        values = pd.to_numeric(frame["quantity"], errors="coerce") * pd.to_numeric(
            frame["price"], errors="coerce"
        )
        total = values.sum()
        frame["weight"] = values / total if total else 0.0
    return categories(frame, category_field="symbol", value_fields=["weight"])


def drawdown_series(records, *, date_field: str, value_field: str) -> pd.DataFrame:
    frame = time_series(records, date_field=date_field, value_fields=[value_field])
    values = frame[value_field]
    peaks = values.cummax()
    frame["drawdown"] = values.div(peaks).sub(1.0).where(peaks.ne(0), 0.0)
    return frame[[date_field, "drawdown"]]
