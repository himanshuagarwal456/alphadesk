"""Top-down Market View layer for AlphaDesk.

Forms the desk's macro regime and risk posture once per run date and feeds it as
a *sizing lens* into every per-name decision. Complements the bottom-up
:mod:`tradingagents.portfolio` layer.

Public surface:

- ``MarketView`` / ``MarketRegime`` / ``SizingBias`` — structured view + render
- ``MarketViewBuilder``           — macro/news context -> ``MarketView``
- ``MarketViewStore``             — deterministic, date-aware JSON persistence
"""

from .builder import MarketViewBuilder, default_macro_context
from .schemas import MarketRegime, MarketView, SizingBias
from .store import MarketViewStore

__all__ = [
    "MarketRegime",
    "MarketView",
    "MarketViewBuilder",
    "MarketViewStore",
    "SizingBias",
    "default_macro_context",
]
