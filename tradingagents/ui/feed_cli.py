"""``alphadesk-feed`` — build the portfolio-aware feed and open it in a browser.

Modes:

- ``--demo``             sample cards (no LLM). Pass ``--portfolio`` or
                         ``--workspace`` so every holding appears in the desk brief.
- default                build from saved runs under ``results_dir``, optionally
                         portfolio-aware with ``--portfolio`` / ``--workspace``.
"""

from __future__ import annotations

import argparse
import webbrowser
from pathlib import Path


def _default_out() -> Path:
    from tradingagents.default_config import DEFAULT_CONFIG

    return Path(DEFAULT_CONFIG["results_dir"]).expanduser() / "feed" / "feed.html"


def _load_portfolio(portfolio_csv: str | None, workspace_id: str | None):
    if portfolio_csv:
        from tradingagents.portfolio import load_portfolio_from_csv

        return load_portfolio_from_csv(portfolio_csv)

    if not workspace_id:
        return None

    from tradingagents.persistence.repositories import (
        PortfolioRepository,
        PortfolioStateRepository,
    )
    from tradingagents.persistence.session import SessionFactory, create_engine_from_url
    from tradingagents.persistence.settings import load_persistence_settings
    from tradingagents.portfolio.service import CURRENT_SNAPSHOT_ID

    settings = load_persistence_settings()
    factory = SessionFactory(create_engine_from_url(settings.database_url))
    with factory.session_scope() as session:
        controls = PortfolioStateRepository(session).get_controls(workspace_id)
        snapshot_id = controls.current_snapshot_id or CURRENT_SNAPSHOT_ID
        book = PortfolioRepository(session).get(workspace_id, snapshot_id)
        if book is None and snapshot_id != CURRENT_SNAPSHOT_ID:
            book = PortfolioRepository(session).get(workspace_id, CURRENT_SNAPSHOT_ID)
        return book


def _build_from_runs(
    results_dir: str | None,
    portfolio_csv: str | None,
    workspace_id: str | None,
):
    from tradingagents.default_config import DEFAULT_CONFIG
    from tradingagents.thesis import LivingThesisStore

    from .deck_builder import build_feed
    from .market_data import fetch_ohlcv
    from .runs import load_saved_runs

    results_dir = results_dir or DEFAULT_CONFIG["results_dir"]
    runs = load_saved_runs(results_dir)
    if not runs:
        return None, results_dir

    portfolio = _load_portfolio(portfolio_csv, workspace_id)

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
        description="Build the AlphaDesk portfolio-aware insight feed.",
    )
    parser.add_argument(
        "--demo",
        action="store_true",
        help="Build a sample feed with no LLM. Uses portfolio when provided.",
    )
    parser.add_argument(
        "--results-dir",
        default=None,
        help="Directory of saved runs (default: configured results_dir).",
    )
    parser.add_argument(
        "--portfolio",
        default=None,
        help="Broker CSV export to make the feed cover your full book.",
    )
    parser.add_argument(
        "--workspace",
        default=None,
        help="Load the current book from the durable workspace store (e.g. ws_local).",
    )
    parser.add_argument("--out", default=None, help="Output HTML path.")
    parser.add_argument("--no-open", action="store_true", help="Do not open a browser.")
    args = parser.parse_args(argv)

    if args.demo:
        from .sample import sample_feed

        portfolio = _load_portfolio(args.portfolio, args.workspace)
        feed = sample_feed(portfolio)
        if portfolio is not None:
            n = len(getattr(portfolio, "open_positions", []) or [])
            print(f"Demo feed using portfolio with {n} open position(s)")
        else:
            print(
                "Demo feed using the default 2-name sample. "
                "Pass --portfolio book.csv or --workspace ws_local to cover your holdings."
            )
    else:
        feed, results_dir = _build_from_runs(
            args.results_dir, args.portfolio, args.workspace
        )
        if feed is None:
            print(
                f"No saved runs found in {results_dir}. "
                "Run an analysis first, or try `alphadesk-feed --demo --workspace ws_local`."
            )
            return 1

    from .render import write_feed_html

    out = Path(args.out).expanduser() if args.out else _default_out()
    path = write_feed_html(feed, out)
    symbols = sorted({s for n in feed.narratives for s in n.symbols})
    print(
        f"Feed written to {path}  "
        f"({len(feed.narratives)} stor{'y' if len(feed.narratives)==1 else 'ies'}, "
        f"{len(symbols)} symbol(s))"
    )
    if not args.no_open:
        webbrowser.open(path.as_uri())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
