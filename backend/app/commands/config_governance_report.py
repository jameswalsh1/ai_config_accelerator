"""Phase 4 — Ticket 23: Governance activity report command.

Generates a summary of recent governance activity including:
  - Drafts created
  - Drafts promoted
  - Drafts archived
  - Template candidates submitted
  - Candidates accepted
  - Candidates rejected
  - Personal revisions created
  - Top actors
  - Recent active layer changes

Usage
-----
    python -m app.commands.config_governance_report [--days N] [--json]
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def generate_report(
    session: AsyncSession,
    since: datetime,
) -> dict[str, Any]:
    """Generate the governance activity report for events after ``since``."""
    from app.db.models.audit import ConfigAuditEvent
    from app.db.models.candidate import TemplateCandidate
    from app.db.models.layer import ConfigLayer
    from app.db.models.revision import UserConfigRevision

    # -----------------------------------------------------------------------
    # Draft activity from audit events
    # -----------------------------------------------------------------------

    async def _count_audit(action: str) -> int:
        res = await session.execute(
            select(func.count()).select_from(ConfigAuditEvent).where(
                ConfigAuditEvent.action == action,
                ConfigAuditEvent.created_at >= since,
            )
        )
        return res.scalar_one()

    drafts_created = await _count_audit("layer_draft_created")
    drafts_promoted = await _count_audit("layer_promoted")
    drafts_archived_audit = await _count_audit("layer_archived")

    # Direct query for layer status changes since ``since``
    archived_layers_res = await session.execute(
        select(func.count()).select_from(ConfigLayer).where(
            ConfigLayer.status == "archived",
            ConfigLayer.archived_at >= since,
        )
    )
    drafts_archived = archived_layers_res.scalar_one()

    # -----------------------------------------------------------------------
    # Candidate activity
    # -----------------------------------------------------------------------

    async def _count_candidates(status: str) -> int:
        res = await session.execute(
            select(func.count()).select_from(TemplateCandidate).where(
                TemplateCandidate.status == status,
                TemplateCandidate.created_at >= since,
            )
        )
        return res.scalar_one()

    candidates_submitted = await _count_candidates("submitted")

    accepted_res = await session.execute(
        select(func.count()).select_from(TemplateCandidate).where(
            TemplateCandidate.reviewed_at >= since,
            TemplateCandidate.status == "accepted",
        )
    )
    candidates_accepted = accepted_res.scalar_one()

    rejected_res = await session.execute(
        select(func.count()).select_from(TemplateCandidate).where(
            TemplateCandidate.reviewed_at >= since,
            TemplateCandidate.status == "rejected",
        )
    )
    candidates_rejected = rejected_res.scalar_one()

    # -----------------------------------------------------------------------
    # Personal revisions
    # -----------------------------------------------------------------------

    revisions_created_res = await session.execute(
        select(func.count()).select_from(UserConfigRevision).where(
            UserConfigRevision.created_at >= since
        )
    )
    revisions_created = revisions_created_res.scalar_one()

    # -----------------------------------------------------------------------
    # Top actors from audit events
    # -----------------------------------------------------------------------

    actor_res = await session.execute(
        select(ConfigAuditEvent.actor, func.count().label("event_count"))
        .where(ConfigAuditEvent.created_at >= since)
        .group_by(ConfigAuditEvent.actor)
        .order_by(func.count().desc())
        .limit(10)
    )
    top_actors = [
        {"actor": row[0], "event_count": row[1]} for row in actor_res
    ]

    # -----------------------------------------------------------------------
    # Recent active layer changes
    # -----------------------------------------------------------------------

    active_changes_res = await session.execute(
        select(ConfigAuditEvent).where(
            ConfigAuditEvent.action == "layer_promoted",
            ConfigAuditEvent.created_at >= since,
        ).order_by(ConfigAuditEvent.created_at.desc()).limit(20)
    )
    recent_active_changes = [
        {
            "at": e.created_at.isoformat(),
            "actor": e.actor,
            "scope": e.scope,
            "target": e.target_key,
            "summary": e.summary,
        }
        for e in active_changes_res.scalars().all()
    ]

    return {
        "report_generated_at": datetime.now(timezone.utc).isoformat(),
        "since": since.isoformat(),
        "drafts": {
            "created": drafts_created,
            "promoted": drafts_promoted,
            "archived": drafts_archived,
        },
        "candidates": {
            "submitted": candidates_submitted,
            "accepted": candidates_accepted,
            "rejected": candidates_rejected,
        },
        "personal_revisions": {
            "created": revisions_created,
        },
        "top_actors": top_actors,
        "recent_active_layer_changes": recent_active_changes,
    }


async def _main(days: int, *, as_json: bool, database_url: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(days=days)
    engine = create_async_engine(database_url, echo=False)
    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
        engine, expire_on_commit=False
    )
    async with factory() as session:
        report = await generate_report(session, since)

    if as_json:
        print(json.dumps(report, indent=2))
    else:
        print(f"Governance Activity Report — last {days} day(s)")
        print(f"Generated: {report['report_generated_at']}")
        print(f"Since:     {report['since']}")
        print()
        print("Drafts:")
        for k, v in report["drafts"].items():
            print(f"  {k}: {v}")
        print()
        print("Template Candidates:")
        for k, v in report["candidates"].items():
            print(f"  {k}: {v}")
        print()
        print("Personal Revisions:")
        for k, v in report["personal_revisions"].items():
            print(f"  {k}: {v}")
        print()
        print("Top Actors:")
        for a in report["top_actors"]:
            print(f"  {a['actor']}: {a['event_count']} event(s)")
        print()
        print("Recent Active Layer Changes:")
        for c in report["recent_active_layer_changes"]:
            print(f"  [{c['at']}] {c['actor']}: {c['summary']}")

    return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate an AI Accelerator governance activity report."
    )
    parser.add_argument(
        "--days",
        type=int,
        default=30,
        help="Number of days to include in the report (default: 30)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="as_json",
        help="Output report as JSON",
    )
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy async database URL (default: DATABASE_URL env var)",
    )
    return parser


if __name__ == "__main__":
    import os

    args = _build_parser().parse_args()
    db_url = args.database_url or os.environ.get("DATABASE_URL")
    if not db_url:
        print(
            "ERROR: No database URL provided. Use --database-url or set DATABASE_URL env var.",
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(asyncio.run(_main(args.days, as_json=args.as_json, database_url=db_url)))
