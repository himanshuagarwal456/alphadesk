"""SQLAlchemy engine and session helpers."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from .models import Base
from .settings import PersistenceSettings, load_persistence_settings


def create_engine_from_url(database_url: str) -> Engine:
    """Create an engine; enable SQLite foreign keys when applicable."""
    connect_args: dict = {}
    if database_url.startswith("sqlite"):
        # Allow FastAPI TestClient / multi-thread access to a shared file DB.
        connect_args["check_same_thread"] = False
    engine = create_engine(database_url, future=True, connect_args=connect_args)
    if database_url.startswith("sqlite"):

        @event.listens_for(engine, "connect")
        def _set_sqlite_pragma(dbapi_connection, _connection_record) -> None:  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    return engine


class SessionFactory:
    """Thin wrapper around ``sessionmaker`` with schema bootstrap helpers."""

    def __init__(self, engine: Engine):
        self.engine = engine
        self._maker = sessionmaker(bind=engine, expire_on_commit=False, future=True)

    def create_all(self) -> None:
        Base.metadata.create_all(self.engine)

    def drop_all(self) -> None:
        Base.metadata.drop_all(self.engine)

    def session(self) -> Session:
        return self._maker()

    @contextmanager
    def session_scope(self) -> Iterator[Session]:
        session = self.session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()


_FACTORY: SessionFactory | None = None


def get_session_factory(
    settings: PersistenceSettings | None = None,
    *,
    create_schema: bool = False,
) -> SessionFactory:
    """Return a process-wide session factory (created on first use)."""
    global _FACTORY
    if _FACTORY is None:
        resolved = settings or load_persistence_settings()
        engine = create_engine_from_url(resolved.database_url)
        _FACTORY = SessionFactory(engine)
        if create_schema:
            _FACTORY.create_all()
    return _FACTORY


def reset_session_factory() -> None:
    """Clear the process-wide factory (tests only)."""
    global _FACTORY
    if _FACTORY is not None:
        _FACTORY.engine.dispose()
    _FACTORY = None
