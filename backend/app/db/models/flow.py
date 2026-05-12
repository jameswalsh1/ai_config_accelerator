"""Phase 5B — User-level wizard flows.

A wizard flow defines a user's (or team's) preferred subset and ordering
of steps.  Flows are independent of the schema version — they reference
steps by key, so they survive schema upgrades.

Tables
------
wizard_flow      : Header record — owner, name, source context.
wizard_flow_step : Ordered step entries within a flow.
"""
from __future__ import annotations

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

# Valid status values
FLOW_STATUS_VALUES = ("active", "archived")


class WizardFlow(AuditMixin, Base):
    """A user-defined wizard step flow.

    ``owner_actor``     : Actor who owns this flow.
    ``name``            : Human-readable name.
    ``source_schema_id``: Schema this flow was created against.
    ``source_tool_id``  : Optional tool scope (null = tool-agnostic).
    ``is_default``      : If true, used when no flow is explicitly selected.
    ``status``          : active | archived
    """

    __tablename__ = "wizard_flow"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    owner_actor: Mapped[str] = mapped_column(String(255), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    source_schema_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_schema.id", ondelete="SET NULL"), nullable=True
    )
    source_tool_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_tool.id", ondelete="SET NULL"), nullable=True
    )
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active")

    # Relationships
    steps: Mapped[list[WizardFlowStep]] = relationship(
        "WizardFlowStep",
        back_populates="flow",
        order_by="WizardFlowStep.position",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_wizard_flow_owner", "owner_actor"),
        Index("ix_wizard_flow_status", "status"),
        Index("ix_wizard_flow_tool", "source_tool_id"),
    )

    def __repr__(self) -> str:
        return f"<WizardFlow id={self.id} name={self.name!r} owner={self.owner_actor!r}>"


class WizardFlowStep(AuditMixin, Base):
    """An ordered step entry within a wizard flow.

    ``step_key``          : String reference to ``config_step.step_key``.
    ``position``          : Order in this flow (0-based).
    ``is_enabled``        : Whether this step is included when flow is active.
    ``custom_title``      : Override the step title for this flow.
    ``custom_description``: Override the step description.
    """

    __tablename__ = "wizard_flow_step"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(
        ForeignKey("wizard_flow.id", ondelete="CASCADE"), nullable=False
    )
    step_key: Mapped[str] = mapped_column(String(100), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    custom_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    custom_description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Relationships
    flow: Mapped[WizardFlow] = relationship("WizardFlow", back_populates="steps")

    __table_args__ = (
        UniqueConstraint("flow_id", "step_key", name="uq_flow_step_key"),
        UniqueConstraint("flow_id", "position", name="uq_flow_step_position"),
        Index("ix_flow_step_flow_id", "flow_id"),
        Index("ix_flow_step_key", "step_key"),
    )

    def __repr__(self) -> str:
        return (
            f"<WizardFlowStep id={self.id} flow_id={self.flow_id} "
            f"step_key={self.step_key!r} pos={self.position}>"
        )
