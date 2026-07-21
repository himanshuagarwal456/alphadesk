"""CLI/API helper to tick monitoring for one or many workspaces."""

from __future__ import annotations

import argparse
import logging
import os

from tradingagents.monitoring.service import MonitoringService
from tradingagents.persistence.session import SessionFactory, create_engine_from_url
from tradingagents.persistence.settings import load_persistence_settings

logger = logging.getLogger(__name__)


def tick_workspace(
    session_factory: SessionFactory,
    workspace_id: str,
    *,
    use_demo_if_empty: bool = True,
):
    with session_factory.session_scope() as session:
        return MonitoringService(session, workspace_id=workspace_id).tick(
            use_demo_if_empty=use_demo_if_empty
        )


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run AlphaDesk monitoring tick")
    parser.add_argument(
        "--workspace",
        action="append",
        dest="workspaces",
        help="Workspace id (repeatable). Defaults to ALPHADESK_MONITOR_WORKSPACES or ws_local.",
    )
    parser.add_argument(
        "--no-demo",
        action="store_true",
        help="Do not synthesize demo events when pollers return nothing",
    )
    args = parser.parse_args(argv)
    settings = load_persistence_settings()
    factory = SessionFactory(create_engine_from_url(settings.database_url))
    factory.create_all()
    raw = args.workspaces or os.environ.get("ALPHADESK_MONITOR_WORKSPACES", "ws_local")
    workspaces = raw if isinstance(raw, list) else [w.strip() for w in raw.split(",") if w.strip()]
    for workspace_id in workspaces:
        run = tick_workspace(
            factory,
            workspace_id,
            use_demo_if_empty=not args.no_demo,
        )
        logger.info(
            "monitor tick workspace=%s status=%s cards=%s material=%s dupes=%s",
            workspace_id,
            run.status.value,
            run.cards_created,
            run.events_material,
            run.duplicates_skipped,
        )


if __name__ == "__main__":
    main()
