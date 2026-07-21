"""AlphaDesk feed UI: agents generate knowledge; we turn it into story posts.

Pipeline: completed runs -> :mod:`.deck_builder` composes a desk brief plus
multi-symbol theme stories -> :mod:`.render` lays them out as a social-style
feed (vertical = distinguishable posts, horizontal = full story arc with
affected tickers).
"""

from .chart_registry import ChartRegistry, register_builtin_charts, registry
from .chart_spec import ChartSpec, ChartType
from .deck_builder import build_feed, build_narrative, compute_dominance
from .feed_schema import Card, CardKind, Feed, Narrative
from .render import render_feed_html, write_feed_html
from .runs import load_saved_runs
from .sample import sample_feed

__all__ = [
    "Card",
    "CardKind",
    "ChartRegistry",
    "ChartSpec",
    "ChartType",
    "Feed",
    "Narrative",
    "build_feed",
    "build_narrative",
    "compute_dominance",
    "load_saved_runs",
    "render_feed_html",
    "register_builtin_charts",
    "registry",
    "sample_feed",
    "write_feed_html",
]
