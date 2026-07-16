"""Phase 4 — Tickets 18, 19, 20, 21: Template candidate service.

Provides:
- submit_candidate        (Ticket 18) — submit a personal revision for review
- list_candidates         (Ticket 19) — list candidates (config editors)
- get_candidate           (Ticket 19) — load a single candidate
- reject_candidate        (Ticket 19) — reject with notes
- withdraw_candidate      (Ticket 19) — submitter withdraws
- diff_candidate          (Ticket 20) — diff candidate vs active target layer
- accept_candidate        (Ticket 21) — accept into a draft layer
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.candidate import CANDIDATE_STATUS_VALUES, TemplateCandidate
from app.db.models.layer import ConfigLayer
from app.db.models.language import Language
from app.db.models.revision import UserConfigRevision, UserConfigRevisionValue
from app.db.models.tool import AITool
from app.services.revision_service import (
    RevisionNotFoundError,
    RevisionOwnershipError,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class CandidateServiceError(Exception):
    """Base error for candidate service operations."""


class CandidateNotFoundError(CandidateServiceError):
    """Raised when the candidate does not exist."""


class CandidateStateError(CandidateServiceError):
    """Raised when the requested operation is invalid for the current status."""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _candidate_to_dict(candidate: TemplateCandidate) -> dict[str, Any]:
    return {
        "id": candidate.id,
        "source_revision_id": candidate.source_revision_id,
        "submitted_by": candidate.submitted_by,
        "summary": candidate.summary,
        "target_layer_type": candidate.target_layer_type,
        "target_tool_id": candidate.target_tool_id,
        "target_language_id": candidate.target_language_id,
        "status": candidate.status,
        "review_notes": candidate.review_notes,
        "reviewed_by": candidate.reviewed_by,
        "reviewed_at": candidate.reviewed_at.isoformat() if candidate.reviewed_at else None,
        "resulting_layer_id": candidate.resulting_layer_id,
        "created_at": candidate.created_at.isoformat() if candidate.created_at else None,
        "updated_at": candidate.updated_at.isoformat() if candidate.updated_at else None,
    }


async def _load_candidate(
    session: AsyncSession, candidate_id: int
) -> TemplateCandidate:
    res = await session.execute(
        select(TemplateCandidate).where(TemplateCandidate.id == candidate_id).limit(1)
    )
    candidate = res.scalar_one_or_none()
    if candidate is None:
        raise CandidateNotFoundError(f"TemplateCandidate id={candidate_id} not found")
    return candidate


# ---------------------------------------------------------------------------
# Ticket 18 — Submit revision as candidate
# ---------------------------------------------------------------------------


async def submit_candidate(
    session: AsyncSession,
    revision_id: int,
    submitter_actor: str,
    target_layer_type: str,
    summary: str,
    *,
    target_tool_key: str | None = None,
    target_language_key: str | None = None,
) -> dict[str, Any]:
    """Submit a personal revision as a template candidate.

    The submitter must own the revision.  The revision status is updated
    to ``submitted``.

    Raises
    ------
    RevisionNotFoundError / RevisionOwnershipError
        On revision access issues.
    CandidateServiceError
        On validation failure.
    """
    rev_res = await session.execute(
        select(UserConfigRevision).where(UserConfigRevision.id == revision_id).limit(1)
    )
    revision = rev_res.scalar_one_or_none()
    if revision is None:
        raise RevisionNotFoundError(f"Revision id={revision_id} not found")
    if revision.owner_actor != submitter_actor:
        raise RevisionOwnershipError(
            f"Revision id={revision_id} belongs to a different actor"
        )
    if revision.status == "archived":
        raise CandidateServiceError("Archived revisions cannot be submitted")

    valid_layer_types = ("tool", "language", "combo")
    if target_layer_type not in valid_layer_types:
        raise CandidateServiceError(
            f"Invalid target_layer_type '{target_layer_type}'. "
            f"Valid values: {', '.join(valid_layer_types)}"
        )

    # Resolve tool/language DB IDs
    target_tool_db_id: int | None = None
    if target_tool_key:
        tool_res = await session.execute(
            select(AITool).where(AITool.tool_key == target_tool_key).limit(1)
        )
        tool = tool_res.scalar_one_or_none()
        if tool is None:
            raise CandidateServiceError(f"Tool '{target_tool_key}' not found")
        target_tool_db_id = tool.id

    target_lang_db_id: int | None = None
    if target_language_key:
        lang_res = await session.execute(
            select(Language).where(Language.language_key == target_language_key).limit(1)
        )
        lang = lang_res.scalar_one_or_none()
        if lang is None:
            raise CandidateServiceError(f"Language '{target_language_key}' not found")
        target_lang_db_id = lang.id

    now = datetime.now(timezone.utc)

    candidate = TemplateCandidate(
        source_revision_id=revision_id,
        submitted_by=submitter_actor,
        summary=summary,
        target_layer_type=target_layer_type,
        target_tool_id=target_tool_db_id,
        target_language_id=target_lang_db_id,
        status="submitted",
        created_by=submitter_actor,
        updated_by=submitter_actor,
        created_at=now,
        updated_at=now,
    )
    session.add(candidate)

    # Mark revision as submitted
    if revision.status == "active":
        revision.status = "submitted"
        revision.updated_by = submitter_actor
        revision.updated_at = now

    await session.flush()
    return _candidate_to_dict(candidate)


# ---------------------------------------------------------------------------
# Ticket 19 — List, get, reject, withdraw candidates
# ---------------------------------------------------------------------------


async def list_candidates(
    session: AsyncSession,
    *,
    status: str | None = None,
    submitted_by: str | None = None,
    target_layer_type: str | None = None,
) -> list[dict[str, Any]]:
    """List template candidates (config editor view), newest first."""
    stmt = select(TemplateCandidate).order_by(TemplateCandidate.created_at.desc())

    if status:
        stmt = stmt.where(TemplateCandidate.status == status)
    if submitted_by:
        stmt = stmt.where(TemplateCandidate.submitted_by == submitted_by)
    if target_layer_type:
        stmt = stmt.where(TemplateCandidate.target_layer_type == target_layer_type)

    res = await session.execute(stmt)
    return [_candidate_to_dict(c) for c in res.scalars().all()]


async def get_candidate(
    session: AsyncSession, candidate_id: int
) -> dict[str, Any]:
    """Load full candidate detail, including source revision values."""
    candidate = await _load_candidate(session, candidate_id)
    result = _candidate_to_dict(candidate)

    # Include source revision values for review
    vals_res = await session.execute(
        select(UserConfigRevisionValue).where(
            UserConfigRevisionValue.revision_id == candidate.source_revision_id
        ).order_by(UserConfigRevisionValue.field_path)
    )
    result["revision_values"] = [
        {"field_path": v.field_path, "value": v.value_json}
        for v in vals_res.scalars().all()
    ]
    return result


async def reject_candidate(
    session: AsyncSession,
    candidate_id: int,
    reviewer_actor: str,
    *,
    review_notes: str = "",
) -> dict[str, Any]:
    """Reject a submitted candidate with optional review notes.

    Raises ``CandidateStateError`` if the candidate is not in 'submitted' status.
    """
    candidate = await _load_candidate(session, candidate_id)
    if candidate.status != "submitted":
        raise CandidateStateError(
            f"Candidate id={candidate_id} cannot be rejected "
            f"(current status: '{candidate.status}')"
        )

    now = datetime.now(timezone.utc)
    candidate.status = "rejected"
    candidate.reviewed_by = reviewer_actor
    candidate.reviewed_at = now
    candidate.review_notes = review_notes
    candidate.updated_by = reviewer_actor
    candidate.updated_at = now

    await session.flush()
    return _candidate_to_dict(candidate)


async def withdraw_candidate(
    session: AsyncSession,
    candidate_id: int,
    submitter_actor: str,
) -> dict[str, Any]:
    """Withdraw a submitted candidate (submitter only).

    Raises ``CandidateStateError`` if the candidate is not in 'submitted' status.
    Raises ``RevisionOwnershipError`` if the actor is not the submitter.
    """
    candidate = await _load_candidate(session, candidate_id)
    if candidate.submitted_by != submitter_actor:
        raise RevisionOwnershipError(
            f"Candidate id={candidate_id} was submitted by a different actor"
        )
    if candidate.status != "submitted":
        raise CandidateStateError(
            f"Candidate id={candidate_id} cannot be withdrawn "
            f"(current status: '{candidate.status}')"
        )

    now = datetime.now(timezone.utc)
    candidate.status = "withdrawn"
    candidate.updated_by = submitter_actor
    candidate.updated_at = now

    await session.flush()
    return _candidate_to_dict(candidate)


# ---------------------------------------------------------------------------
# Ticket 20 — Diff candidate vs active target layer
# ---------------------------------------------------------------------------


async def diff_candidate(
    session: AsyncSession,
    candidate_id: int,
) -> dict[str, Any]:
    """Compare the candidate's revision values against the active target layer.

    Returns a structured diff of field value additions/changes relative to
    the current active configuration for the candidate's target scope.
    """
    candidate = await _load_candidate(session, candidate_id)

    # Load revision values
    vals_res = await session.execute(
        select(UserConfigRevisionValue).where(
            UserConfigRevisionValue.revision_id == candidate.source_revision_id
        ).order_by(UserConfigRevisionValue.field_path)
    )
    revision_values: dict[str, Any] = {
        v.field_path: v.value_json for v in vals_res.scalars().all()
    }

    # Find active target layer
    stmt = select(ConfigLayer).where(ConfigLayer.status == "active")
    if candidate.target_layer_type == "tool" and candidate.target_tool_id:
        stmt = stmt.where(
            ConfigLayer.layer_type == "tool",
            ConfigLayer.tool_id == candidate.target_tool_id,
        )
    elif candidate.target_layer_type == "language" and candidate.target_language_id:
        stmt = stmt.where(
            ConfigLayer.layer_type == "language",
            ConfigLayer.language_id == candidate.target_language_id,
        )
    else:
        stmt = stmt.where(ConfigLayer.layer_type == candidate.target_layer_type)

    layer_res = await session.execute(stmt.limit(1))
    active_layer = layer_res.scalar_one_or_none()

    # Collect current active layer field defaults (via metadata overrides)
    active_defaults: dict[str, Any] = {}
    if active_layer:
        from app.db.models.layer import ConfigFieldMetadataOverride
        fmo_res = await session.execute(
            select(ConfigFieldMetadataOverride).where(
                ConfigFieldMetadataOverride.layer_id == active_layer.id
            )
        )
        # Map field_id → default_value_json
        from app.db.models.schema import ConfigField, ConfigSchema
        schema_res = await session.execute(
            select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
        )
        schema = schema_res.scalar_one_or_none()
        if schema:
            for fmo in fmo_res.scalars().all():
                if fmo.default_value_json is not None:
                    field_res = await session.execute(
                        select(ConfigField).where(
                            ConfigField.id == fmo.field_id,
                            ConfigField.schema_id == schema.id,
                        ).limit(1)
                    )
                    field = field_res.scalar_one_or_none()
                    if field:
                        active_defaults[field.field_path] = fmo.default_value_json

    # Build diff
    changes: list[dict[str, Any]] = []
    all_paths = set(revision_values) | set(active_defaults)
    for path in sorted(all_paths):
        lv = active_defaults.get(path)
        rv = revision_values.get(path)
        if lv is None and rv is not None:
            changes.append({"path": path, "type": "added", "active": None, "candidate": rv})
        elif lv is not None and rv is None:
            pass  # candidate doesn't touch this field — no change
        elif lv != rv:
            changes.append({"path": path, "type": "changed", "active": lv, "candidate": rv})

    return {
        "candidate_id": candidate_id,
        "active_layer_id": active_layer.id if active_layer else None,
        "target_layer_type": candidate.target_layer_type,
        "changes": changes,
        "change_count": len(changes),
        "has_changes": len(changes) > 0,
    }


# ---------------------------------------------------------------------------
# Ticket 21 — Accept candidate → create draft layer
# ---------------------------------------------------------------------------


async def accept_candidate(
    session: AsyncSession,
    candidate_id: int,
    reviewer_actor: str,
    *,
    review_notes: str = "",
) -> dict[str, Any]:
    """Accept a template candidate and create a draft layer from its values.

    The candidate is NOT directly promoted to active.  A draft layer is
    created so the normal draft review/promotion workflow applies.

    Returns a dict with the candidate summary and the new draft layer id.

    Raises ``CandidateStateError`` if not in 'submitted' status.
    """
    candidate = await _load_candidate(session, candidate_id)
    if candidate.status != "submitted":
        raise CandidateStateError(
            f"Candidate id={candidate_id} cannot be accepted "
            f"(current status: '{candidate.status}')"
        )

    now = datetime.now(timezone.utc)

    # Load revision values
    vals_res = await session.execute(
        select(UserConfigRevisionValue).where(
            UserConfigRevisionValue.revision_id == candidate.source_revision_id
        )
    )
    revision_values = list(vals_res.scalars().all())

    # Find or build the draft layer
    # Determine layer_key and FK references
    tool_id: int | None = candidate.target_tool_id
    language_id: int | None = candidate.target_language_id

    if candidate.target_layer_type == "tool" and tool_id:
        tool_res = await session.execute(
            select(AITool).where(AITool.id == tool_id).limit(1)
        )
        tool = tool_res.scalar_one_or_none()
        layer_key = f"tool:{tool.tool_key}" if tool else f"tool:id{tool_id}"
    elif candidate.target_layer_type == "language" and language_id:
        lang_res = await session.execute(
            select(Language).where(Language.id == language_id).limit(1)
        )
        lang = lang_res.scalar_one_or_none()
        layer_key = f"language:{lang.language_key}" if lang else f"language:id{language_id}"
    else:
        layer_key = f"combo:candidate_{candidate_id}"

    version = f"candidate-{candidate_id}-{now.strftime('%Y%m%dT%H%M%SZ')}"

    draft = ConfigLayer(
        layer_type=candidate.target_layer_type,
        layer_key=layer_key,
        tool_id=tool_id,
        language_id=language_id,
        version=version,
        status="draft",
        draft_name=f"From candidate #{candidate_id}",
        draft_summary=(
            candidate.summary
            + (f"\n\nReviewer notes: {review_notes}" if review_notes else "")
        ),
        created_by=reviewer_actor,
        updated_by=reviewer_actor,
        created_at=now,
        updated_at=now,
    )
    session.add(draft)
    await session.flush()

    # Apply revision field values as metadata overrides
    from app.db.models.layer import ConfigFieldMetadataOverride
    from app.db.models.schema import ConfigField, ConfigSchema

    schema_res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = schema_res.scalar_one_or_none()

    if schema:
        for val in revision_values:
            # Find ConfigField by field_path
            field_res = await session.execute(
                select(ConfigField).where(
                    ConfigField.schema_id == schema.id,
                    ConfigField.field_path == val.field_path,
                ).limit(1)
            )
            field = field_res.scalar_one_or_none()
            if field is None:
                continue  # skip unknown paths

            fmo = ConfigFieldMetadataOverride(
                layer_id=draft.id,
                field_id=field.id,
                default_value_json=val.value_json,
                created_by=reviewer_actor,
                updated_by=reviewer_actor,
                created_at=now,
                updated_at=now,
            )
            session.add(fmo)

    await session.flush()

    # Update candidate status
    candidate.status = "accepted"
    candidate.reviewed_by = reviewer_actor
    candidate.reviewed_at = now
    candidate.review_notes = review_notes
    candidate.resulting_layer_id = draft.id
    candidate.updated_by = reviewer_actor
    candidate.updated_at = now

    await session.flush()

    return {
        "candidate": _candidate_to_dict(candidate),
        "draft_layer_id": draft.id,
        "draft_layer_key": draft.layer_key,
        "draft_version": draft.version,
    }
