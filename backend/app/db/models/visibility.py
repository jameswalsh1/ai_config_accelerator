"""Phase 5A — Conditional visibility rules for steps and fields.

A visibility rule defines a condition on a field answer that controls
whether a target step or field is shown or hidden in the wizard.

Tables
------
visibility_rule          : Defines a condition + target + action.
visibility_rule_override : Layer-scoped override to disable or alter a rule.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

# Valid values — enforced at application level
RULE_TARGET_TYPES = ("step", "field")
RULE_OPERATORS = ("equals", "not_equals", "in", "not_in", "is_empty", "is_not_empty")
RULE_ACTIONS = ("show", "hide")


class VisibilityRule(AuditMixin, Base):
    """Conditional visibility rule evaluated at wizard runtime.

    ``target_type``           : Whether this rule targets a ``step`` or ``field``.
    ``target_step_key``       : Step key to show/hide (always set).
    ``target_field_path``     : Field path to show/hide (null when targeting a step).
    ``depends_on_field_path`` : The field whose current answer is evaluated.
    ``operator``              : Comparison operator (equals, in, is_empty, …).
    ``value_json``            : The comparison value(s).
    ``action``                : ``show`` or ``hide`` when condition is met.
    ``priority``              : Higher priority wins when rules conflict.
    """

    __tablename__ = "visibility_rule"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    schema_id: Mapped[int] = mapped_column(
        ForeignKey("config_schema.id", ondelete="CASCADE"), nullable=False
    )
    target_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    target_field_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    depends_on_field_path: Mapped[str] = mapped_column(String(500), nullable=False)
    operator: Mapped[str] = mapped_column(String(20), nullable=False, default="equals")
    value_json: Mapped[Any] = mapped_column(JSON, nullable=True)
    action: Mapped[str] = mapped_column(String(10), nullable=False, default="show")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # Relationships
    overrides: Mapped[list[VisibilityRuleOverride]] = relationship(
        "VisibilityRuleOverride",
        back_populates="rule",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_visibility_rule_schema_id", "schema_id"),
        Index("ix_visibility_rule_target_step", "target_step_key"),
        Index("ix_visibility_rule_depends_on", "depends_on_field_path"),
    )

    def __repr__(self) -> str:
        return (
            f"<VisibilityRule id={self.id} "
            f"target={self.target_type}:{self.target_step_key} "
            f"action={self.action!r}>"
        )


class VisibilityRuleOverride(AuditMixin, Base):
    """Layer-scoped override for a visibility rule.

    Allows a tool or language layer to disable a base rule or change
    its comparison value.
    """

    __tablename__ = "visibility_rule_override"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    layer_id: Mapped[int] = mapped_column(
        ForeignKey("config_layer.id", ondelete="CASCADE"), nullable=False
    )
    rule_id: Mapped[int] = mapped_column(
        ForeignKey("visibility_rule.id", ondelete="CASCADE"), nullable=False
    )
    is_disabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    override_value_json: Mapped[Any] = mapped_column(JSON, nullable=True)

    # Relationships
    rule: Mapped[VisibilityRule] = relationship(
        "VisibilityRule", back_populates="overrides"
    )

    __table_args__ = (
        UniqueConstraint("layer_id", "rule_id", name="uq_visibility_override_layer_rule"),
        Index("ix_visibility_override_layer_id", "layer_id"),
        Index("ix_visibility_override_rule_id", "rule_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<VisibilityRuleOverride id={self.id} "
            f"rule_id={self.rule_id} disabled={self.is_disabled}>"
        )
