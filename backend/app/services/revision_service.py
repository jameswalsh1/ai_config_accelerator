"""Phase 4 — Tickets 13, 14, 15, 16: Personal saved revision service.

Provides:
- save_revision      (Ticket 14) — save wizard answers as a personal revision
- list_revisions     (Ticket 15) — list actor's own revisions
- get_revision       (Ticket 15) — load a single revision with its values
- archive_revision   (Ticket 16) — archive a personal revision
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language
from app.db.models.revision import REVISION_STATUS_VALUES, UserConfigRevision, UserConfigRevisionValue
from app.db.models.schema import ConfigField, ConfigSchema
from app.db.models.tool import AITool


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class RevisionServiceError(Exception):
    """Base error for revision service operations."""


class RevisionNotFoundError(RevisionServiceError):
    """Raised when the requested revision does not exist or is inaccessible."""


class RevisionOwnershipError(RevisionServiceError):
    """Raised when an actor attempts to access another actor's revision."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _revision_to_dict(revision: UserConfigRevision) -> dict[str, Any]:
    return {
        "id": revision.id,
        "owner_actor": revision.owner_actor,
        "name": revision.name,
        "description": revision.description,
        "status": revision.status,
        "source_tool_id": revision.source_tool_id,
        "source_language_id": revision.source_language_id,
        "source_schema_id": revision.source_schema_id,
        "source_layers_json": revision.source_layers_json,
        "created_at": revision.created_at.isoformat() if revision.created_at else None,
        "updated_at": revision.updated_at.isoformat() if revision.updated_at else None,
    }


def _value_to_dict(val: UserConfigRevisionValue) -> dict[str, Any]:
    return {
        "field_path": val.field_path,
        "value": val.value_json,
    }


async def _resolve_tool_id(session: AsyncSession, tool_key: str) -> int | None:
    res = await session.execute(
        select(AITool).where(AITool.tool_key == tool_key).limit(1)
    )
    tool = res.scalar_one_or_none()
    return tool.id if tool else None


async def _resolve_language_id(session: AsyncSession, language_key: str) -> int | None:
    res = await session.execute(
        select(Language).where(Language.language_key == language_key).limit(1)
    )
    lang = res.scalar_one_or_none()
    return lang.id if lang else None


async def _resolve_schema_id(session: AsyncSession) -> int | None:
    from app.db.models.schema import ConfigSchema
    res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = res.scalar_one_or_none()
    return schema.id if schema else None


async def _validate_field_paths(
    session: AsyncSession, field_paths: list[str]
) -> None:
    """Validate that all field paths exist in the active schema.

    Raises ``RevisionServiceError`` for the first unknown path found.
    """
    schema_res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = schema_res.scalar_one_or_none()
    if schema is None:
        return  # cannot validate without a schema; allow through

    for path in field_paths:
        res = await session.execute(
            select(ConfigField).where(
                ConfigField.schema_id == schema.id,
                ConfigField.field_path == path,
            ).limit(1)
        )
        if res.scalar_one_or_none() is None:
            raise RevisionServiceError(
                f"Field path '{path}' does not exist in the active schema"
            )


# ---------------------------------------------------------------------------
# Ticket 14 — Save personal revision
# ---------------------------------------------------------------------------


