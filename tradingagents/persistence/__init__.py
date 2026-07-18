"""Durable persistence for AlphaDesk (Phase 3).

Optional install: ``pip install "alphadesk[server]"``. The CLI and research
engine keep working without these dependencies; the API and repositories are
the multi-user product surface.
"""

from .exporters import CompatibilityExporter
from .object_store import LocalObjectStore, ObjectStore
from .session import SessionFactory, create_engine_from_url, get_session_factory
from .settings import PersistenceSettings, load_persistence_settings

__all__ = [
    "CompatibilityExporter",
    "LocalObjectStore",
    "ObjectStore",
    "PersistenceSettings",
    "SessionFactory",
    "create_engine_from_url",
    "get_session_factory",
    "load_persistence_settings",
]
