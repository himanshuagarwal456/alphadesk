"""Workspace endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from tradingagents.api.deps import get_db_session, get_workspace_id
from tradingagents.domain.schemas import Workspace
from tradingagents.persistence.repositories import WorkspaceRepository

router = APIRouter(prefix="/workspaces")


class WorkspaceCreate(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)


@router.get("/me", response_model=Workspace)
def current_workspace(
    workspace_id: str = Depends(get_workspace_id),
    session: Session = Depends(get_db_session),
) -> Workspace:
    return WorkspaceRepository(session).ensure(workspace_id)


@router.post("", response_model=Workspace, status_code=201)
def create_workspace(
    body: WorkspaceCreate,
    session: Session = Depends(get_db_session),
) -> Workspace:
    return WorkspaceRepository(session).ensure(body.id, name=body.name)


@router.get("", response_model=list[Workspace])
def list_workspaces(session: Session = Depends(get_db_session)) -> list[Workspace]:
    return WorkspaceRepository(session).list()
