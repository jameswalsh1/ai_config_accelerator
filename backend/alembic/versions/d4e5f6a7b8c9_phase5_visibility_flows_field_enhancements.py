"""Phase 5 — Visibility rules, wizard flows, and field enhancements.

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-05-12 00:00:00.000000

Phase 5A: visibility_rule, visibility_rule_override tables
Phase 5B: wizard_flow, wizard_flow_step tables
Phase 5C: attributes_json column on config_field
Phase 5D: field_id FK column on user_config_revision_value
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4e5f6a7b8c9"
down_revision: Union[str, None] = "c3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Phase 5A — Visibility rules
    # ------------------------------------------------------------------
    op.create_table(
        "visibility_rule",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schema_id", sa.Integer(), nullable=False),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_step_key", sa.String(100), nullable=False),
        sa.Column("target_field_path", sa.String(500), nullable=True),
        sa.Column("depends_on_field_path", sa.String(500), nullable=False),
        sa.Column("operator", sa.String(20), nullable=False, server_default="equals"),
        sa.Column("value_json", sa.JSON(), nullable=True),
        sa.Column("action", sa.String(10), nullable=False, server_default="show"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        # Audit columns
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["schema_id"], ["config_schema.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_visibility_rule_schema_id", "visibility_rule", ["schema_id"])
    op.create_index("ix_visibility_rule_target_step", "visibility_rule", ["target_step_key"])
    op.create_index("ix_visibility_rule_depends_on", "visibility_rule", ["depends_on_field_path"])

    op.create_table(
        "visibility_rule_override",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("layer_id", sa.Integer(), nullable=False),
        sa.Column("rule_id", sa.Integer(), nullable=False),
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("override_value_json", sa.JSON(), nullable=True),
        # Audit columns
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["layer_id"], ["config_layer.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_id"], ["visibility_rule.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("layer_id", "rule_id", name="uq_visibility_override_layer_rule"),
    )
    op.create_index("ix_visibility_override_layer_id", "visibility_rule_override", ["layer_id"])
    op.create_index("ix_visibility_override_rule_id", "visibility_rule_override", ["rule_id"])

    # ------------------------------------------------------------------
    # Phase 5B — Wizard flows
    # ------------------------------------------------------------------
    op.create_table(
        "wizard_flow",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("owner_actor", sa.String(255), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("source_schema_id", sa.Integer(), nullable=True),
        sa.Column("source_tool_id", sa.Integer(), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        # Audit columns
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["source_schema_id"], ["config_schema.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_tool_id"], ["ai_tool.id"], ondelete="SET NULL"),
    )
    op.create_index("ix_wizard_flow_owner", "wizard_flow", ["owner_actor"])
    op.create_index("ix_wizard_flow_status", "wizard_flow", ["status"])
    op.create_index("ix_wizard_flow_tool", "wizard_flow", ["source_tool_id"])

    op.create_table(
        "wizard_flow_step",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("flow_id", sa.Integer(), nullable=False),
        sa.Column("step_key", sa.String(100), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("custom_title", sa.String(255), nullable=True),
        sa.Column("custom_description", sa.Text(), nullable=True),
        # Audit columns
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_by", sa.String(255), nullable=False, server_default="system"),
        sa.Column("updated_by", sa.String(255), nullable=False, server_default="system"),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["flow_id"], ["wizard_flow.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("flow_id", "step_key", name="uq_flow_step_key"),
        sa.UniqueConstraint("flow_id", "position", name="uq_flow_step_position"),
    )
    op.create_index("ix_flow_step_flow_id", "wizard_flow_step", ["flow_id"])
    op.create_index("ix_flow_step_key", "wizard_flow_step", ["step_key"])

    # ------------------------------------------------------------------
    # Phase 5C — Extensible attributes column on config_field
    # ------------------------------------------------------------------
    op.add_column("config_field", sa.Column("attributes_json", sa.JSON(), nullable=True))

    # ------------------------------------------------------------------
    # Phase 5D — field_id FK on user_config_revision_value
    # ------------------------------------------------------------------
    op.add_column(
        "user_config_revision_value",
        sa.Column("field_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_revision_value_field_id",
        "user_config_revision_value",
        "config_field",
        ["field_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_revision_value_field_id",
        "user_config_revision_value",
        ["field_id"],
    )


def downgrade() -> None:
    # Phase 5D
    op.drop_index("ix_revision_value_field_id", table_name="user_config_revision_value")
    op.drop_constraint("fk_revision_value_field_id", "user_config_revision_value", type_="foreignkey")
    op.drop_column("user_config_revision_value", "field_id")

    # Phase 5C
    op.drop_column("config_field", "attributes_json")

    # Phase 5B
    op.drop_index("ix_flow_step_key", table_name="wizard_flow_step")
    op.drop_index("ix_flow_step_flow_id", table_name="wizard_flow_step")
    op.drop_table("wizard_flow_step")
    op.drop_index("ix_wizard_flow_tool", table_name="wizard_flow")
    op.drop_index("ix_wizard_flow_status", table_name="wizard_flow")
    op.drop_index("ix_wizard_flow_owner", table_name="wizard_flow")
    op.drop_table("wizard_flow")

    # Phase 5A
    op.drop_index("ix_visibility_override_rule_id", table_name="visibility_rule_override")
    op.drop_index("ix_visibility_override_layer_id", table_name="visibility_rule_override")
    op.drop_table("visibility_rule_override")
    op.drop_index("ix_visibility_rule_depends_on", table_name="visibility_rule")
    op.drop_index("ix_visibility_rule_target_step", table_name="visibility_rule")
    op.drop_index("ix_visibility_rule_schema_id", table_name="visibility_rule")
    op.drop_table("visibility_rule")
