from fastapi import APIRouter, HTTPException, Query
from typing import Any, Literal, cast

from app.services.config_loader_composable import (
    load_composable_config,
    get_available_tools,
    get_available_languages,
    get_available_steps,
    get_coverage_matrix,
)
from app.services.config_editor import get_editable_step
from app.services.config_patcher import update_field_metadata, ConfigNotFoundError, add_preset_to_field, remove_preset_from_field, remove_field_override
from app.services.config_validator import validate_language_override, validate_tool_override
from app.services.config_persistence import create_language_config, get_language_tags, ValidationError as PersistenceValidationError
from app.services.audit_log import read_audit_log
from app.services.version_history import list_versions, get_version, get_version_data

router = APIRouter(prefix="/config", tags=["config"])


@router.get("/edit")
def get_editable_config_slice(
    tool: str = Query(..., description="Tool ID (e.g., 'claude', 'copilot', 'cursor')"),
    language: str = Query(..., description="Language ID (e.g., 'python', 'java', 'javascript')"),
    step_id: str = Query(..., description="Step ID to fetch editable portion for"),
) -> dict[str, Any]:
    """Get editable configuration slice for a specific step + language.

    Fetches the editable portion of config for a specific step, including:
    - All fields in the step
    - Current overrides with source tracking
    - Editability status (free, locked, suggested, defaulted)
    - Clear indication of which values are:
      * default (from schema.json)
      * overridden (from tool/language/combo layer)
      * locked (read-only)

    Response includes:
    - step: Full step definition with enhanced field metadata
    - source_tracking: Summary of override sources used

    Args:
        tool: Tool identifier (e.g., 'claude', 'copilot', 'cursor')
        language: Language identifier (e.g., 'python', 'java', 'javascript')
        step_id: Step ID to extract (e.g., 'engineering_standards', 'language_selection')

    Returns:
        Dictionary containing editable step with override metadata

    Raises:
        HTTPException 400: If tool/language/step invalid or validation fails
        HTTPException 404: If step_id not found in configuration
        HTTPException 500: For internal errors

    Example:
        GET /config/edit?tool=claude&language=python&step_id=engineering_standards

        Returns:
        {
            "step": {
                "id": "engineering_standards",
                "title": "Engineering Standards",
                "fields": [
                    {
                        "id": "coding_conventions",
                        "type": "textarea",
                        "label": "Coding Conventions",
                        "default": "PEP8",
                        "editability": "free",
                        "is_locked": false,
                        "is_default": false,
                        "override_source": "language:python",
                        "source_file": "languages/python.json",
                        "presets": [...],
                        ...
                    }
                ]
            },
            "source_tracking": {
                "total_fields": 5,
                "by_source": {
                    "schema.json": 2,
                    "tools/claude.json": 1,
                    "languages/python.json": 2
                },
                "by_editability": {"free": 4, "locked": 1},
                "locked_fields": 1,
                "default_fields": 2,
                "overridden_fields": 3
            }
        }
    """
    try:
        # Load fully resolved config
        resolved_dict = load_composable_config(tool, language)

        # Extract editable step with metadata
        result = get_editable_step(resolved_dict, step_id)

        return result
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Config not found for tool '{tool}' and language '{language}': {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading editable config: {str(e)}"
        )


