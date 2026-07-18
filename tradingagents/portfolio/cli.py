"""CLI for portfolio import preview/confirm (Phase 5).

    alphadesk-portfolio import book.csv --preview
    alphadesk-portfolio import book.csv --confirm --workspace ws_local
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

from tradingagents.portfolio.preview import preview_portfolio_csv
from tradingagents.portfolio.service import CURRENT_SNAPSHOT_ID


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="alphadesk-portfolio",
        description="Preview or confirm a broker CSV as the AlphaDesk research book.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    import_parser = sub.add_parser("import", help="Import a broker CSV export")
    import_parser.add_argument("csv_path", type=Path)
    mode = import_parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--preview", action="store_true", help="Validate without saving")
    mode.add_argument(
        "--confirm",
        action="store_true",
        help="Save as the workspace current book (requires [server] extra)",
    )
    import_parser.add_argument("--as-of", default=None, help="Snapshot date YYYY-MM-DD")
    import_parser.add_argument(
        "--workspace",
        default=os.environ.get("ALPHADESK_DEFAULT_WORKSPACE_ID", "ws_local"),
    )
    import_parser.add_argument(
        "--column",
        action="append",
        default=[],
        metavar="FIELD=HEADER",
        help="Canonical field override, e.g. --column symbol=Ticker",
    )
    import_parser.add_argument(
        "--database-url",
        default=os.environ.get("ALPHADESK_DATABASE_URL")
        or os.environ.get("DATABASE_URL"),
    )

    args = parser.parse_args(argv)
    if args.command != "import":
        parser.error(f"unknown command {args.command}")

    column_map = {}
    for item in args.column:
        if "=" not in item:
            parser.error(f"--column expects FIELD=HEADER, got {item!r}")
        field, header = item.split("=", 1)
        column_map[field.strip()] = header.strip()

    preview = preview_portfolio_csv(
        path=args.csv_path,
        as_of=args.as_of or date.today().isoformat(),
        column_map=column_map or None,
    )
    if args.preview or not args.confirm:
        print(json.dumps(preview.model_dump(mode="json"), indent=2, sort_keys=True))
        if preview.fatal_error:
            return 2
        if preview.error_rows:
            return 1
        return 0

    if preview.fatal_error or preview.portfolio is None or not preview.can_confirm:
        print(json.dumps(preview.model_dump(mode="json"), indent=2, sort_keys=True))
        print(
            "Refusing to confirm: fix column_map / row errors and --preview again.",
            file=sys.stderr,
        )
        return 2

    try:
        from tradingagents.persistence.repositories import (
            PortfolioRepository,
            PortfolioStateRepository,
        )
        from tradingagents.persistence.session import SessionFactory, create_engine_from_url
        from tradingagents.persistence.settings import load_persistence_settings
    except ImportError:
        print(
            'Confirm requires the server extra: pip install "alphadesk[server]"',
            file=sys.stderr,
        )
        return 2

    settings = load_persistence_settings()
    url = args.database_url or settings.database_url
    factory = SessionFactory(create_engine_from_url(url))
    factory.create_all()
    with factory.session_scope() as session:
        sid, portfolio = PortfolioRepository(session).save(
            preview.portfolio,
            workspace_id=args.workspace,
            snapshot_id=CURRENT_SNAPSHOT_ID,
        )
        controls = PortfolioStateRepository(session).get_controls(args.workspace)
        PortfolioStateRepository(session).set_controls(
            args.workspace,
            controls.model_copy(
                update={"current_snapshot_id": sid, "research_only": True}
            ),
        )
    print(
        json.dumps(
            {
                "id": sid,
                "workspace_id": args.workspace,
                "positions": len(portfolio.positions),
                "cash": portfolio.cash,
                "research_only": True,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
