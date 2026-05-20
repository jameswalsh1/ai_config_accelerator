"""Phase 4 — Revisions router.

Tickets: 14, 15, 16, 18

Provides personal saved wizard revision endpoints:
  POST  /api/wizard/revisions               - save revision
  GET   /api/wizard/revisions               - list own revisions
  GET   /api/wizard/revisions/{id}          - load single revision
  POST  /api/wizard/revisions/{id}/archive  - archive revision
  POST  /api/wizard/revisions/{id}/submit   - submit as template candidate
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthUser, require_config_editor

router = APIRouter(prefix="/api/wizard", tags=["revisions"])


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------


async def _require_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; raises 503 if not in database mode."""
    from app.settings import get_config_source_settings

    if get_config_source_settings().config_source != "database":
        raise HTTPException(
            status_code=503,
            detail="Revision endpoints require CONFIG_SOURCE=database",
        )
    from app.db.session import get_db_session

    async for session in get_db_session():
        yield session


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class SaveRevisionRequest(BaseModel):
    name: str
    description: str = ""
    tool_key: str | None = None
    language_key: str | None = None
    answers: dict[str, Any]


class SubmitCandidateRequest(BaseModel):
    target_layer_type: str  # "tool" | "language" | "combo"
    target_tool_key: str | None = None
    target_language_key: str | None = None
    summary: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/revisions")
async def save_revision(
    body: SaveRevisionRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 14 — Save a wizard revision for the current actor."""
    from app.services.revision_service import RevisionServiceError, save_revision as _save

    try:
        result = await _save(
            session,
            _user.username,
            body.name,
            body.answers,
            description=body.description,
            tool_key=body.tool_key,
            language_key=body.language_key,
        )
        await session.commit()
        return result
    except RevisionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.get("/revisions")
async def list_revisions(
    include_archived: bool = Query(False),
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> list[dict[str, Any]]:
    """Ticket 15 — List the current actor's personal revisions."""
    from app.services.revision_service import list_revisions as _list

    return await _list(session, _user.username, include_archived=include_archived)


@router.get("/revisions/{revision_id}")
async def get_revision(
    revision_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 15 — Load a single revision with field values."""
    from app.services.revision_service import (
        RevisionNotFoundError,
        RevisionOwnershipError,
        get_revision as _get,
    )

    try:
        return await _get(session, revision_id, _user.username)
    except RevisionOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RevisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/revisions/{revision_id}/archive")
async def archive_revision(
    revision_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 16 — Archive a personal revision."""
    from app.services.revision_service import (
        RevisionNotFoundError,
        RevisionOwnershipError,
        RevisionServiceError,
        archive_revision as _archive,
    )

    try:
        result = await _archive(session, revision_id, _user.username)
        await session.commit()
        return result
    except RevisionOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RevisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except RevisionServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/revisions/{revision_id}/submit")
async def submit_as_candidate(
    revision_id: int,
    body: SubmitCandidateRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 18 — Submit a revision as a template candidate for review."""
    from app.services.candidate_service import CandidateServiceError, submit_candidate
    from app.services.revision_service import RevisionNotFoundError, RevisionOwnershipError

    try:
        result = await submit_candidate(
            session,
            revision_id,
            _user.username,
            body.target_layer_type,
            body.summary,
            target_tool_key=body.target_tool_key,
            target_language_key=body.target_language_key,
        )
        await session.commit()
        return result
    except RevisionOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except RevisionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CandidateServiceError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
