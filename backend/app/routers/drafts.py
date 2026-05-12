"""Phase 4 — Drafts router.

Tickets: 3, 4, 5, 6, 7, 8, 9, 10, 11

Provides draft lifecycle management endpoints:
  POST   /config/drafts                    - create draft from active layer
  GET    /config/drafts                    - list drafts
  GET    /config/drafts/{id}               - get draft detail (basic)
  GET    /config/drafts/{id}/preview       - preview with draft layer applied
  GET    /config/drafts/{id}/diff          - diff draft vs source layer
  POST   /config/drafts/{id}/promote       - promote draft to active
  POST   /config/drafts/{id}/archive       - archive draft
  GET    /config/layers/compare            - compare any two layers by ID
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthUser, require_config_editor
from app.services.draft_service import (
    ActiveLayerNotFoundError,
    DraftServiceError,
    archive_draft as _archive,
    create_draft_from_active,
    diff_draft_vs_source,
    list_drafts as _list_drafts,
    load_draft_preview,
    promote_draft as _promote,
)
from app.services.layer_comparison import ComparisonError, compare_layers as _compare

router = APIRouter(prefix="/config", tags=["drafts"])


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------


async def _require_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; raises 503 if not in database mode."""
    from app.settings import get_config_source_settings

    if get_config_source_settings().config_source != "database":
        raise HTTPException(
            status_code=503,
            detail="Draft lifecycle endpoints require CONFIG_SOURCE=database",
        )
    from app.db.session import get_db_session

    async for session in get_db_session():
        yield session


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class CreateDraftRequest(BaseModel):
    scope: str  # "tool" | "language" | "combo"
    target: str  # tool_key or language_key
    draft_name: str
    draft_summary: str = ""


class PromoteDraftRequest(BaseModel):
    summary: str = ""


class ArchiveDraftRequest(BaseModel):
    reason: str = ""


class CompareLayersQuery(BaseModel):
    left_layer_id: int
    right_layer_id: int


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/drafts")
async def create_draft(
    body: CreateDraftRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 3 — Create a draft layer from the active layer."""
    try:
        result = await create_draft_from_active(
            session,
            body.scope,
            body.target,
            _user.username,
            draft_name=body.draft_name,
            draft_summary=body.draft_summary,
        )
        await session.commit()
        return result
    except ActiveLayerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except DraftServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))



@router.get("/drafts")
async def list_drafts(
    layer_type: str | None = Query(None),
    tool_key: str | None = Query(None),
    language_key: str | None = Query(None),
    status: str | None = Query(None),
    created_by: str | None = Query(None),
    include_archived: bool = Query(False),
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> list[dict[str, Any]]:
    """Ticket 10 — List draft layers."""
    return await _list_drafts(
        session,
        layer_type=layer_type,
        tool_key=tool_key,
        language_key=language_key,
        status=status,
        created_by=created_by,
        include_archived=include_archived,
    )


@router.get("/drafts/{draft_layer_id}/preview")
async def get_draft_preview(
    draft_layer_id: int,
    tool_id: str | None = Query(None),
    language_id: str | None = Query(None),
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 5 — Preview resolved config with the draft layer applied."""
    try:
        return await load_draft_preview(session, draft_layer_id, tool_id, language_id)
    except DraftServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/drafts/{draft_layer_id}/diff")
async def get_draft_diff(
    draft_layer_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 6 — Diff a draft layer against its source layer."""
    try:
        return await diff_draft_vs_source(session, draft_layer_id)
    except DraftServiceError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/drafts/{draft_layer_id}/promote")
async def promote_draft(
    draft_layer_id: int,
    body: PromoteDraftRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 7/8 — Promote a draft layer to active."""
    try:
        result = await _promote(
            session,
            draft_layer_id,
            _user.username,
            summary=body.summary,
        )
        await session.commit()
        return result
    except DraftServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/drafts/{draft_layer_id}/archive")
async def archive_draft(
    draft_layer_id: int,
    body: ArchiveDraftRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 9 — Archive a draft layer."""
    try:
        result = await _archive(
            session,
            draft_layer_id,
            _user.username,
            reason=body.reason,
        )
        await session.commit()
        return result
    except DraftServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/layers/compare")
async def compare_layers(
    left_layer_id: int = Query(..., description="ID of the left/before layer"),
    right_layer_id: int = Query(..., description="ID of the right/after layer"),
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 11 — Compare any two config layers by their DB IDs."""
    try:
        return await _compare(session, left_layer_id, right_layer_id)
    except ComparisonError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