@router.post("/update")
def update_field_config(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Update field configuration metadata.

    Updates the default value and editability of a specific field in an override file.
    Triggers validation of the updated configuration.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "package_manager",
            "changes": {
                "default": "uv",
                "editable": false
            }
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        # Extract and validate payload
        scope = payload.get("scope")
        target = payload.get("target")
        tool = payload.get("tool")
        language = payload.get("language")
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        changes = payload.get("changes", {})

        if not all([scope, target, tool, language, step_id, field_id]):
            raise ValueError("Missing required fields: scope, target, tool, language, step_id, field_id")

        scope_str: str = str(scope)
        target_str: str = str(target)
        tool_str: str = str(tool)
        language_str: str = str(language)
        step_id_str: str = str(step_id)
        field_id_str: str = str(field_id)

        if scope_str not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        # Transform changes: map 'editable' to 'editability'
        transformed_changes: dict[str, Any] = {}
        for key, value in changes.items():
            if key == "editable":
                # Map boolean to editability string
                transformed_changes["editability"] = "free" if value else "locked"
            else:
                transformed_changes[key] = value

        # Update the override file
        updated_config = update_field_metadata(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, transformed_changes)

        # Validate the updated config
        if scope_str == "language":
            validate_language_override(updated_config)
        elif scope_str == "tool":
            validate_tool_override(updated_config)

        # Load fully resolved config
        resolved_dict = load_composable_config(tool_str, language_str)

        # Extract editable step with metadata
        result = get_editable_step(resolved_dict, step_id_str)

        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(
            status_code=404,
            detail=f"Config file not found: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error updating config: {str(e)}"
        )


@router.post("/reset")
def reset_field_to_base(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Reset a field to its base/tool defaults by removing overrides.

    Removes the field override from the specified scope, allowing the field
    to revert to base schema or tool defaults.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "coding_conventions",
            "override_type": "metadata"  // optional, defaults to "metadata"
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        # Extract and validate payload
        scope = payload.get("scope")
        target = payload.get("target")
        tool = payload.get("tool")
        language = payload.get("language")
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        override_type = payload.get("override_type", "metadata")

        if not all([scope, target, tool, language, step_id, field_id]):
            raise ValueError("Missing required fields: scope, target, tool, language, step_id, field_id")

        scope_str: str = str(scope)
        target_str: str = str(target)
        tool_str: str = str(tool)
        language_str: str = str(language)
        step_id_str: str = str(step_id)
        field_id_str: str = str(field_id)
        override_type_str: str = str(override_type) if override_type else "metadata"

        if scope_str not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        if override_type_str not in ["metadata", "structure"]:
            raise ValueError("Invalid override_type. Must be 'metadata' or 'structure'")

        # Remove the override
        updated_config = remove_field_override(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, cast(Literal["metadata", "structure"], override_type_str))

        resolved_dict = load_composable_config(tool_str, language_str)
        result = get_editable_step(resolved_dict, step_id_str)

        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(
            status_code=404,
            detail=f"Config file not found: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error resetting field: {str(e)}"
        )


@router.post("/presets/add")
def add_preset(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Add a preset to a field.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "coding_conventions",
            "preset": {
                "label": "PEP8",
                "value": "PEP8",
                "description": "Python Enhancement Proposal 8",
                "mode": "append",
                "tags": ["python"]
            },
            "position": 0  // optional, defaults to append
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        # Extract and validate payload
        scope = payload.get("scope")
        target = payload.get("target")
        tool = payload.get("tool")
        language = payload.get("language")
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        preset = payload.get("preset")
        position = payload.get("position")

        if not all([scope, target, tool, language, step_id, field_id, preset]):
            raise ValueError("Missing required fields: scope, target, tool, language, step_id, field_id, preset")

        scope_str: str = str(scope)
        target_str: str = str(target)
        tool_str: str = str(tool)
        language_str: str = str(language)
        step_id_str: str = str(step_id)
        field_id_str: str = str(field_id)
        preset_dict: dict[str, Any] = dict(preset) if isinstance(preset, dict) else {}

        if scope_str not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        # Add the preset
        updated_config = add_preset_to_field(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, preset_dict, position)

        resolved_dict = load_composable_config(tool_str, language_str)
        result = get_editable_step(resolved_dict, step_id_str)

        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(
            status_code=404,
            detail=f"Config file not found: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error adding preset: {str(e)}"
        )


@router.post("/presets/remove")
def remove_preset(payload: dict[str, Any]) -> dict[str, Any]:
    """
    Remove a preset from a field.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "coding_conventions",
            "preset_label": "PEP8",  // optional, if not provided use position
            "position": 0  // optional, takes precedence over preset_label
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        # Extract and validate payload
        scope = payload.get("scope")
        target = payload.get("target")
        tool = payload.get("tool")
        language = payload.get("language")
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        preset_label = payload.get("preset_label")
        position = payload.get("position")

        if not all([scope, target, tool, language, step_id, field_id]):
            raise ValueError("Missing required fields: scope, target, tool, language, step_id, field_id")

        scope_str: str = str(scope)
        target_str: str = str(target)
        tool_str: str = str(tool)
        language_str: str = str(language)
        step_id_str: str = str(step_id)
        field_id_str: str = str(field_id)

        if scope_str not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        if preset_label is None and position is None:
            raise ValueError("Must specify either preset_label or position")

        # Remove the preset
        updated_config = remove_preset_from_field(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, preset_label, position)

        resolved_dict = load_composable_config(tool_str, language_str)
        result = get_editable_step(resolved_dict, step_id_str)

        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(
            status_code=404,
            detail=f"Config file not found: {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error removing preset: {str(e)}"
        )


@router.get("/tools")
def list_available_tools() -> list[dict[str, str]]:
    """Get list of available tools."""
    return get_available_tools()


@router.get("/coverage")
def get_tool_language_coverage() -> dict[str, Any]:
    """Return the tool × language coverage matrix.

    Each cell reports whether the language configuration has field overrides
    relevant to that tool's visible steps.

    Returns:
        {
            "tools":     [{"id": ..., "title": ...}, ...],
            "languages": [{"id": ..., "title": ...}, ...],
            "matrix":    { tool_id: { language_id: { "status", "field_count", "fields" } } }
        }

    Status values:
        - "full":    ≥ 2 relevant field overrides
        - "partial": exactly 1 relevant field override
        - "none":    no relevant field overrides
    """
    return get_coverage_matrix()


@router.get("/languages")
def list_available_languages() -> list[dict[str, str]]:
    """Get list of available languages."""
    return get_available_languages()


@router.post("/languages")
def create_language(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Create a new language configuration.

    The language_id is derived automatically from the title.

    Payload:
        {
            "title": "Python – Data Science",
            "description": "NumPy, pandas, PyTorch stack",
            "based_on": "python"  // optional — copy overrides from existing language
        }

    Returns:
        The newly created language config dict.

    Raises:
        HTTPException 400: title missing, derived id invalid or already exists
        HTTPException 500: Write failure
    """
    title = payload.get("title", "").strip()
    description = payload.get("description", "").strip()
    based_on = payload.get("based_on") or None
    tag_remap_raw = payload.get("tag_remap")  # dict[str, str] or None

    if not title:
        raise HTTPException(status_code=400, detail="title is required")
    if tag_remap_raw is not None and not isinstance(tag_remap_raw, dict):
        raise HTTPException(status_code=400, detail="tag_remap must be an object mapping old tags to new tags")

    try:
        new_config = create_language_config(
            title=title,
            description=description,
            based_on=based_on,
            tag_remap=tag_remap_raw or None,
        )
        return new_config
    except PersistenceValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create language: {e}")


@router.get("/languages/{language_id}/tags")
def get_language_tag_list(
    language_id: str,
) -> list[str]:
    """Return the unique tags used in presets for a language config.

    Useful for pre-populating a tag-remap UI when cloning a language.

    Returns:
        Sorted list of unique tag strings.

    Raises:
        HTTPException 404: Language not found.
    """
    try:
        return get_language_tags(language_id)
    except PersistenceValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/steps")
def list_available_steps(
    tool: str = Query(..., description="Tool ID"),
    language: str = Query(..., description="Language ID"),
) -> list[dict[str, str]]:
    """Get list of available steps for a tool/language combination."""
    return get_available_steps(tool, language)


@router.get("/audit")
def get_audit_log(
    limit: int = Query(default=50, ge=1, le=500, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Entries to skip (pagination)"),
    scope: str | None = Query(default=None, description="Filter by scope (language|tool|override)"),
    target: str | None = Query(default=None, description="Filter by target (e.g. 'python', 'claude')"),
) -> dict[str, Any]:
    """Return a paginated, newest-first view of the audit log.

    Each entry records what config file changed, who changed it, when,
    and a full structured diff of what was different.

    Returns:
        {
            "entries": [
                {
                    "timestamp": "2026-04-28T14:30:00Z",
                    "action":    "update",
                    "scope":     "language",
                    "target":    "python",
                    "file":      "backend/app/data/wizard_configs/languages/python.json",
                    "actor":     "system",
                    "diff_summary": "step 'claude_md': 1 field(s) modified",
                    "diff":      { ... }
                },
                ...
            ],
            "total": 42
        }
    """
    return read_audit_log(limit=limit, offset=offset, scope=scope, target=target)


# ---------------------------------------------------------------------------
# Version history endpoints
# ---------------------------------------------------------------------------

@router.get("/history")
def get_config_history(
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier, e.g. 'python' or 'claude'"),
) -> list[dict[str, Any]]:
    """List all versions for a scope+target, newest first."""
    return list_versions(scope, target)


@router.get("/history/diff")
def diff_config_versions(
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier, e.g. 'python' or 'claude'"),
    v1: int = Query(..., description="First version number"),
    v2: int = Query(..., description="Second version number"),
) -> dict[str, Any]:
    """Compute the diff between two versions.

    Returns the structured diff from config_diff plus the version metadata.
    """
    from app.services.config_diff import compare_configs, diff_to_dict

    try:
        data1 = get_version_data(scope, target, v1)
        data2 = get_version_data(scope, target, v2)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    diff_obj = compare_configs(data1, data2)
    return {
        "v1": v1,
        "v2": v2,
        "scope": scope,
        "target": target,
        "diff": diff_to_dict(diff_obj),
    }


@router.get("/history/{version}")
def get_config_version(
    version: int,
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier, e.g. 'python' or 'claude'"),
) -> dict[str, Any]:
    """Return the full envelope (metadata + data) for a specific version."""
    try:
        return get_version(scope, target, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))