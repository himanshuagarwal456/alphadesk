"""``alphadesk-feed`` — build the portfolio-aware feed and open it in a browser.

Two modes:

- ``--demo``           build a sample feed (no API spend / network) to feel the UX.
- default              build from saved runs under the configured ``results_dir``,
                       optionally made portfolio-aware with ``--portfolio book.csv``.
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path


def _default_out() -> Path:
    from tradingagents.default_config import DEFAULT_CONFIG

    return Path(DEFAULT_CONFIG["results_dir"]).expanduser() / "feed" / "feed.html"


def _build_from_runs(results_dir: str | None, portfolio_csv: str | None):
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.thesis import LivingThesisStore

    from .deck_builder import build_feed
    from .market_data import fetch_ohlcv
    from .runs import load_saved_runs

    results_dir = results_dir or DEFAULT_CONFIG["results_dir"]
    runs = load_saved_runs(results_dir)
    if not runs:
        return None, results_dir

    portfolio = None
    if portfolio_csv:
        from tradingagents.portfolio import load_portfolio_from_csv

        portfolio = load_portfolio_from_csv(portfolio_csv)

    ohlcv_map = {}
    for state in runs:
        symbol = (state.get("company_of_interest") or "").upper()
        df = fetch_ohlcv(symbol, state.get("trade_date"))
        if df is not None:
            ohlcv_map[symbol] = df

    return build_feed(
        runs,
        portfolio=portfolio,
        ohlcv_map=ohlcv_map,
        thesis_store=LivingThesisStore(DEFAULT_CONFIG["thesis_store_dir"]),
    ), results_dir


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="alphadesk-feed",
        description="Build the AlphaDesk portfolio-aware insight feed (FinTok).",
    )
    parser.add_argument("--demo", action="store_true",
                        help="Build a sample feed with no API/network access.")
    parser.add_argument("--results-dir", default=None,
                        help="Directory of saved runs (default: configured results_dir).")
    parser.add_argument("--portfolio", default=None,
                        help="Broker CSV export to make the feed portfolio-aware.")
    parser.add_argument("--out", default=None, help="Output HTML path.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser.")
    args = parser.parse_args(argv)

    if args.demo:
        from .sample import sample_feed

        feed = sample_feed()
    else:
        feed, results_dir = _build_from_runs(args.results_dir, args.portfolio)
        if feed is None:
            print(f"No saved runs found in {results_dir}. "
                  "Run an analysis first, or try `alphadesk-feed --demo`.")
            return 1

    from .render import write_feed_html

    out = Path(args.out).expanduser() if args.out else _default_out()
    path = write_feed_html(feed, out)
    print(f"Feed written to {path}  ({len(feed.narratives)} narrative(s))")
    if not args.no_open:
        webbrowser.open(path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
