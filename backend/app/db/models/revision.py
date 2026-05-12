"""Phase 4 — Ticket 13: Personal saved wizard revision models.

A personal saved revision captures the wizard answers for a specific
tool/language combination.  It is owned by an actor string (not a full user
row) and is private to that actor.

A revision can later be submitted as a template candidate (Ticket 17/18).

Tables
------
user_config_revision        : Header record — owner, name, source refs.
user_config_revision_value  : Per-field answer values (one row per field path).
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

# Valid status values
REVISION_STATUS_VALUES = ("active", "archived", "submitted")


class UserConfigRevision(AuditMixin, Base):
    """Personal saved wizard configuration revision.

    ``owner_actor``   : Actor string who owns this revision.
    ``status``        : active | archived | submitted
    ``source_*``      : References to the tool/language/schema used when
                        the revision was saved.
    """

    __tablename__ = "user_config_revision"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_actor: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Source context
    source_tool_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_tool.id", ondelete="SET NULL"), nullable=True
    )
    source_language_id: Mapped[int | None] = mapped_column(
        ForeignKey("language.id", ondelete="SET NULL"), nullable=True
    )
    source_schema_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_schema.id", ondelete="SET NULL"), nullable=True
    )
    # JSON snapshot of which layers were active when revision was saved
    source_layers_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    values: Mapped[list[UserConfigRevisionValue]] = relationship(
        "UserConfigRevisionValue",
        back_populates="revision",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_revision_owner_actor", "owner_actor"),
        Index("ix_revision_status", "status"),
        Index("ix_revision_tool_lang", "source_tool_id", "source_language_id"),
    )

    def __repr__(self) -> str:
        return f"<UserConfigRevision id={self.id} owner={self.owner_actor!r} name={self.name!r}>"


class UserConfigRevisionValue(AuditMixin, Base):
    """Per-field saved answer value within a personal revision.

    ``field_path`` uses the ``step_id.field_id`` convention established in
    the config field model.
    """

    __tablename__ = "user_config_revision_value"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    revision_id: Mapped[int] = mapped_column(
        ForeignKey("user_config_revision.id", ondelete="CASCADE"), nullable=False
    )
    field_path: Mapped[str] = mapped_column(String(500), nullable=False)
    field_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_field.id", ondelete="SET NULL"), nullable=True
    )
    value_json: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # Relationships
    revision: Mapped[UserConfigRevision] = relationship(
        "UserConfigRevision", back_populates="values"
    )

    __table_args__ = (
        UniqueConstraint(
            "revision_id", "field_path", name="uq_revision_value_path"
        ),
        Index("ix_revision_value_revision_id", "revision_id"),
        Index("ix_revision_value_field_path", "field_path"),
        Index("ix_revision_value_field_id", "field_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<UserConfigRevisionValue id={self.id} "
            f"revision_id={self.revision_id} field_path={self.field_path!r}>"
        )
