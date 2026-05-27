"""ORM models for config layers and overrides (Tickets 5, 6, 7, 8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
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

# Valid values — validated in application code, not as DB constraints
LAYER_TYPE_VALUES = ("tool", "language", "combo")
# Phase 4 adds candidate and rejected to the lifecycle
LAYER_STATUS_VALUES = ("draft", "active", "archived", "candidate", "rejected")
MERGE_MODE_VALUES = ("append", "merge_by_label", "replace")
EDITABILITY_VALUES = ("free", "locked", "suggested", "defaulted")

# ---------------------------------------------------------------------------
# Ticket 5 — Config Layer (Phase 4: lifecycle columns added)
# ---------------------------------------------------------------------------


class ConfigLayer(AuditMixin, Base):
    """An override layer (tool / language / combo).

    layer_type: tool | language | combo
    status:     draft | active | archived | candidate | rejected

    Phase 4 lifecycle columns
    -------------------------
    parent_layer_id        : The layer this draft was cloned from (active layer).
    published_from_layer_id: The draft layer that was promoted to create this active layer.
    draft_name             : Human-readable name for the draft (optional).
    draft_summary          : Description of what the draft changes.
    published_at           : UTC timestamp when this draft was promoted to active.
    published_by           : Actor who promoted this draft.
    archived_at            : UTC timestamp when this layer was archived.
    archived_by            : Actor who archived this layer.
    archive_reason         : Reason provided when archiving.
    rejected_at            : UTC timestamp when this candidate was rejected.
    rejected_by            : Actor who rejected this candidate.
    rejection_reason       : Reason provided when rejecting.
    """

    __tablename__ = "config_layer"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    layer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    layer_key: Mapped[str] = mapped_column(String(200), nullable=False)
    tool_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_tool.id", ondelete="SET NULL"), nullable=True
    )
    language_id: Mapped[int | None] = mapped_column(
        ForeignKey("language.id", ondelete="SET NULL"), nullable=True
    )
    version: Mapped[str] = mapped_column(String(50), nullable=False, default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")
    metadata_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    applies_to_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # ------------------------------------------------------------------
    # Phase 4 — Draft lifecycle provenance columns
    # ------------------------------------------------------------------
    parent_layer_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_layer.id", ondelete="SET NULL"), nullable=True
    )
    published_from_layer_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_layer.id", ondelete="SET NULL"), nullable=True
    )
    draft_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    draft_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Promotion metadata
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    published_by: Mapped[str | None] = mapped_column(String(255), nullable=True)

    # Archive metadata
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    archived_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    archive_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Rejection metadata (for candidate layers)
    rejected_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    rejected_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    step_overrides: Mapped[list[ConfigStepOverride]] = relationship(
        "ConfigStepOverride",
        back_populates="layer",
        cascade="all, delete-orphan",
    )
    field_metadata_overrides: Mapped[list[ConfigFieldMetadataOverride]] = relationship(
        "ConfigFieldMetadataOverride",
        back_populates="layer",
        cascade="all, delete-orphan",
    )
    field_content_overrides: Mapped[list[ConfigFieldContentOverride]] = relationship(
        "ConfigFieldContentOverride",
        back_populates="layer",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        UniqueConstraint(
            "layer_type", "tool_id", "language_id", "version",
            name="uq_config_layer_type_tool_lang_ver",
        ),
        Index("ix_config_layer_key", "layer_key"),
        Index("ix_config_layer_type", "layer_type"),
        Index("ix_config_layer_tool_id", "tool_id"),
        Index("ix_config_layer_lang_id", "language_id"),
        Index("ix_config_layer_status", "status"),
        Index("ix_config_layer_parent_id", "parent_layer_id"),
        Index("ix_config_layer_tool_lang_status", "tool_id", "language_id", "status"),
    )

    def __repr__(self) -> str:
        return f"<ConfigLayer id={self.id} layer_key={self.layer_key!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# Ticket 6 — Config Step Override
# ---------------------------------------------------------------------------


class ConfigStepOverride(AuditMixin, Base):
    """Step-level override in a config layer."""

    __tablename__ = "config_step_override"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    layer_id: Mapped[int] = mapped_column(
        ForeignKey("config_layer.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[int] = mapped_column(
        ForeignKey("config_step.id", ondelete="CASCADE"), nullable=False
    )
    hidden: Mapped[bool | None] = mapped_column(nullable=True)
    title_override: Mapped[str | None] = mapped_column(String(255), nullable=True)
    description_override: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint_override: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    layer: Mapped[ConfigLayer] = relationship("ConfigLayer", back_populates="step_overrides")

    __table_args__ = (
        UniqueConstraint("layer_id", "step_id", name="uq_step_override_layer_step"),
        Index("ix_step_override_layer_id", "layer_id"),
        Index("ix_step_override_step_id", "step_id"),
    )

    def __repr__(self) -> str:
        return f"<ConfigStepOverride id={self.id} layer_id={self.layer_id} step_id={self.step_id}>"


# ---------------------------------------------------------------------------
# Ticket 7 — Config Field Metadata Override
# ---------------------------------------------------------------------------


class ConfigFieldMetadataOverride(AuditMixin, Base):
    """Field metadata override in a config layer.

    editability: free | locked | suggested | defaulted
    """

    __tablename__ = "config_field_metadata_override"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    layer_id: Mapped[int] = mapped_column(
        ForeignKey("config_layer.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[int] = mapped_column(
        ForeignKey("config_field.id", ondelete="CASCADE"), nullable=False
    )
    default_value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    editability: Mapped[str | None] = mapped_column(String(20), nullable=True)
    required: Mapped[bool | None] = mapped_column(nullable=True)
    hidden: Mapped[bool | None] = mapped_column(nullable=True)
    lock_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    layer: Mapped[ConfigLayer] = relationship(
        "ConfigLayer", back_populates="field_metadata_overrides"
    )

    __table_args__ = (
        UniqueConstraint(
            "layer_id", "field_id", name="uq_field_meta_override_layer_field"
        ),
        Index("ix_field_meta_override_layer_id", "layer_id"),
        Index("ix_field_meta_override_field_id", "field_id"),
    )

    def __repr__(self) -> str:
        return f"<ConfigFieldMetadataOverride id={self.id} field_id={self.field_id}>"


# ---------------------------------------------------------------------------
# Ticket 8 — Config Field Content Override
# ---------------------------------------------------------------------------


class ConfigFieldContentOverride(AuditMixin, Base):
    """Field content (options/presets) override in a config layer.

    merge_mode: append | merge_by_label | replace
    """

    __tablename__ = "config_field_content_override"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    layer_id: Mapped[int] = mapped_column(
        ForeignKey("config_layer.id", ondelete="CASCADE"), nullable=False
    )
    field_id: Mapped[int] = mapped_column(
        ForeignKey("config_field.id", ondelete="CASCADE"), nullable=False
    )
    replace_options_with_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    merge_options_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    replace_presets_with_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    merge_presets_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    preset_files_to_add_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    merge_mode: Mapped[str] = mapped_column(
        String(20), nullable=False, default="append"
    )

    # Relationships
    layer: Mapped[ConfigLayer] = relationship(
        "ConfigLayer", back_populates="field_content_overrides"
    )

    __table_args__ = (
        UniqueConstraint(
            "layer_id", "field_id", name="uq_field_content_override_layer_field"
        ),
        Index("ix_field_content_override_layer_id", "layer_id"),
        Index("ix_field_content_override_field_id", "field_id"),
    )

    def __repr__(self) -> str:
        return f"<ConfigFieldContentOverride id={self.id} field_id={self.field_id}>"
