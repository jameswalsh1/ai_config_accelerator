"""Phase 2 — database configuration domain tables.

Creates all tables introduced in Phase 2:
    ai_tool
    language
    config_schema
    config_step
    config_field
    config_layer
    config_step_override
    config_field_metadata_override
    config_field_content_override
    config_audit_event
    config_version

Revision ID: a1b2c3d4e5f6
Revises: (none — Phase 1 had no migrations)
Create Date: 2026-05-12
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = None
branch_labels: str | tuple[str, ...] | None = None
depends_on: str | tuple[str, ...] | None = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # ai_tool
    # ------------------------------------------------------------------
    op.create_table(
        "ai_tool",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("tool_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint("tool_key", name="uq_ai_tool_key"),
    )
    op.create_index("ix_ai_tool_key", "ai_tool", ["tool_key"])

    # ------------------------------------------------------------------
    # language
    # ------------------------------------------------------------------
    op.create_table(
        "language",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("language_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.String(1000), nullable=False, server_default=""),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint("language_key", name="uq_language_key"),
    )
    op.create_index("ix_language_key", "language", ["language_key"])

    # ------------------------------------------------------------------
    # config_schema
    # ------------------------------------------------------------------
    op.create_table(
        "config_schema",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("schema_version", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("source_checksum", sa.String(64), nullable=True),
        sa.Column("source_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
    )
    op.create_index("ix_config_schema_version", "config_schema", ["schema_version"])
    op.create_index("ix_config_schema_status", "config_schema", ["status"])

    # ------------------------------------------------------------------
    # config_step
    # ------------------------------------------------------------------
    op.create_table(
        "config_step",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "schema_id",
            sa.Integer,
            sa.ForeignKey("config_schema.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("title", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("hint", sa.Text, nullable=True),
        sa.Column("output_file", sa.String(500), nullable=False, server_default=""),
        sa.Column("output_format", sa.String(50), nullable=False, server_default="text"),
        sa.Column("supported_surfaces_json", sa.JSON, nullable=True),
        sa.Column("hidden", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("scope", sa.String(20), nullable=False, server_default="global"),
        sa.Column(
            "tool_id",
            sa.Integer,
            sa.ForeignKey("ai_tool.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint("schema_id", "step_key", name="uq_config_step_schema_key"),
    )
    op.create_index("ix_config_step_schema_id", "config_step", ["schema_id"])
    op.create_index("ix_config_step_key", "config_step", ["step_key"])

    # ------------------------------------------------------------------
    # config_field
    # ------------------------------------------------------------------
    op.create_table(
        "config_field",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "schema_id",
            sa.Integer,
            sa.ForeignKey("config_schema.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            sa.Integer,
            sa.ForeignKey("config_step.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "parent_field_id",
            sa.Integer,
            sa.ForeignKey("config_field.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("field_key", sa.String(100), nullable=False),
        sa.Column("field_path", sa.String(500), nullable=False),
        sa.Column("field_type", sa.String(50), nullable=False),
        sa.Column("label", sa.String(255), nullable=False, server_default=""),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("placeholder", sa.Text, nullable=True),
        sa.Column("required", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("default_value_json", sa.JSON, nullable=True),
        sa.Column("editability", sa.String(20), nullable=False, server_default="free"),
        sa.Column("locked_value", sa.JSON, nullable=True),
        sa.Column("render", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("hidden", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("options_json", sa.JSON, nullable=True),
        sa.Column("presets_json", sa.JSON, nullable=True),
        sa.Column("preset_files_json", sa.JSON, nullable=True),
        sa.Column("screen_hint", sa.Text, nullable=True),
        sa.Column("frontmatter", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("frontmatter_key", sa.String(100), nullable=True),
        sa.Column("tag_source", sa.String(100), nullable=True),
        sa.Column("validation_json", sa.JSON, nullable=True),
        sa.Column("agent_config_json", sa.JSON, nullable=True),
        sa.Column("rows", sa.Integer, nullable=True),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint("schema_id", "field_path", name="uq_config_field_schema_path"),
    )
    op.create_index("ix_config_field_schema_id", "config_field", ["schema_id"])
    op.create_index("ix_config_field_step_id", "config_field", ["step_id"])
    op.create_index("ix_config_field_path", "config_field", ["field_path"])
    op.create_index("ix_config_field_parent", "config_field", ["parent_field_id"])

    # ------------------------------------------------------------------
    # config_layer
    # ------------------------------------------------------------------
    op.create_table(
        "config_layer",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("layer_type", sa.String(20), nullable=False),
        sa.Column("layer_key", sa.String(200), nullable=False),
        sa.Column(
            "tool_id",
            sa.Integer,
            sa.ForeignKey("ai_tool.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "language_id",
            sa.Integer,
            sa.ForeignKey("language.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("version", sa.String(50), nullable=False, server_default="1"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("metadata_json", sa.JSON, nullable=True),
        sa.Column("applies_to_json", sa.JSON, nullable=True),
        sa.Column("source_path", sa.String(500), nullable=True),
        sa.Column("source_checksum", sa.String(64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint(
            "layer_type", "tool_id", "language_id", "version",
            name="uq_config_layer_type_tool_lang_ver",
        ),
    )
    op.create_index("ix_config_layer_key", "config_layer", ["layer_key"])
    op.create_index("ix_config_layer_type", "config_layer", ["layer_type"])
    op.create_index("ix_config_layer_tool_id", "config_layer", ["tool_id"])
    op.create_index("ix_config_layer_lang_id", "config_layer", ["language_id"])

    # ------------------------------------------------------------------
    # config_step_override
    # ------------------------------------------------------------------
    op.create_table(
        "config_step_override",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "layer_id",
            sa.Integer,
            sa.ForeignKey("config_layer.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "step_id",
            sa.Integer,
            sa.ForeignKey("config_step.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("hidden", sa.Boolean, nullable=True),
        sa.Column("title_override", sa.String(255), nullable=True),
        sa.Column("description_override", sa.Text, nullable=True),
        sa.Column("hint_override", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint("layer_id", "step_id", name="uq_step_override_layer_step"),
    )
    op.create_index("ix_step_override_layer_id", "config_step_override", ["layer_id"])
    op.create_index("ix_step_override_step_id", "config_step_override", ["step_id"])

    # ------------------------------------------------------------------
    # config_field_metadata_override
    # ------------------------------------------------------------------
    op.create_table(
        "config_field_metadata_override",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "layer_id",
            sa.Integer,
            sa.ForeignKey("config_layer.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "field_id",
            sa.Integer,
            sa.ForeignKey("config_field.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("default_value_json", sa.JSON, nullable=True),
        sa.Column("editability", sa.String(20), nullable=True),
        sa.Column("required", sa.Boolean, nullable=True),
        sa.Column("hidden", sa.Boolean, nullable=True),
        sa.Column("lock_reason", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint(
            "layer_id", "field_id", name="uq_field_meta_override_layer_field"
        ),
    )
    op.create_index(
        "ix_field_meta_override_layer_id", "config_field_metadata_override", ["layer_id"]
    )
    op.create_index(
        "ix_field_meta_override_field_id", "config_field_metadata_override", ["field_id"]
    )

    # ------------------------------------------------------------------
    # config_field_content_override
    # ------------------------------------------------------------------
    op.create_table(
        "config_field_content_override",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "layer_id",
            sa.Integer,
            sa.ForeignKey("config_layer.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "field_id",
            sa.Integer,
            sa.ForeignKey("config_field.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("replace_options_with_json", sa.JSON, nullable=True),
        sa.Column("merge_options_json", sa.JSON, nullable=True),
        sa.Column("replace_presets_with_json", sa.JSON, nullable=True),
        sa.Column("merge_presets_json", sa.JSON, nullable=True),
        sa.Column("preset_files_to_add_json", sa.JSON, nullable=True),
        sa.Column("merge_mode", sa.String(20), nullable=False, server_default="append"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.UniqueConstraint(
            "layer_id", "field_id", name="uq_field_content_override_layer_field"
        ),
    )
    op.create_index(
        "ix_field_content_override_layer_id",
        "config_field_content_override",
        ["layer_id"],
    )
    op.create_index(
        "ix_field_content_override_field_id",
        "config_field_content_override",
        ["field_id"],
    )

    # ------------------------------------------------------------------
    # config_audit_event
    # ------------------------------------------------------------------
    op.create_table(
        "config_audit_event",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("actor", sa.String(255), nullable=False, server_default="system"),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("scope", sa.String(50), nullable=True),
        sa.Column("target_key", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("before_json", sa.JSON, nullable=True),
        sa.Column("after_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_audit_event_scope", "config_audit_event", ["scope"])
    op.create_index("ix_audit_event_target_key", "config_audit_event", ["target_key"])
    op.create_index("ix_audit_event_created_at", "config_audit_event", ["created_at"])
    op.create_index("ix_audit_event_actor", "config_audit_event", ["actor"])

    # ------------------------------------------------------------------
    # config_version
    # ------------------------------------------------------------------
    op.create_table(
        "config_version",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("scope", sa.String(50), nullable=False),
        sa.Column("target_key", sa.String(255), nullable=False),
        sa.Column("version_number", sa.Integer, nullable=False),
        sa.Column("actor", sa.String(255), nullable=False, server_default="system"),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("data_json", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint(
            "scope", "target_key", "version_number",
            name="uq_config_version_scope_target_ver",
        ),
    )
    op.create_index("ix_config_version_scope", "config_version", ["scope"])
    op.create_index("ix_config_version_target_key", "config_version", ["target_key"])
    op.create_index("ix_config_version_created_at", "config_version", ["created_at"])


def downgrade() -> None:
    op.drop_table("config_version")
    op.drop_table("config_audit_event")
    op.drop_table("config_field_content_override")
    op.drop_table("config_field_metadata_override")
    op.drop_table("config_step_override")
    op.drop_table("config_layer")
    op.drop_table("config_field")
    op.drop_table("config_step")
    op.drop_table("config_schema")
    op.drop_table("language")
    op.drop_table("ai_tool")
