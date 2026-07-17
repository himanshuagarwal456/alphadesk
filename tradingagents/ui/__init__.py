"""AlphaDesk feed UI ("FinTok"): agents generate knowledge, we visualise it and
disseminate it in a portfolio-aware vertical feed.

Pipeline: a completed agent run (``final_state``) -> :mod:`.deck_builder` turns
its structured knowledge into a :class:`~tradingagents.ui.feed_schema.Narrative`
(an album of chart cards) -> :mod:`.render` lays narratives out as a two-axis
scroll-snap feed (vertical = narratives ranked by dominance, horizontal = the
card arc: hook -> evidence -> tension -> verdict).

Public surface:

- ``Feed`` / ``Narrative`` / ``Card`` / ``CardKind`` — the feed contract
- ``build_feed`` / ``build_narrative``                — run knowledge -> feed
- ``render_feed_html`` / ``write_feed_html``          — feed -> self-contained HTML
- ``load_saved_runs``                                 — load past runs from disk
- ``sample_feed``                                     — a demo feed (no network)
"""

from .deck_builder import build_feed, build_narrative, compute_dominance
from .feed_schema import Card, CardKind, Feed, Narrative
from .render import render_feed_html, write_feed_html
from .runs import load_saved_runs
from .sample import sample_feed

__all__ = [
    "Card",
    "CardKind",
    "Feed",
    "Narrative",
    "build_feed",
    "build_narrative",
    "compute_dominance",
    "load_saved_runs",
    "render_feed_html",
    "sample_feed",
    "write_feed_html",
]