async def save_revision(
    session: AsyncSession,
    owner_actor: str,
    name: str,
    answers: dict[str, Any],
    *,
    description: str = "",
    tool_key: str | None = None,
    language_key: str | None = None,
) -> dict[str, Any]:
    """Save wizard answers as a personal revision owned by ``owner_actor``.

    Parameters
    ----------
    session:
        Async SQLAlchemy session.  Caller must commit.
    owner_actor:
        Actor string (the owner of this revision).
    name:
        Human-readable name for the revision.
    answers:
        Dict of ``{field_path: value}`` pairs.
    description:
        Optional description.
    tool_key:
        The tool identifier (e.g. ``"claude"``).
    language_key:
        The language identifier (e.g. ``"python"``).

    Returns
    -------
    Summary dict of the created revision.
    """
    if not name.strip():
        raise RevisionServiceError("Revision name must not be empty")

    # Validate field paths
    await _validate_field_paths(session, list(answers.keys()))

    now = datetime.now(timezone.utc)
    tool_db_id = await _resolve_tool_id(session, tool_key) if tool_key else None
    lang_db_id = await _resolve_language_id(session, language_key) if language_key else None
    schema_db_id = await _resolve_schema_id(session)

    revision = UserConfigRevision(
        owner_actor=owner_actor,
        name=name,
        description=description,
        status="active",
        source_tool_id=tool_db_id,
        source_language_id=lang_db_id,
        source_schema_id=schema_db_id,
        source_layers_json=None,
        created_by=owner_actor,
        updated_by=owner_actor,
        created_at=now,
        updated_at=now,
    )
    session.add(revision)
    await session.flush()

    for field_path, value in answers.items():
        val = UserConfigRevisionValue(
            revision_id=revision.id,
            field_path=field_path,
            value_json=value,
            created_by=owner_actor,
            updated_by=owner_actor,
            created_at=now,
            updated_at=now,
        )
        session.add(val)

    await session.flush()
    result = _revision_to_dict(revision)
    result["values"] = [{"field_path": k, "value": v} for k, v in answers.items()]
    return result


# ---------------------------------------------------------------------------
# Ticket 15 — List and load personal revisions
# ---------------------------------------------------------------------------


async def list_revisions(
    session: AsyncSession,
    owner_actor: str,
    *,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Return the owner's personal revisions, newest first.

    ``include_archived=True`` includes archived revisions.
    """
    stmt = select(UserConfigRevision).where(
        UserConfigRevision.owner_actor == owner_actor
    )
    if not include_archived:
        stmt = stmt.where(UserConfigRevision.status != "archived")
    stmt = stmt.order_by(UserConfigRevision.created_at.desc())

    res = await session.execute(stmt)
    return [_revision_to_dict(r) for r in res.scalars().all()]


async def get_revision(
    session: AsyncSession,
    revision_id: int,
    owner_actor: str,
) -> dict[str, Any]:
    """Load a single revision with its field values.

    Raises ``RevisionNotFoundError`` if not found.
    Raises ``RevisionOwnershipError`` if the revision belongs to a different actor.
    """
    res = await session.execute(
        select(UserConfigRevision).where(
            UserConfigRevision.id == revision_id
        ).limit(1)
    )
    revision = res.scalar_one_or_none()
    if revision is None:
        raise RevisionNotFoundError(f"Revision id={revision_id} not found")
    if revision.owner_actor != owner_actor:
        raise RevisionOwnershipError(
            f"Revision id={revision_id} belongs to a different actor"
        )

    vals_res = await session.execute(
        select(UserConfigRevisionValue).where(
            UserConfigRevisionValue.revision_id == revision_id
        ).order_by(UserConfigRevisionValue.field_path)
    )
    values = [_value_to_dict(v) for v in vals_res.scalars().all()]

    result = _revision_to_dict(revision)
    result["values"] = values
    return result


# ---------------------------------------------------------------------------
# Ticket 16 — Archive personal revision
# ---------------------------------------------------------------------------


async def archive_revision(
    session: AsyncSession,
    revision_id: int,
    owner_actor: str,
) -> dict[str, Any]:
    """Archive a personal revision.

    The revision values are preserved.  The revision is excluded from the
    default list endpoint after archiving.

    Raises ``RevisionNotFoundError`` / ``RevisionOwnershipError`` as above.
    Raises ``RevisionServiceError`` if already archived.
    """
    res = await session.execute(
        select(UserConfigRevision).where(
            UserConfigRevision.id == revision_id
        ).limit(1)
    )
    revision = res.scalar_one_or_none()
    if revision is None:
        raise RevisionNotFoundError(f"Revision id={revision_id} not found")
    if revision.owner_actor != owner_actor:
        raise RevisionOwnershipError(
            f"Revision id={revision_id} belongs to a different actor"
        )
    if revision.status == "archived":
        raise RevisionServiceError(
            f"Revision id={revision_id} is already archived"
        )

    now = datetime.now(timezone.utc)
    revision.status = "archived"
    revision.updated_by = owner_actor
    revision.updated_at = now
    await session.flush()

    return _revision_to_dict(revision)
