"""Shared AlphaDesk visualization design tokens."""

from __future__ import annotations

TOKENS = {
    "light": {
        "paper": "#f7f4ec",
        "plot": "#fffdf8",
        "ink": "#1a221c",
        "muted": "#5c6a60",
        "grid": "rgba(26,34,28,0.10)",
        "tooltip": "#fffdf8",
    },
    "dark": {
        "paper": "#0e1117",
        "plot": "#151a20",
        "ink": "#edf2ed",
        "muted": "#a6b0a8",
        "grid": "rgba(237,242,237,0.12)",
        "tooltip": "#20262d",
    },
    "series": ["#315c55", "#657c75", "#8b7e6a", "#536779", "#92745f", "#7c7087"],
    "positive": "#287a5b",
    "negative": "#b44c43",
    "benchmark": "#81735d",
    "selected": "#0f6b5c",
    "muted_series": "#aeb5af",
    "warning": "#a56b2b",
    "risk": "#8f3d38",
    "font_family": "IBM Plex Sans, Segoe UI, sans-serif",
    "title_family": "Fraunces, Georgia, serif",
    "chart_height": 360,
    "line_width": 2,
    "point_size": 7,
    "spacing": 12,
}


def theme_tokens(theme: str = "light") -> dict:
    """Return a copy of the requested theme plus semantic shared tokens."""
    name = theme if theme in {"light", "dark"} else "light"
    return {**TOKENS, **TOKENS[name], "theme": name}
