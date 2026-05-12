"""Phase 4 — Ticket 1: Add draft lifecycle columns to config_layer.

Extends config_layer with:
  - parent_layer_id       : FK to config_layer (draft parent)
  - created_from_layer_id : FK to config_layer (creation source)
  - published_from_layer_id: FK to config_layer (promotion source)
  - draft_name            : human-readable name for the draft
  - draft_summary         : change description
  - published_at / published_by
  - archived_at / archived_by / archive_reason
  - rejected_at / rejected_by / rejection_reason
  - New status values: candidate, rejected (enforced at application level)
  - New index on status and parent_layer_id

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # Draft provenance
    op.add_column(
        "config_layer",
        sa.Column("parent_layer_id", sa.Integer, nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("created_from_layer_id", sa.Integer, nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("published_from_layer_id", sa.Integer, nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("draft_name", sa.String(255), nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("draft_summary", sa.Text, nullable=True),
    )

    # Promotion metadata
    op.add_column(
        "config_layer",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("published_by", sa.String(255), nullable=True),
    )

    # Archive metadata
    op.add_column(
        "config_layer",
        sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("archived_by", sa.String(255), nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("archive_reason", sa.Text, nullable=True),
    )

    # Rejection metadata
    op.add_column(
        "config_layer",
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("rejected_by", sa.String(255), nullable=True),
    )
    op.add_column(
        "config_layer",
        sa.Column("rejection_reason", sa.Text, nullable=True),
    )

    # Indexes
    op.create_index("ix_config_layer_status", "config_layer", ["status"])
    op.create_index("ix_config_layer_parent_id", "config_layer", ["parent_layer_id"])


def downgrade() -> None:
    op.drop_index("ix_config_layer_parent_id", table_name="config_layer")
    op.drop_index("ix_config_layer_status", table_name="config_layer")

    for col in (
        "rejection_reason",
        "rejected_by",
        "rejected_at",
        "archive_reason",
        "archived_by",
        "archived_at",
        "published_by",
        "published_at",
        "draft_summary",
        "draft_name",
        "published_from_layer_id",
        "created_from_layer_id",
        "parent_layer_id",
    ):
        op.drop_column("config_layer", col)
