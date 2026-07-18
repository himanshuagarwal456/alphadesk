"""Shared FastAPI dependencies (workspace scoping, DB sessions)."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request
from sqlalchemy.orm import Session

from tradingagents.persistence.session import SessionFactory
from tradingagents.persistence.settings import PersistenceSettings


@dataclass
class AppState:
    session_factory: SessionFactory
    settings: PersistenceSettings


def get_app_state(request: Request) -> AppState:
    return request.app.state.alphadesk


def get_workspace_id(
    request: Request,
    x_workspace_id: str | None = Header(default=None, alias="X-Workspace-Id"),
) -> str:
    """Resolve the active workspace.

    Phase 4 will replace the header with authenticated membership checks.
    Until then, ``X-Workspace-Id`` selects the tenant; missing header uses the
    configured default local workspace.
    """
    state = get_app_state(request)
    workspace_id = (x_workspace_id or state.settings.default_workspace_id).strip()
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace id required")
    return workspace_id


def get_db_session(request: Request) -> Iterator[Session]:
    state = get_app_state(request)
    session = state.session_factory.session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
