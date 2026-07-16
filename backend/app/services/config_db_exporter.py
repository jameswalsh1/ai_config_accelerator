"""Ticket 11 — Export database configuration back to JSON.

Reconstructs the canonical JSON file structure (schema.json, tools/*.json,
languages/*.json, overrides/*.json) from the current database records.

This is the inverse of the JSON-to-DB import operation.  The export is
deterministic (sorted keys, consistent ordering) so the output is suitable
for code review and VCS diffing.

Design notes
------------
- Export does **not** mutate any database records.
- Database-internal fields (id, timestamps, checksums) are excluded unless
  they are also meaningful in the JSON format (e.g. source_path).
- Step and field ordering follows the ``position`` column.
- Override arrays match the existing JSON schema conventions understood by
  the validators and import service.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language
from app.db.models.layer import (
    ConfigFieldContentOverride,
    ConfigFieldMetadataOverride,
    ConfigLayer,
    ConfigStepOverride,
)
from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.db.models.tool import AITool


# ---------------------------------------------------------------------------
# Schema export
# ---------------------------------------------------------------------------


async def export_schema(session: AsyncSession) -> dict[str, Any]:
    """Export the active ConfigSchema to the schema.json structure."""
    schema_res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = schema_res.scalar_one_or_none()
    if schema is None:
        raise RuntimeError("No active config schema found in database")

    steps_res = await session.execute(
        select(ConfigStep)
        .where(ConfigStep.schema_id == schema.id)
        .order_by(ConfigStep.position)
    )
    steps = list(steps_res.scalars().all())

    exported_steps: list[dict[str, Any]] = []
    for step in steps:
        fields_res = await session.execute(
            select(ConfigField)
            .where(ConfigField.schema_id == schema.id, ConfigField.step_id == step.id)
            .order_by(ConfigField.position)
        )
        all_fields = list(fields_res.scalars().all())
        exported_steps.append(_export_step(step, all_fields))

    result: dict[str, Any] = {
        "schema_version": schema.schema_version,
    }
    if schema.description:
        result["description"] = schema.description
    result["steps"] = exported_steps
    return result


def _export_step(step: ConfigStep, all_fields: list[ConfigField]) -> dict[str, Any]:
    result: dict[str, Any] = {"id": step.step_key}
    if step.title:
        result["title"] = step.title
    if step.description:
        result["description"] = step.description
    if step.hint:
        result["hint"] = step.hint
    if step.output_file:
        result["output_file"] = step.output_file
    if step.output_format:
        result["output_format"] = step.output_format
    if step.hidden:
        result["hidden"] = step.hidden
    if step.scope and step.scope != "global":
        result["scope"] = step.scope
    # Supported surfaces
    if step.supported_surfaces_json:
        result["supported_surfaces"] = step.supported_surfaces_json
    # Top-level fields only
    top_level = [f for f in all_fields if f.parent_field_id is None]
    if top_level:
        result["fields"] = [
            _export_field(f, all_fields) for f in top_level
        ]
    return result


def _export_field(field: ConfigField, all_fields: list[ConfigField]) -> dict[str, Any]:
    result: dict[str, Any] = {"id": field.field_key}
    if field.field_type:
        result["type"] = field.field_type
    if field.label:
        result["label"] = field.label
    if field.description:
        result["description"] = field.description
    if field.placeholder:
        result["placeholder"] = field.placeholder
    if field.required:
        result["required"] = field.required
    if field.rows is not None:
        result["rows"] = field.rows
    if not field.render:  # default is True, skip if True
        result["render"] = field.render
    if field.hidden:
        result["hidden"] = field.hidden
    if field.frontmatter:
        result["frontmatter"] = field.frontmatter
    if field.frontmatter_key:
        result["frontmatter_key"] = field.frontmatter_key
    if field.screen_hint:
        result["screen_hint"] = field.screen_hint
    if field.tag_source:
        result["tag_source"] = field.tag_source
    if field.default_value_json is not None:
        result["default"] = field.default_value_json
    if field.options_json:
        result["options"] = field.options_json
    if field.presets_json:
        result["presets"] = field.presets_json
    if field.preset_files_json:
        result["preset_files"] = field.preset_files_json
    if field.agent_config_json:
        result["agent_config"] = field.agent_config_json
    # Children
    children = [f for f in all_fields if f.parent_field_id == field.id]
    if children:
        result["fields"] = [_export_field(c, all_fields) for c in children]
    return result


# ---------------------------------------------------------------------------
# Layer export helpers
# ---------------------------------------------------------------------------


async def _export_layer_overrides(
    session: AsyncSession,
    layer: ConfigLayer,
) -> dict[str, Any]:
    """Build the JSON override structure for a layer."""
    result: dict[str, Any] = {}

    # Step overrides
    so_res = await session.execute(
        select(ConfigStepOverride, ConfigStep.step_key)
        .join(ConfigStep, ConfigStepOverride.step_id == ConfigStep.id)
        .where(ConfigStepOverride.layer_id == layer.id)
    )
    step_overrides = []
    for so, step_key in so_res:
        entry: dict[str, Any] = {"step_id": step_key}
        if so.hidden is not None:
            entry["hidden"] = so.hidden
        if so.title_override:
            entry["title"] = so.title_override
        if so.description_override:
            entry["description"] = so.description_override
        if so.hint_override:
            entry["hint"] = so.hint_override
        step_overrides.append(entry)
    if step_overrides:
        result["step_overrides"] = step_overrides

    # Field metadata overrides
    fmo_res = await session.execute(
        select(ConfigFieldMetadataOverride, ConfigField.field_path)
        .join(ConfigField, ConfigFieldMetadataOverride.field_id == ConfigField.id)
        .where(ConfigFieldMetadataOverride.layer_id == layer.id)
    )
    metadata_overrides = []
    for fmo, field_path in fmo_res:
        entry = {"field_id": field_path}
        if fmo.default_value_json is not None:
            entry["default"] = fmo.default_value_json
        if fmo.editability:
            entry["editability"] = fmo.editability
        if fmo.required is not None:
            entry["required"] = fmo.required
        if fmo.hidden is not None:
            entry["hidden"] = fmo.hidden
        if fmo.lock_reason:
            entry["lock_reason"] = fmo.lock_reason
        metadata_overrides.append(entry)
    if metadata_overrides:
        result["metadata_overrides"] = metadata_overrides

    # Field content overrides
    fco_res = await session.execute(
        select(ConfigFieldContentOverride, ConfigField.field_path)
        .join(ConfigField, ConfigFieldContentOverride.field_id == ConfigField.id)
        .where(ConfigFieldContentOverride.layer_id == layer.id)
    )
    field_overrides = []
    for fco, field_path in fco_res:
        entry = {"field_id": field_path}
        if fco.replace_options_with_json is not None:
            entry["replace_options_with"] = fco.replace_options_with_json
        if fco.merge_options_json:
            entry["merge_options"] = fco.merge_options_json
        if fco.replace_presets_with_json is not None:
            entry["replace_presets_with"] = fco.replace_presets_with_json
        if fco.merge_presets_json:
            entry["merge_presets"] = fco.merge_presets_json
        if fco.preset_files_to_add_json:
            entry["preset_files_to_add"] = fco.preset_files_to_add_json
        if fco.merge_mode and fco.merge_mode != "append":
            entry["merge_mode"] = fco.merge_mode
        field_overrides.append(entry)
    if field_overrides:
        result["field_overrides"] = field_overrides

    return result


# ---------------------------------------------------------------------------
# Tool / language / combo layer exports
# ---------------------------------------------------------------------------


async def export_tool_layer(
    session: AsyncSession, tool_key: str
) -> dict[str, Any] | None:
    """Export a tool layer to the tools/{tool_id}.json structure."""
    tool_res = await session.execute(
        select(AITool).where(AITool.tool_key == tool_key).limit(1)
    )
    tool = tool_res.scalar_one_or_none()
    if tool is None:
        return None

    layer_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "tool",
            ConfigLayer.tool_id == tool.id,
            ConfigLayer.status == "active",
        ).limit(1)
    )
    layer = layer_res.scalar_one_or_none()
    if layer is None:
        return None

    result: dict[str, Any] = {}
    if tool.title:
        result["tool_id"] = tool.tool_key
    if layer.metadata_json:
        meta = layer.metadata_json
        if "title" in meta:
            result.setdefault("tool_metadata", {})["title"] = meta["title"]
        if "description" in meta:
            result.setdefault("tool_metadata", {})["description"] = meta["description"]

    overrides = await _export_layer_overrides(session, layer)
    result.update(overrides)
    return result


async def export_language_layer(
    session: AsyncSession, language_key: str
) -> dict[str, Any] | None:
    """Export a language layer to the languages/{language_id}.json structure."""
    lang_res = await session.execute(
        select(Language).where(Language.language_key == language_key).limit(1)
    )
    lang = lang_res.scalar_one_or_none()
    if lang is None:
        return None

    layer_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "language",
            ConfigLayer.language_id == lang.id,
            ConfigLayer.status == "active",
        ).limit(1)
    )
    layer = layer_res.scalar_one_or_none()
    if layer is None:
        return None

    result: dict[str, Any] = {
        "language_id": lang.language_key,
        "metadata": {
            "title": lang.title,
            "description": lang.description,
        },
    }
    overrides = await _export_layer_overrides(session, layer)
    result.update(overrides)
    return result


async def export_combo_layer(
    session: AsyncSession, combo_key: str
) -> dict[str, Any] | None:
    """Export a combo layer to the overrides/{tool}+{language}.json structure.

    ``combo_key`` should be in the form ``"tool+language"`` (e.g. ``"claude+python"``).
    """
    layer_key = f"override:{combo_key}"
    layer_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "combo",
            ConfigLayer.layer_key == layer_key,
            ConfigLayer.status == "active",
        ).limit(1)
    )
    layer = layer_res.scalar_one_or_none()
    if layer is None:
        return None

    result: dict[str, Any] = {"combo": combo_key}
    overrides = await _export_layer_overrides(session, layer)
    result.update(overrides)
    return result


# ---------------------------------------------------------------------------
# Full database export
# ---------------------------------------------------------------------------


async def export_all(session: AsyncSession) -> dict[str, Any]:
    """Export all active DB config to a dict keyed by target file path.

    Returns a mapping like::

        {
            "schema.json": { ... },
            "tools/claude.json": { ... },
            "languages/python.json": { ... },
            "overrides/claude+python.json": { ... },
        }
    """
    return await export_by_lifecycle(session, status="active")


async def export_by_lifecycle(
    session: AsyncSession,
    *,
    status: str = "active",
    layer_id: int | None = None,
) -> dict[str, Any]:
    """Export DB config filtered by lifecycle status or specific layer ID.

    Phase 4 — Ticket 22: Extends export to support active/draft/archived
    layer selection.

    Parameters
    ----------
    session:
        Async SQLAlchemy session (read-only).
    status:
        Layer status to export: ``"active"`` (default), ``"draft"``,
        ``"archived"``, or ``"all"`` for all statuses.
    layer_id:
        If provided, export only this specific layer (ignores ``status``).

    Returns
    -------
    A dict mapping relative file paths to their JSON content, plus optional
    ``_export_metadata`` key describing the export parameters.
    """
    result: dict[str, Any] = {}

    # Schema is always from the active schema regardless of layer status
    try:
        result["schema.json"] = await export_schema(session)
    except RuntimeError:
        pass  # No active schema — skip

    if layer_id is not None:
        # Export a single specific layer
        layer_res = await session.execute(
            select(ConfigLayer).where(ConfigLayer.id == layer_id).limit(1)
        )
        layer = layer_res.scalar_one_or_none()
        if layer is not None:
            overrides = await _export_layer_overrides(session, layer)
            rel_path = _layer_to_export_path(layer)
            result[rel_path] = overrides
        result["_export_metadata"] = {
            "export_type": "single_layer",
            "layer_id": layer_id,
            "layer_status": layer.status if layer is not None else None,
        }
        return result

    # Build status filter
    status_filter: list[str]
    if status == "all":
        status_filter = ["active", "draft", "archived", "candidate", "rejected"]
    else:
        status_filter = [status]

    # Tools
    tools_res = await session.execute(
        select(AITool).where(AITool.is_active.is_(True)).order_by(AITool.tool_key)
    )
    for tool in tools_res.scalars().all():
        layers_res = await session.execute(
            select(ConfigLayer).where(
                ConfigLayer.layer_type == "tool",
                ConfigLayer.tool_id == tool.id,
                ConfigLayer.status.in_(status_filter),
            ).order_by(ConfigLayer.id)
        )
        for layer in layers_res.scalars().all():
            overrides = await _export_layer_overrides(session, layer)
            overrides["tool_id"] = tool.tool_key
            rel_path = _layer_to_export_path(layer, tool_key=tool.tool_key)
            result[rel_path] = overrides

    # Languages
    langs_res = await session.execute(
        select(Language).where(Language.is_active.is_(True)).order_by(Language.language_key)
    )
    for lang in langs_res.scalars().all():
        layers_res = await session.execute(
            select(ConfigLayer).where(
                ConfigLayer.layer_type == "language",
                ConfigLayer.language_id == lang.id,
                ConfigLayer.status.in_(status_filter),
            ).order_by(ConfigLayer.id)
        )
        for layer in layers_res.scalars().all():
            overrides = await _export_layer_overrides(session, layer)
            overrides["language_id"] = lang.language_key
            rel_path = _layer_to_export_path(layer, language_key=lang.language_key)
            result[rel_path] = overrides

    # Combo layers
    combos_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "combo",
            ConfigLayer.status.in_(status_filter),
        ).order_by(ConfigLayer.layer_key)
    )
    for combo_layer in combos_res.scalars().all():
        overrides = await _export_layer_overrides(session, combo_layer)
        combo_key = combo_layer.layer_key.removeprefix("override:")
        overrides["combo"] = combo_key
        rel_path = _layer_to_export_path(combo_layer, combo_key=combo_key)
        result[rel_path] = overrides

    result["_export_metadata"] = {
        "export_type": "lifecycle",
        "status_filter": status,
    }
    return result


def _layer_to_export_path(
    layer: ConfigLayer,
    *,
    tool_key: str | None = None,
    language_key: str | None = None,
    combo_key: str | None = None,
) -> str:
    """Generate a relative export path for a layer, including status suffix for non-active."""
    suffix = "" if layer.status == "active" else f".{layer.status}.{layer.id}"
    if layer.layer_type == "tool" and tool_key:
        return f"tools/{tool_key}{suffix}.json"
    if layer.layer_type == "language" and language_key:
        return f"languages/{language_key}{suffix}.json"
    if combo_key:
        return f"overrides/{combo_key}{suffix}.json"
    return f"layers/layer_{layer.id}{suffix}.json"
