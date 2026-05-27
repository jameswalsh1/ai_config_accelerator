"""Phase 4 — Template candidates router.

Tickets: 19, 20, 21

Provides template candidate review endpoints:
  GET   /config/template-candidates                    - list candidates
  GET   /config/template-candidates/{id}               - candidate detail
  GET   /config/template-candidates/{id}/diff          - diff vs active layer
  POST  /config/template-candidates/{id}/reject        - reject candidate
  POST  /config/template-candidates/{id}/withdraw      - submitter withdraws
  POST  /config/template-candidates/{id}/accept        - accept → draft layer
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthUser, require_config_editor

router = APIRouter(prefix="/config", tags=["candidates"])


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------


async def _require_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; raises 503 if not in database mode."""
    from app.settings import get_config_source_settings

    if get_config_source_settings().config_source != "database":
        raise HTTPException(
            status_code=503,
            detail="Candidate endpoints require CONFIG_SOURCE=database",
        )
    from app.db.session import get_db_session

    async for session in get_db_session():
        yield session


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class RejectCandidateRequest(BaseModel):
    review_notes: str = ""


class AcceptCandidateRequest(BaseModel):
    review_notes: str = ""


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/template-candidates")
async def list_candidates(
    status: str | None = Query(None),
    submitted_by: str | None = Query(None),
    target_layer_type: str | None = Query(None),
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> list[dict[str, Any]]:
    """Ticket 19 — List template candidates."""
    from app.services.candidate_service import list_candidates as _list

    return await _list(
        session,
        status=status,
        submitted_by=submitted_by,
        target_layer_type=target_layer_type,
    )


@router.get("/template-candidates/{candidate_id}")
async def get_candidate(
    candidate_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 19 — Load a single candidate with revision values."""
    from app.services.candidate_service import CandidateNotFoundError, get_candidate as _get

    try:
        return await _get(session, candidate_id)
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.get("/template-candidates/{candidate_id}/diff")
async def diff_candidate(
    candidate_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 20 — Diff candidate values vs the active target layer."""
    from app.services.candidate_service import CandidateNotFoundError, diff_candidate as _diff

    try:
        return await _diff(session, candidate_id)
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/template-candidates/{candidate_id}/reject")
async def reject_candidate(
    candidate_id: int,
    body: RejectCandidateRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 19 — Reject a submitted candidate."""
    from app.services.candidate_service import (
        CandidateNotFoundError,
        CandidateStateError,
        reject_candidate as _reject,
    )

    try:
        result = await _reject(
            session,
            candidate_id,
            _user.username,
            review_notes=body.review_notes,
        )
        await session.commit()
        return result
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CandidateStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/template-candidates/{candidate_id}/withdraw")
async def withdraw_candidate(
    candidate_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 19 — Submitter withdraws a pending candidate."""
    from app.services.candidate_service import (
        CandidateNotFoundError,
        CandidateStateError,
        withdraw_candidate as _withdraw,
    )
    from app.services.revision_service import RevisionOwnershipError

    try:
        result = await _withdraw(session, candidate_id, _user.username)
        await session.commit()
        return result
    except RevisionOwnershipError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CandidateStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/template-candidates/{candidate_id}/accept")
async def accept_candidate(
    candidate_id: int,
    body: AcceptCandidateRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Ticket 21 — Accept a candidate and create a draft layer from its values."""
    from app.services.candidate_service import (
        CandidateNotFoundError,
        CandidateStateError,
        accept_candidate as _accept,
    )

    try:
        result = await _accept(
            session,
            candidate_id,
            _user.username,
            review_notes=body.review_notes,
        )
        await session.commit()
        return result
    except CandidateNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except CandidateStateError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
