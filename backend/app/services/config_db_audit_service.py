"""Ticket 8 — Database-backed audit log reads.

Reads ConfigAuditEvent rows from the database, returning the same response
shape as the file-backed ``read_audit_log`` function so the frontend remains
unchanged.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import ConfigAuditEvent


async def read_db_audit_log(
    session: AsyncSession,
    limit: int = 50,
    offset: int = 0,
    scope: str | None = None,
    target: str | None = None,
) -> dict[str, Any]:
    """Return a paginated audit log from the database.

    Response shape matches the file-backed ``read_audit_log`` so the router
    and frontend need no changes.
    """
    stmt = select(ConfigAuditEvent).order_by(desc(ConfigAuditEvent.created_at))

    count_stmt = select(ConfigAuditEvent)

    if scope is not None:
        stmt = stmt.where(ConfigAuditEvent.scope == scope)
        count_stmt = count_stmt.where(ConfigAuditEvent.scope == scope)
    if target is not None:
        stmt = stmt.where(ConfigAuditEvent.target_key == target)
        count_stmt = count_stmt.where(ConfigAuditEvent.target_key == target)

    stmt = stmt.offset(offset).limit(limit)

    rows_res = await session.execute(stmt)
    rows = list(rows_res.scalars().all())

    # Count total matching rows
    from sqlalchemy import func

    count_res = await session.execute(
        select(func.count()).select_from(count_stmt.subquery())
    )
    total: int = count_res.scalar_one()

    entries = [
        {
            "timestamp": row.created_at.isoformat() if row.created_at else "",
            "action": row.action,
            "scope": row.scope or "",
            "target": row.target_key or "",
            "actor": row.actor,
            "diff_summary": row.summary or "",
            "diff": {
                "before": row.before_json,
                "after": row.after_json,
            },
        }
        for row in rows
    ]

    return {"entries": entries, "total": total}
