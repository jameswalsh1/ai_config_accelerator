"""ORM models for database-backed audit and version records (Ticket 9)."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ConfigAuditEvent(Base):
    """Database-backed audit event record.

    These will receive writes in a later phase when DB config mutations land.
    For Phase 2, the table exists so the schema is ready.
    """

    __tablename__ = "config_audit_event"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    action: Mapped[str] = mapped_column(String(100), nullable=False)
    scope: Mapped[str | None] = mapped_column(String(50), nullable=True)
    target_key: Mapped[str | None] = mapped_column(String(255), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    before_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    after_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    __table_args__ = (
        Index("ix_audit_event_scope", "scope"),
        Index("ix_audit_event_target_key", "target_key"),
        Index("ix_audit_event_created_at", "created_at"),
        Index("ix_audit_event_actor", "actor"),
    )

    def __repr__(self) -> str:
        return f"<ConfigAuditEvent id={self.id} action={self.action!r}>"


class ConfigVersion(Base):
    """Database-backed config version snapshot.

    Replaces the JSON file history in a future phase.
    """

    __tablename__ = "config_version"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(String(50), nullable=False)
    target_key: Mapped[str] = mapped_column(String(255), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(255), nullable=False, default="system")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    data_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=_utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint(
            "scope", "target_key", "version_number",
            name="uq_config_version_scope_target_ver",
        ),
        Index("ix_config_version_scope", "scope"),
        Index("ix_config_version_target_key", "target_key"),
        Index("ix_config_version_created_at", "created_at"),
    )

    def __repr__(self) -> str:
        return (
            f"<ConfigVersion id={self.id} scope={self.scope!r} "
            f"target={self.target_key!r} v={self.version_number}>"
        )
