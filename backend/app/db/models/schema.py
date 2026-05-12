"""ORM models for config schema, steps, and fields (Tickets 2, 3, 4)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

# ---------------------------------------------------------------------------
# Ticket 2 — Config Schema
# ---------------------------------------------------------------------------

# Valid status values for ConfigSchema
SCHEMA_STATUS_VALUES = ("draft", "active", "archived")


class ConfigSchema(AuditMixin, Base):
    """Represents an imported version of schema.json.

    status values: draft | active | archived
    """

    __tablename__ = "config_schema"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schema_version: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft")
    source_checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_path: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships (back-populated by children)
    steps: Mapped[list[ConfigStep]] = relationship(
        "ConfigStep",
        back_populates="schema",
        order_by="ConfigStep.position",
        cascade="all, delete-orphan",
    )
    fields: Mapped[list[ConfigField]] = relationship(
        "ConfigField",
        back_populates="schema",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_config_schema_version", "schema_version"),
        Index("ix_config_schema_status", "status"),
    )

    def __repr__(self) -> str:
        return f"<ConfigSchema id={self.id} version={self.schema_version!r} status={self.status!r}>"


# ---------------------------------------------------------------------------
# Ticket 3 — Config Step
# ---------------------------------------------------------------------------

# Valid scope values
STEP_SCOPE_VALUES = ("global", "tool_specific")


class ConfigStep(AuditMixin, Base):
    """A wizard step belonging to a ConfigSchema.

    scope values: global | tool_specific
    """

    __tablename__ = "config_step"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schema_id: Mapped[int] = mapped_column(
        ForeignKey("config_schema.id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    output_file: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    output_format: Mapped[str] = mapped_column(String(50), nullable=False, default="text")
    supported_surfaces_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    scope: Mapped[str] = mapped_column(String(20), nullable=False, default="global")
    tool_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_tool.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    schema: Mapped[ConfigSchema] = relationship("ConfigSchema", back_populates="steps")
    fields: Mapped[list[ConfigField]] = relationship(
        "ConfigField",
        primaryjoin="and_(ConfigField.step_id == ConfigStep.id, ConfigField.parent_field_id == None)",
        back_populates="step",
        order_by="ConfigField.position",
        cascade="all, delete-orphan",
        foreign_keys="[ConfigField.step_id]",
    )

    __table_args__ = (
        UniqueConstraint("schema_id", "step_key", name="uq_config_step_schema_key"),
        Index("ix_config_step_schema_id", "schema_id"),
        Index("ix_config_step_key", "step_key"),
    )

    def __repr__(self) -> str:
        return f"<ConfigStep id={self.id} step_key={self.step_key!r} pos={self.position}>"


# ---------------------------------------------------------------------------
# Ticket 4 — Config Field (with nested field support via self-referential FK)
# ---------------------------------------------------------------------------


class ConfigField(AuditMixin, Base):
    """A field within a wizard step.

    Nested fields (e.g. rule_files.rules.rule_file_name) use a self-referential
    parent_field_id relationship.  field_path stores the full dot-separated path
    (step_key.field_key or step_key.parent_key.field_key …).
    """

    __tablename__ = "config_field"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schema_id: Mapped[int] = mapped_column(
        ForeignKey("config_schema.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[int] = mapped_column(
        ForeignKey("config_step.id", ondelete="CASCADE"), nullable=False
    )
    parent_field_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_field.id", ondelete="CASCADE"), nullable=True
    )

    field_key: Mapped[str] = mapped_column(String(100), nullable=False)
    field_path: Mapped[str] = mapped_column(String(500), nullable=False)
    field_type: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    placeholder: Mapped[str | None] = mapped_column(Text, nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    default_value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    editability: Mapped[str] = mapped_column(String(20), nullable=False, default="free")
    locked_value: Mapped[Any] = mapped_column(JSON, nullable=True)
    render: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    hidden: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    options_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    presets_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    preset_files_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    screen_hint: Mapped[str | None] = mapped_column(Text, nullable=True)
    frontmatter: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    frontmatter_key: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tag_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    validation_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    agent_config_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    schema: Mapped[ConfigSchema] = relationship("ConfigSchema", back_populates="fields")
    step: Mapped[ConfigStep] = relationship(
        "ConfigStep",
        back_populates="fields",
        foreign_keys=[step_id],
    )
    parent: Mapped[ConfigField | None] = relationship(
        "ConfigField",
        remote_side="ConfigField.id",
        back_populates="children",
        foreign_keys=[parent_field_id],
    )
    children: Mapped[list[ConfigField]] = relationship(
        "ConfigField",
        back_populates="parent",
        order_by="ConfigField.position",
        cascade="all, delete-orphan",
        foreign_keys=[parent_field_id],
    )

    __table_args__ = (
        UniqueConstraint("schema_id", "field_path", name="uq_config_field_schema_path"),
        Index("ix_config_field_schema_id", "schema_id"),
        Index("ix_config_field_step_id", "step_id"),
        Index("ix_config_field_path", "field_path"),
        Index("ix_config_field_parent", "parent_field_id"),
    )

    def __repr__(self) -> str:
        return f"<ConfigField id={self.id} field_path={self.field_path!r}>"
