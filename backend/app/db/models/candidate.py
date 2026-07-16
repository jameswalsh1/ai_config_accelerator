"""Phase 4 — Ticket 17: Template candidate model.

A template candidate represents a personal saved revision (UserConfigRevision)
submitted by an actor for consideration as a shared configuration template.

The review workflow:
  submitted  → accepted  → creates draft config layer (Ticket 21)
  submitted  → rejected
  submitted  → withdrawn (by submitter)

Candidates are separate from shared config layers.  An accepted candidate
becomes a *draft* layer — it does not directly modify active configuration.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.mixins import AuditMixin

# Valid status values
CANDIDATE_STATUS_VALUES = ("submitted", "accepted", "rejected", "withdrawn")


class TemplateCandidate(AuditMixin, Base):
    """A submitted personal revision awaiting review for shared config inclusion.

    ``source_revision_id``  : The UserConfigRevision being proposed.
    ``submitted_by``        : Actor string who submitted the candidate.
    ``target_layer_type``   : What kind of layer should be created (tool/language/combo).
    ``status``              : submitted | accepted | rejected | withdrawn
    ``resulting_layer_id``  : Set when accepted — points to the draft layer created.
    """

    __tablename__ = "template_candidate"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)

    source_revision_id: Mapped[int] = mapped_column(
        ForeignKey("user_config_revision.id", ondelete="CASCADE"), nullable=False
    )
    submitted_by: Mapped[str] = mapped_column(String(255), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    # Target layer context
    target_layer_type: Mapped[str] = mapped_column(String(20), nullable=False)
    target_tool_id: Mapped[int | None] = mapped_column(
        ForeignKey("ai_tool.id", ondelete="SET NULL"), nullable=True
    )
    target_language_id: Mapped[int | None] = mapped_column(
        ForeignKey("language.id", ondelete="SET NULL"), nullable=True
    )

    # Lifecycle
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="submitted"
    )

    # Review metadata
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Result — set when accepted and draft layer created
    resulting_layer_id: Mapped[int | None] = mapped_column(
        ForeignKey("config_layer.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    source_revision: Mapped["UserConfigRevision"] = relationship(
        "UserConfigRevision", foreign_keys=[source_revision_id], lazy="select"
    )

    __table_args__ = (
        Index("ix_candidate_submitted_by", "submitted_by"),
        Index("ix_candidate_status", "status"),
        Index("ix_candidate_source_revision_id", "source_revision_id"),
        Index("ix_candidate_target_tool_id", "target_tool_id"),
        Index("ix_candidate_target_language_id", "target_language_id"),
    )

    def __repr__(self) -> str:
        return (
            f"<TemplateCandidate id={self.id} status={self.status!r} "
            f"submitted_by={self.submitted_by!r}>"
        )


# Avoid circular import — import here after model is defined
from app.db.models.revision import UserConfigRevision  # noqa: E402, F401
