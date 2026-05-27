"""Ticket 9 — Database-backed version history reads.

Reads ConfigVersion rows from the database, returning the same response
shapes as the file-backed ``list_versions`` / ``get_version`` / ``get_version_data``
functions so the router and frontend remain unchanged.
"""
from __future__ import annotations

from typing import Any, cast

from sqlalchemy import asc, desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import ConfigVersion


async def db_list_versions(
    session: AsyncSession, scope: str, target: str
) -> list[dict[str, Any]]:
    """List all versions for a scope+target, newest first."""
    res = await session.execute(
        select(ConfigVersion)
        .where(
            ConfigVersion.scope == scope,
            ConfigVersion.target_key == target,
        )
        .order_by(desc(ConfigVersion.version_number))
    )
    rows = list(res.scalars().all())
    return [
        {
            "version": row.version_number,
            "timestamp": row.created_at.isoformat() if row.created_at else "",
            "actor": row.actor,
            "summary": row.summary or "",
            "scope": row.scope,
            "target": row.target_key,
        }
        for row in rows
    ]


async def db_get_version(
    session: AsyncSession, scope: str, target: str, version: int
) -> dict[str, Any]:
    """Return the full envelope (metadata + data) for a specific version."""
    res = await session.execute(
        select(ConfigVersion).where(
            ConfigVersion.scope == scope,
            ConfigVersion.target_key == target,
            ConfigVersion.version_number == version,
        ).limit(1)
    )
    row = res.scalar_one_or_none()
    if row is None:
        raise FileNotFoundError(
            f"Version {version} not found for {scope}:{target}"
        )
    return {
        "version": row.version_number,
        "timestamp": row.created_at.isoformat() if row.created_at else "",
        "actor": row.actor,
        "summary": row.summary or "",
        "scope": row.scope,
        "target": row.target_key,
        "data": row.data_json or {},
    }


async def db_get_version_data(
    session: AsyncSession, scope: str, target: str, version: int
) -> dict[str, Any]:
    """Return only the ``data`` payload for a version (used for diff)."""
    envelope = await db_get_version(session, scope, target, version)
    return cast(dict[str, Any], envelope["data"])
