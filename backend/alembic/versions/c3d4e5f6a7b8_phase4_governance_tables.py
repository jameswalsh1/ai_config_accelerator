"""Phase 4 — Tickets 12, 13, 17: New governance tables.

Creates:
  config_actor            : Lightweight actor registry (Ticket 12)
  user_config_revision    : Personal saved wizard revisions (Ticket 13)
  user_config_revision_value : Per-field values within a revision (Ticket 13)
  template_candidate      : Submitted revision candidates (Ticket 17)

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "c3d4e5f6a7b8"
down_revision: str | None = "b2c3d4e5f6a7"
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # config_actor
    # ------------------------------------------------------------------
    op.create_table(
        "config_actor",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor_key", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("source", sa.String(50), nullable=False, server_default="header"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint("actor_key", name="uq_config_actor_key"),
    )
    op.create_index("ix_config_actor_key", "config_actor", ["actor_key"])
    op.create_index("ix_config_actor_source", "config_actor", ["source"])

    # ------------------------------------------------------------------
    # user_config_revision
    # ------------------------------------------------------------------
    op.create_table(
        "user_config_revision",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("owner_actor", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("source_tool_id", sa.Integer, sa.ForeignKey("ai_tool.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_language_id", sa.Integer, sa.ForeignKey("language.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_schema_id", sa.Integer, sa.ForeignKey("config_schema.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_layers_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
    )
    op.create_index("ix_revision_owner_actor", "user_config_revision", ["owner_actor"])
    op.create_index("ix_revision_status", "user_config_revision", ["status"])
    op.create_index("ix_revision_tool_lang", "user_config_revision", ["source_tool_id", "source_language_id"])

    # ------------------------------------------------------------------
    # user_config_revision_value
    # ------------------------------------------------------------------
    op.create_table(
        "user_config_revision_value",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("revision_id", sa.Integer, sa.ForeignKey("user_config_revision.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_path", sa.String(255), nullable=False),
        sa.Column("value_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint("revision_id", "field_path", name="uq_revision_value_path"),
    )
    op.create_index("ix_revision_value_revision_id", "user_config_revision_value", ["revision_id"])
    op.create_index("ix_revision_value_field_path", "user_config_revision_value", ["field_path"])

    # ------------------------------------------------------------------
    # template_candidate
    # ------------------------------------------------------------------
    op.create_table(
        "template_candidate",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source_revision_id", sa.Integer, sa.ForeignKey("user_config_revision.id", ondelete="CASCADE"), nullable=False),
        sa.Column("submitted_by", sa.String(255), nullable=False),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("target_layer_type", sa.String(20), nullable=False),
        sa.Column("target_tool_id", sa.Integer, sa.ForeignKey("ai_tool.id", ondelete="SET NULL"), nullable=True),
        sa.Column("target_language_id", sa.Integer, sa.ForeignKey("language.id", ondelete="SET NULL"), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="submitted"),
        sa.Column("review_notes", sa.Text, nullable=True),
        sa.Column("reviewed_by", sa.String(255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("resulting_layer_id", sa.Integer, sa.ForeignKey("config_layer.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
    )
    op.create_index("ix_candidate_submitted_by", "template_candidate", ["submitted_by"])
    op.create_index("ix_candidate_status", "template_candidate", ["status"])
    op.create_index("ix_candidate_source_revision_id", "template_candidate", ["source_revision_id"])
    op.create_index("ix_candidate_target_tool_id", "template_candidate", ["target_tool_id"])
    op.create_index("ix_candidate_target_language_id", "template_candidate", ["target_language_id"])


def downgrade() -> None:
    op.drop_table("template_candidate")
    op.drop_table("user_config_revision_value")
    op.drop_table("user_config_revision")
    op.drop_table("config_actor")
