"""Phase 4 — Ticket 12: Lightweight actor registry model.

Stores actor strings without implementing login or SSO.  This table is
populated lazily as actors perform governance actions.  It is forward-
compatible with a future SSO/RBAC integration.

The existing audit/version ``actor`` string columns remain in place and are
the primary record.  This table adds display names and provenance metadata
for governance reporting.
"""
from __future__ import annotations

from sqlalchemy import Boolean, DateTime, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.mixins import AuditMixin

# Valid source values — enforced at application level
ACTOR_SOURCE_VALUES = ("system", "header", "manual", "future_sso")


class ConfigActor(AuditMixin, Base):
    """Lightweight actor registry.

    ``actor_key`` matches the string stored in ``created_by`` / ``updated_by``
    and in audit/version records.  It is the canonical identifier.

    source
    ------
    system      : Built-in system actor (non-human automation).
    header      : Actor resolved from ``x-auth-user`` request header.
    manual      : Manually registered actor (e.g. service account).
    future_sso  : Reserved for SSO-provisioned actors (Phase N+).
    """

    __tablename__ = "config_actor"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    actor_key: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    source: Mapped[str] = mapped_column(String(50), nullable=False, default="header")
    first_seen_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_seen_at: Mapped[str | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("actor_key", name="uq_config_actor_key"),
        Index("ix_config_actor_key", "actor_key"),
        Index("ix_config_actor_source", "source"),
    )

    def __repr__(self) -> str:
        return f"<ConfigActor id={self.id} actor_key={self.actor_key!r}>"
