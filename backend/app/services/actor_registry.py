"""Phase 4 — Ticket 12: Lightweight actor registry service.

Provides ``upsert_actor`` to record actor strings in the ``config_actor``
table without requiring SSO or a full user table.

The existing audit/version actor string columns remain unchanged.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.actor import ACTOR_SOURCE_VALUES, ConfigActor


async def upsert_actor(
    session: AsyncSession,
    actor_key: str,
    *,
    source: str = "header",
    display_name: str | None = None,
    email: str | None = None,
) -> ConfigActor:
    """Get or create a ConfigActor record for ``actor_key``.

    Updates ``last_seen_at`` on every call.

    Parameters
    ----------
    session:
        Async SQLAlchemy session.  Caller must commit.
    actor_key:
        The canonical actor string (e.g. ``"system"``, ``"alice"``).
    source:
        How this actor was resolved: system | header | manual | future_sso.
    display_name:
        Optional human-readable name; only stored if provided and not already set.
    email:
        Optional email; only stored if provided and not already set.

    Returns
    -------
    The existing or newly created ConfigActor row.
    """
    if source not in ACTOR_SOURCE_VALUES:
        source = "header"  # safe fallback

    now = datetime.now(timezone.utc)

    res = await session.execute(
        select(ConfigActor).where(ConfigActor.actor_key == actor_key).limit(1)
    )
    actor = res.scalar_one_or_none()

    if actor is None:
        actor = ConfigActor(
            actor_key=actor_key,
            source=source,
            display_name=display_name,
            email=email,
            first_seen_at=now,
            last_seen_at=now,
            is_active=True,
            created_by="system",
            updated_by="system",
            created_at=now,
            updated_at=now,
        )
        session.add(actor)
    else:
        actor.last_seen_at = now
        actor.updated_at = now
        actor.updated_by = "system"
        if display_name and not actor.display_name:
            actor.display_name = display_name
        if email and not actor.email:
            actor.email = email

    await session.flush()
    return actor


async def get_actor(
    session: AsyncSession, actor_key: str
) -> ConfigActor | None:
    """Return the ConfigActor row for ``actor_key``, or None."""
    res = await session.execute(
        select(ConfigActor).where(ConfigActor.actor_key == actor_key).limit(1)
    )
    return res.scalar_one_or_none()


def actor_to_dict(actor: ConfigActor) -> dict[str, Any]:
    return {
        "id": actor.id,
        "actor_key": actor.actor_key,
        "display_name": actor.display_name,
        "email": actor.email,
        "source": actor.source,
        "first_seen_at": actor.first_seen_at.isoformat() if actor.first_seen_at else None,
        "last_seen_at": actor.last_seen_at.isoformat() if actor.last_seen_at else None,
        "is_active": actor.is_active,
    }
