"""Phase 6 — Schema integrity improvements.

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-05-12 00:00:00.000000

Changes:
  - Drop redundant created_from_layer_id column from config_layer
  - Widen user_config_revision_value.field_path from VARCHAR(255) to VARCHAR(500)
  - Add composite index (tool_id, language_id, status) on config_layer
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, None] = "d4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # 1. Drop redundant created_from_layer_id column
    # ------------------------------------------------------------------
    op.drop_column("config_layer", "created_from_layer_id")

    # ------------------------------------------------------------------
    # 2. Widen field_path on user_config_revision_value
    # ------------------------------------------------------------------
    op.alter_column(
        "user_config_revision_value",
        "field_path",
        existing_type=sa.String(255),
        type_=sa.String(500),
        existing_nullable=False,
    )

    # ------------------------------------------------------------------
    # 3. Add composite index for layer resolution queries
    # ------------------------------------------------------------------
    op.create_index(
        "ix_config_layer_tool_lang_status",
        "config_layer",
        ["tool_id", "language_id", "status"],
    )


def downgrade() -> None:
    # Reverse composite index
    op.drop_index("ix_config_layer_tool_lang_status", table_name="config_layer")

    # Reverse field_path widening
    op.alter_column(
        "user_config_revision_value",
        "field_path",
        existing_type=sa.String(500),
        type_=sa.String(255),
        existing_nullable=False,
    )

    # Reverse column drop — re-add created_from_layer_id
    op.add_column(
        "config_layer",
        sa.Column("created_from_layer_id", sa.Integer(), nullable=True),
    )
