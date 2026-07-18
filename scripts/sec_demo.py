"""Run one SEC-backed AAPL analysis and open the resulting AlphaDesk feed.

Usage:
    python scripts/sec_demo.py
"""

from __future__ import annotations

from copy import deepcopy
from datetime import date

from dotenv import load_dotenv

from tradingagents.default_config import DEFAULT_CONFIG
from tradingagents.graph.trading_graph import TradingAgentsGraph
from tradingagents.ui.feed_cli import main as feed_main


def main() -> None:
    load_dotenv()
    config = deepcopy(DEFAULT_CONFIG)
    config["data_vendors"]["fundamental_data"] = "sec"

    desk = TradingAgentsGraph(
        selected_analysts=("fundamentals",),
        config=config,
    )
    _, rating = desk.propagate("AAPL", date.today().isoformat())
    print(f"AAPL rating: {rating}")
    feed_main([])


if __name__ == "__main__":
    main()
