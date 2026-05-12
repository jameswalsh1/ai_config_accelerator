"""Phase 5B — Wizard flows router.

Provides endpoints for managing user-level wizard flows.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthUser, require_config_editor

router = APIRouter(prefix="/api/wizard", tags=["flows"])


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------


async def _require_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; raises 503 if not in database mode."""
    from app.settings import get_config_source_settings

    if get_config_source_settings().config_source != "database":
        raise HTTPException(
            status_code=503,
            detail="Flow endpoints require CONFIG_SOURCE=database",
        )
    from app.db.session import get_db_session

    async for session in get_db_session():
        yield session


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class FlowStepInput(BaseModel):
    step_key: str
    is_enabled: bool = True
    custom_title: str | None = None
    custom_description: str | None = None


class CreateFlowRequest(BaseModel):
    name: str
    description: str = ""
    tool_key: str | None = None
    step_keys: list[str] | None = None


class UpdateFlowRequest(BaseModel):
    name: str | None = None
    description: str | None = None
    steps: list[FlowStepInput] | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/flows")
async def list_flows(
    include_archived: bool = Query(False),
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> list[dict[str, Any]]:
    """List the current user's wizard flows."""
    from app.services.wizard_flow_service import list_flows as _list

    return await _list(session, _user.username, include_archived=include_archived)


@router.post("/flows")
async def create_flow(
    body: CreateFlowRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Create a new wizard flow."""
    from app.services.wizard_flow_service import create_flow as _create, FlowServiceError
    from app.db.models.tool import AITool
    from sqlalchemy import select

    tool_id: int | None = None
    if body.tool_key:
        res = await session.execute(select(AITool).where(AITool.tool_key == body.tool_key))
        tool_row = res.scalar_one_or_none()
        if tool_row:
            tool_id = tool_row.id

    try:
        result = await _create(
            session,
            _user.username,
            body.name,
            tool_id=tool_id,
            description=body.description,
            step_keys=body.step_keys,
        )
        await session.commit()
        return result
    except FlowServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/flows/default")
async def get_default_flow(
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Get or create the user's default flow."""
    from app.services.wizard_flow_service import get_or_create_default_flow

    result = await get_or_create_default_flow(session, _user.username)
    await session.commit()
    return result


@router.get("/flows/{flow_id}")
async def get_flow(
    flow_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Get a flow by ID."""
    from app.services.wizard_flow_service import (
        FlowNotFoundError,
        FlowOwnershipError,
        get_flow as _get,
    )

    try:
        return await _get(session, flow_id, _user.username)
    except FlowOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except FlowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.put("/flows/{flow_id}")
async def update_flow(
    flow_id: int,
    body: UpdateFlowRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Update a flow's metadata and/or step ordering."""
    from app.services.wizard_flow_service import (
        FlowNotFoundError,
        FlowOwnershipError,
        FlowServiceError,
        update_flow as _update,
    )

    step_keys: list[dict[str, Any]] | None = None
    if body.steps is not None:
        step_keys = [s.model_dump() for s in body.steps]

    try:
        result = await _update(
            session,
            flow_id,
            _user.username,
            name=body.name,
            description=body.description,
            step_keys=step_keys,
        )
        await session.commit()
        return result
    except FlowOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except FlowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except FlowServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/flows/{flow_id}/set-default")
async def set_default_flow(
    flow_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Set a flow as the default."""
    from app.services.wizard_flow_service import (
        FlowNotFoundError,
        FlowOwnershipError,
        set_default_flow as _set_default,
    )

    try:
        result = await _set_default(session, flow_id, _user.username)
        await session.commit()
        return result
    except FlowOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except FlowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/flows/{flow_id}/archive")
async def archive_flow(
    flow_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Archive a flow."""
    from app.services.wizard_flow_service import (
        FlowNotFoundError,
        FlowOwnershipError,
        archive_flow as _archive,
    )

    try:
        result = await _archive(session, flow_id, _user.username)
        await session.commit()
        return result
    except FlowOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except FlowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
