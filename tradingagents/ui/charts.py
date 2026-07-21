"""Plotly figure builders for feed cards.

Pure and self-contained: every function takes plain data (a DataFrame, a number,
a string) and returns a ``plotly.graph_objects.Figure``. No network, no globals,
so they unit-test by asserting on ``fig.data``. Figures are serialised to dicts
by the deck builder and rendered client-side by Plotly.js, so nothing here
depends on the rendering target.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from . import indicators
from .chart_spec import ChartSpec, ChartType
from .visualization_tokens import theme_tokens

# Rating -> numeric position for the verdict dial (Sell..Buy).
_RATING_SCALE = {
    "sell": 0,
    "underweight": 1,
    "hold": 2,
    "overweight": 3,
    "buy": 4,
}
_RATING_COLOR = {
    "sell": "#d62728",
    "underweight": "#ff7f0e",
    "hold": "#7f7f7f",
    "overweight": "#2ca02c",
    "buy": "#1a9850",
}

_DARK = "#0e1117"
_PAPER = "#f7f4ec"
_INK = "#1a221c"
_MUTED = "#5c6a60"
_PLOT = "#fffdf8"


def _col(df: pd.DataFrame, name: str) -> pd.Series:
    """Fetch a column case-insensitively (yfinance uses Title-case)."""
    for c in df.columns:
        if c.lower() == name.lower():
            return df[c]
    raise KeyError(f"column {name!r} not found in {list(df.columns)}")


def close_series(df: pd.DataFrame) -> pd.Series:
    """Return the close series using the same case-insensitive lookup as charts."""
    return _col(df, "close")


def _base_layout(fig: go.Figure, title: str = "") -> go.Figure:
    fig.update_layout(
        title={"text": title, "font": {"color": _INK, "size": 14}} if title else None,
        template="plotly_white",
        paper_bgcolor=_PAPER,
        plot_bgcolor=_PLOT,
        font={"color": _INK},
        margin={"l": 8, "r": 8, "t": 36 if title else 8, "b": 8},
        showlegend=False,
        xaxis_rangeslider_visible=False,
    )
    return fig


def apply_chart_layout(fig: go.Figure, spec: ChartSpec, *, theme: str = "light") -> go.Figure:
    """Apply the common title, axes, legend, tooltip, and source treatment."""
    token = theme_tokens(theme)
    source = spec.source_metadata
    caption = ""
    if source:
        caption = " · ".join(x for x in (source.provider, source.as_of) if x)
    fig.update_layout(
        title={"text": spec.title, "subtitle": {"text": spec.subtitle}, "font": {"family": token["title_family"]}},
        template="plotly_dark" if theme == "dark" else "plotly_white",
        paper_bgcolor=token["paper"], plot_bgcolor=token["plot"],
        font={"family": token["font_family"], "color": token["ink"]},
        colorway=token["series"], height=spec.config.get("height", token["chart_height"]),
        margin={"l": 48, "r": 24, "t": 68 if spec.subtitle else 52, "b": 52},
        legend={"orientation": "h", "y": -0.16}, hovermode="x unified",
        meta={"chart_id": spec.id, "description": spec.description, "source": caption,
              "empty_state": spec.empty_state, "interactions": spec.interactions.model_dump()},
    )
    formats = {
        "percent": ".1%",
        "currency": "$,.2f",
        "currency_compact": "$.3s",
        "integer": ",.0f",
        "decimal_2": ".2f",
    }
    fig.update_xaxes(gridcolor=token["grid"], showgrid=True, tickformat=spec.config.get("date_format"))
    fig.update_yaxes(
        gridcolor=token["grid"], showgrid=True,
        tickformat=formats.get(spec.number_format),
    )
    return fig


def _frame(data) -> pd.DataFrame:
    return data.copy() if isinstance(data, pd.DataFrame) else pd.DataFrame(data)


def time_series_chart(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    frame = _frame(data)
    fig = go.Figure()
    for field in spec.y_fields:
        fill = "tozeroy" if spec.chart_type is ChartType.AREA else None
        line = {"dash": "dash"} if spec.benchmark and field == spec.benchmark.field else {}
        fig.add_trace(go.Scatter(x=frame[spec.x_field], y=frame[field], mode="lines", name=field,
                                 fill=fill, line=line, connectgaps=False))
    for annotation in spec.annotations:
        if annotation.x is not None:
            fig.add_vline(x=annotation.x, line_dash="dot", annotation_text=annotation.label)
    return apply_chart_layout(fig, spec, theme=theme)


def bar_chart(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    frame = _frame(data)
    fig = go.Figure()
    for field in spec.y_fields:
        values = frame[field]
        colors = None
        if spec.config.get("semantic_colors"):
            token = theme_tokens(theme)
            colors = [token["positive"] if value >= 0 else token["negative"] for value in values]
        fig.add_trace(go.Bar(x=frame[spec.x_field], y=values, name=field, marker_color=colors))
    fig.update_layout(barmode="stack" if spec.chart_type is ChartType.STACKED_BAR else "group")
    return apply_chart_layout(fig, spec, theme=theme)


def donut_chart(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    frame = _frame(data)
    fig = go.Figure(go.Pie(labels=frame[spec.category_field], values=frame[spec.y_fields[0]],
                           hole=0.58, sort=False, textinfo="label+percent"))
    return apply_chart_layout(fig, spec, theme=theme)


def waterfall_chart(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    frame = _frame(data)
    token = theme_tokens(theme)
    measure = spec.config.get("measure") or ["relative"] * len(frame)
    fig = go.Figure(go.Waterfall(
        x=frame[spec.x_field], y=frame[spec.y_fields[0]], measure=measure,
        increasing={"marker": {"color": token["positive"]}},
        decreasing={"marker": {"color": token["negative"]}},
        totals={"marker": {"color": token["benchmark"]}},
    ))
    return apply_chart_layout(fig, spec, theme=theme)


def correlation_heatmap(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    frame = _frame(data)
    matrix = frame if frame.index.equals(pd.Index(frame.columns)) else frame.corr(numeric_only=True)
    fig = go.Figure(go.Heatmap(z=matrix.values, x=list(matrix.columns), y=list(matrix.index),
                               zmin=-1, zmax=1, zmid=0, colorscale="RdBu", reversescale=True,
                               text=matrix.round(2).astype(str).values, texttemplate="%{text}"))
    return apply_chart_layout(fig, spec, theme=theme)


def risk_return_scatter(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    frame = _frame(data)
    y_field = spec.y_fields[0]
    label_field = spec.category_field
    size_field = spec.config.get("size_field")
    fig = go.Figure(go.Scatter(
        x=frame[spec.x_field], y=frame[y_field], mode="markers+text" if label_field else "markers",
        text=frame[label_field] if label_field else None, textposition="top center",
        marker={"size": frame[size_field] if size_field else theme_tokens(theme)["point_size"], "sizemode": "area"},
        name=y_field,
    ))
    return apply_chart_layout(fig, spec, theme=theme)


def drawdown_chart(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    frame = _frame(data)
    values = frame[spec.y_fields[0]]
    if spec.config.get("values_are_drawdown", False):
        drawdown = values
    else:
        drawdown = values.div(values.cummax()).sub(1.0)
    fig = go.Figure(go.Scatter(x=frame[spec.x_field], y=drawdown, mode="lines", fill="tozeroy",
                               name="Drawdown", line={"color": theme_tokens(theme)["negative"]}))
    return apply_chart_layout(fig, spec, theme=theme)


def event_annotated_price_chart(data, *, spec: ChartSpec, theme: str = "light") -> go.Figure:
    return time_series_chart(data, spec=spec, theme=theme)


def price_chart(
    df: pd.DataFrame,
    *,
    title: str = "",
    sma_windows: tuple[int, ...] = (20, 50),
    bollinger: bool = False,
    levels: list[dict] | None = None,
) -> go.Figure:
    """Candlestick + volume with optional SMA/Bollinger overlays and price levels.

    ``levels`` is a list of ``{"label": str, "value": float, "color": str}`` that
    become horizontal reference lines (e.g. a target, a stop, a broken support) —
    this is how an agent's thesis gets *drawn on the chart*.
    """
    close = _col(df, "close")
    fig = make_subplots(
        rows=2, cols=1, shared_xaxes=True,
        row_heights=[0.78, 0.22], vertical_spacing=0.02,
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=_col(df, "open"), high=_col(df, "high"),
            low=_col(df, "low"), close=close, name="Price",
        ),
        row=1, col=1,
    )
    for window in sma_windows:
        fig.add_trace(
            go.Scatter(x=df.index, y=indicators.sma(close, window), mode="lines",
                       name=f"SMA{window}", line={"width": 1}),
            row=1, col=1,
        )
    if bollinger:
        bands = indicators.bollinger(close)
        for key, dash in (("upper", "dot"), ("lower", "dot")):
            fig.add_trace(
                go.Scatter(x=df.index, y=bands[key], mode="lines", name=f"BB {key}",
                           line={"width": 1, "dash": dash, "color": "#888"}),
                row=1, col=1,
            )
    try:
        volume = _col(df, "volume")
        fig.add_trace(
            go.Bar(x=df.index, y=volume, name="Volume", marker_color="#3b6"),
            row=2, col=1,
        )
    except KeyError:
        pass

    for level in levels or []:
        fig.add_hline(
            y=level["value"],
            line={"color": level.get("color", "#aaa"), "dash": "dash", "width": 1},
            annotation_text=level.get("label", ""), annotation_position="right",
            row=1, col=1,
        )
    return _base_layout(fig, title)


def scenario_bands(
    df: pd.DataFrame,
    *,
    entry: float | None = None,
    target: float | None = None,
    stop: float | None = None,
    title: str = "",
) -> go.Figure:
    """Close line with the bull target and bear stop drawn as a risk/reward band.

    This is the "the debate becomes a picture" card: bull target (green) and bear
    downside (red) framed around the current price.
    """
    close = _col(df, "close")
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=df.index, y=close, mode="lines", name="Close",
                             line={"color": "#4c9be8", "width": 2}))
    if target is not None and stop is not None:
        fig.add_hrect(y0=stop, y1=target, fillcolor="rgba(46,160,44,0.08)", line_width=0)
    for value, label, color in (
        (target, "Bull target", "#2ca02c"),
        (entry, "Now", "#cccccc"),
        (stop, "Bear risk", "#d62728"),
    ):
        if value is not None:
            fig.add_hline(y=value, line={"color": color, "dash": "dash", "width": 1},
                          annotation_text=label, annotation_position="right")
    return _base_layout(fig, title)


def sentiment_gauge(score: float, band: str = "") -> go.Figure:
    """0–10 sentiment gauge (0 = max bearish, 10 = max bullish)."""
    score = max(0.0, min(10.0, float(score)))
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=score,
        title={"text": band or "Sentiment"},
        gauge={
            "axis": {"range": [0, 10]},
            "bar": {"color": "#4c9be8"},
            "steps": [
                {"range": [0, 3.4], "color": "#d62728"},
                {"range": [3.4, 4.5], "color": "#ff7f0e"},
                {"range": [4.5, 5.5], "color": "#7f7f7f"},
                {"range": [5.5, 6.5], "color": "#9acd32"},
                {"range": [6.5, 10], "color": "#2ca02c"},
            ],
        },
    ))
    return _base_layout(fig)


def rating_dial(rating: str) -> go.Figure:
    """Verdict dial mapping Sell..Buy onto a 0–4 gauge."""
    key = (rating or "").strip().lower()
    value = _RATING_SCALE.get(key, 2)
    color = _RATING_COLOR.get(key, "#7f7f7f")
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=value,
        number={"valueformat": ".0f", "suffix": f"  {rating}".rstrip()},
        title={"text": "Verdict"},
        gauge={
            "axis": {
                "range": [0, 4],
                "tickmode": "array",
                "tickvals": [0, 1, 2, 3, 4],
                "ticktext": ["Sell", "UW", "Hold", "OW", "Buy"],
            },
            "bar": {"color": color},
        },
    ))
    return _base_layout(fig)


def book_impact_bars(
    rows: list[dict],
    *,
    title: str = "Affected names",
) -> go.Figure:
    """Horizontal bars of portfolio weight, colored by rating.

    Each row: ``{"symbol": str, "weight": float|None, "rating": str|None}``.
    """
    if not rows:
        fig = go.Figure()
        return _base_layout(fig, title)

    symbols = [str(r.get("symbol") or "?").upper() for r in rows]
    weights = [float(r.get("weight") or 0.0) * 100.0 for r in rows]
    colors = [
        _RATING_COLOR.get(str(r.get("rating") or "").strip().lower(), "#7f7f7f")
        for r in rows
    ]
    labels = [
        f"{(r.get('rating') or '—')} · {float(r.get('weight') or 0.0) * 100:.0f}%"
        for r in rows
    ]
    fig = go.Figure(
        go.Bar(
            x=weights,
            y=symbols,
            orientation="h",
            marker_color=colors,
            text=labels,
            textposition="auto",
            hovertemplate="%{y}<br>%{x:.1f}% of book<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="% of book",
        yaxis={"autorange": "reversed"},
    )
    return _base_layout(fig, title)
