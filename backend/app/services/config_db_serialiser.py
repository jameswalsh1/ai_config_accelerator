"""Ticket 10 — Database model serialisation helpers.

Converts ConfigField / ConfigStep / ConfigSchema ORM rows into the dict shapes
expected by the existing WizardConfig / WizardStep / WizardField Pydantic models.

These helpers are used by the database-backed config resolver so that the DB
path produces the exact same output shape as the JSON-backed path.

Design notes
------------
- Preserve field insertion order (maintained by ``position`` column).
- Reconstruct nested field trees from parent-child relationships.
- JSON column values are passed through without transformation.
- ``override_source`` is set by the resolver, not by these helpers.
"""
from __future__ import annotations

from typing import Any

from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep


# ---------------------------------------------------------------------------
# Field serialisation
# ---------------------------------------------------------------------------


def field_to_dict(field: ConfigField, children: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    """Convert a ConfigField row into the dict shape used by WizardField.

    Parameters
    ----------
    field:
        The ORM model instance.
    children:
        Pre-serialised child field dicts (for nested / repeatable_group fields).
        Pass ``None`` (or omit) for leaf fields.
    """
    result: dict[str, Any] = {
        "id": field.field_key,
        "type": field.field_type,
        "label": field.label,
    }

    # Optional scalar fields — only emit when set to avoid cluttering the dict
    if field.description is not None:
        result["description"] = field.description
    if field.placeholder is not None:
        result["placeholder"] = field.placeholder

    result["required"] = field.required

    if field.rows is not None:
        result["rows"] = field.rows

    result["render"] = field.render
    result["hidden"] = field.hidden
    result["frontmatter"] = field.frontmatter

    if field.frontmatter_key is not None:
        result["frontmatter_key"] = field.frontmatter_key

    if field.screen_hint is not None:
        result["screen_hint"] = field.screen_hint

    if field.tag_source is not None:
        result["tag_source"] = field.tag_source

    # JSON columns — pass through as-is
    if field.default_value_json is not None:
        result["default"] = field.default_value_json

    if field.options_json is not None:
        result["options"] = field.options_json

    if field.presets_json is not None:
        result["presets"] = field.presets_json

    if field.preset_files_json is not None:
        result["preset_files"] = field.preset_files_json

    if field.locked_value is not None:
        result["locked_value"] = field.locked_value

    if field.validation_json is not None:
        result["validation"] = field.validation_json

    if field.agent_config_json is not None:
        result["agent_config"] = field.agent_config_json

    # Editability
    result["editability"] = field.editability

    # Nested children
    if children:
        result["fields"] = children

    return result


def _build_field_tree(
    all_fields: list[ConfigField],
    parent_id: int | None,
) -> list[dict[str, Any]]:
    """Recursively build the field tree for fields with the given parent_id.

    Parameters
    ----------
    all_fields:
        All ConfigField rows belonging to a step, sorted by ``position``.
    parent_id:
        The parent field's database ID, or ``None`` for top-level fields.
    """
    result: list[dict[str, Any]] = []
    for field in all_fields:
        if field.parent_field_id == parent_id:
            children = _build_field_tree(all_fields, field.id)
            result.append(field_to_dict(field, children or None))
    return result


# ---------------------------------------------------------------------------
# Step serialisation
# ---------------------------------------------------------------------------


def step_to_dict(step: ConfigStep, all_fields: list[ConfigField]) -> dict[str, Any]:
    """Convert a ConfigStep row into the dict shape used by WizardStep.

    Parameters
    ----------
    step:
        The ORM model instance.
    all_fields:
        All ConfigField rows that belong to this step, sorted by ``position``.
        The function builds the nested tree internally.
    """
    # Build nested field tree (top-level fields only; children are attached recursively)
    fields = _build_field_tree(all_fields, parent_id=None)

    result: dict[str, Any] = {
        "id": step.step_key,
        "title": step.title,
        "fields": fields,
        "output_file": step.output_file,
        "output_format": step.output_format,
        "hidden": step.hidden,
    }

    if step.description is not None:
        result["description"] = step.description
    if step.hint is not None:
        result["hint"] = step.hint
    if step.supported_surfaces_json is not None:
        result["supported_surfaces"] = step.supported_surfaces_json

    return result


# ---------------------------------------------------------------------------
# Schema / full config serialisation
# ---------------------------------------------------------------------------


def schema_to_config_dict(
    schema: ConfigSchema,
    steps: list[ConfigStep],
    fields_by_step: dict[int, list[ConfigField]],
) -> dict[str, Any]:
    """Assemble the full wizard config dict from DB objects.

    Parameters
    ----------
    schema:
        The active ConfigSchema row.
    steps:
        All ConfigStep rows ordered by ``position``.
    fields_by_step:
        Mapping from step.id → list[ConfigField] (ordered by position).
    """
    serialised_steps = [
        step_to_dict(step, fields_by_step.get(step.id, []))
        for step in steps
    ]

    return {
        "schema_version": schema.schema_version,
        "description": schema.description,
        "steps": serialised_steps,
    }


# ---------------------------------------------------------------------------
# Override application helpers
# ---------------------------------------------------------------------------


def apply_step_overrides_to_dict(
    step_dict: dict[str, Any],
    overrides: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a list of step override payloads to a serialised step dict.

    Parameters
    ----------
    step_dict:
        The serialised step dict (from ``step_to_dict``).
    overrides:
        List of dicts with keys: hidden, title_override, description_override,
        hint_override.  Earlier items in the list have lower priority.
    """
    result = dict(step_dict)
    for override in overrides:
        if override.get("hidden") is not None:
            result["hidden"] = override["hidden"]
        if override.get("title_override") is not None:
            result["title"] = override["title_override"]
        if override.get("description_override") is not None:
            result["description"] = override["description_override"]
        if override.get("hint_override") is not None:
            result["hint"] = override["hint_override"]
    return result


def apply_field_metadata_override_to_dict(
    field_dict: dict[str, Any],
    override: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    """Apply a single field metadata override to a serialised field dict.

    Parameters
    ----------
    field_dict:
        Serialised field dict (from ``field_to_dict``).
    override:
        Dict with keys: default_value_json, editability, required, hidden,
        lock_reason.
    source:
        Override source label (e.g. ``"tool:claude"``).
    """
    result = dict(field_dict)
    if "default_value_json" in override and override["default_value_json"] is not None:
        result["default"] = override["default_value_json"]
    if override.get("editability") is not None:
        result["editability"] = override["editability"]
    if override.get("required") is not None:
        result["required"] = override["required"]
    if override.get("hidden") is not None:
        result["hidden"] = override["hidden"]
    if override.get("lock_reason") is not None:
        result["lock_reason"] = override["lock_reason"]
    # Track override source (first layer that sets it wins — lower-priority layers
    # may update it if a higher-priority layer hasn't touched the field)
    if "override_source" not in result or result.get("override_source") is None:
        result["override_source"] = source
    return result


def apply_field_content_override_to_dict(
    field_dict: dict[str, Any],
    override: dict[str, Any],
    source: str,
) -> dict[str, Any]:
    """Apply a single field content override to a serialised field dict.

    Parameters
    ----------
    field_dict:
        Serialised field dict.
    override:
        Dict with keys: replace_options_with_json, merge_options_json,
        replace_presets_with_json, merge_presets_json,
        preset_files_to_add_json, merge_mode.
    source:
        Override source label.
    """
    result = dict(field_dict)
    merge_mode: str = override.get("merge_mode", "append")

    if override.get("replace_options_with_json") is not None:
        result["options"] = override["replace_options_with_json"]
    elif override.get("merge_options_json") is not None:
        existing = result.get("options") or []
        result["options"] = existing + override["merge_options_json"]

    if override.get("replace_presets_with_json") is not None:
        result["presets"] = override["replace_presets_with_json"]
    elif override.get("merge_presets_json") is not None:
        existing = result.get("presets") or []
        new_presets = override["merge_presets_json"]
        if merge_mode == "merge_by_label":
            merged = list(existing)
            for new_p in new_presets:
                label = new_p.get("label")
                idx = next((i for i, p in enumerate(merged) if p.get("label") == label), None)
                if idx is not None:
                    merged[idx] = new_p
                else:
                    merged.append(new_p)
            result["presets"] = merged
        else:
            result["presets"] = existing + new_presets

    if override.get("preset_files_to_add_json") is not None:
        existing_files = result.get("preset_files") or []
        result["preset_files"] = existing_files + override["preset_files_to_add_json"]

    if "override_source" not in result or result.get("override_source") is None:
        result["override_source"] = source

    return result
