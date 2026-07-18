"""Environment-backed settings for the persistence and API layers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class PersistenceSettings:
    """Resolved connection and storage paths.

    Defaults prefer a local SQLite file under ``~/.tradingagents`` so a
    developer can run the API without provisioning Postgres. Production
    sets ``ALPHADESK_DATABASE_URL`` (or ``DATABASE_URL``) to Postgres.
    """

    database_url: str
    object_store_dir: Path
    default_workspace_id: str = "ws_local"
    api_title: str = "AlphaDesk API"
    api_version: str = "v1"


def load_persistence_settings() -> PersistenceSettings:
    home = Path(os.path.expanduser("~")) / ".tradingagents"
    default_db = home / "alphadesk.db"
    database_url = (
        os.environ.get("ALPHADESK_DATABASE_URL")
        or os.environ.get("DATABASE_URL")
        or f"sqlite:///{default_db}"
    )
    object_dir = Path(
        os.environ.get(
            "ALPHADESK_OBJECT_STORE_DIR",
            str(home / "object_store"),
        )
    ).expanduser()
    workspace = os.environ.get("ALPHADESK_DEFAULT_WORKSPACE_ID", "ws_local")
    return PersistenceSettings(
        database_url=database_url,
        object_store_dir=object_dir,
        default_workspace_id=workspace,
    )
