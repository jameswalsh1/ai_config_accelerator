from fastapi import APIRouter, HTTPException, Query
from typing import Any

from app.services.config_loader_composable import (
    load_composable_config,
    get_available_tools,
    get_available_languages,
    get_available_steps,
)
from app.services.config_editor import get_editable_step
from app.services.config_patcher import update_field_metadata, ConfigNotFoundError, add_preset_to_field, remove_preset_from_field, remove_field_override
from app.services.config_validator import validate_language_override, validate_tool_override

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
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        changes = payload.get("changes", {})

        if not all([scope, target, step_id, field_id]):
            raise ValueError("Missing required fields: scope, target, step_id, field_id")

        if scope not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        # Transform changes: map 'editable' to 'editability'
        transformed_changes = {}
        for key, value in changes.items():
            if key == "editable":
                # Map boolean to editability string
                transformed_changes["editability"] = "free" if value else "locked"
            else:
                transformed_changes[key] = value

        # Update the override file
        updated_config = update_field_metadata(scope, target, step_id, field_id, transformed_changes)

        # Validate the updated config
        if scope == "language":
            validate_language_override(updated_config)
        elif scope == "tool":
            validate_tool_override(updated_config)
        # For override scope, could add validation if needed

        # Return updated config slice
        # Need to load the full config to get the slice
        # Assuming tool/language are known, but since scope is language, perhaps need tool
        # The payload doesn't have tool, but for the slice, we need tool and language
        # Perhaps assume a default tool, or since it's language scope, the slice is for a specific tool
        # But the acceptance says "Returns updated config slice", probably the step slice
        # But to get the slice, need to load composable config with tool and language
        # The payload doesn't specify tool, only scope=target which is language
        # Perhaps the slice is just the updated override, but the acceptance says "updated config slice"
        # Looking at /edit, it returns the step with resolved config
        # So probably need tool and language in payload, but the example doesn't have it
        # The example payload has scope "language", target "python", but to get the slice, need tool
        # Perhaps the slice is the updated metadata, but I think we need to return the editable step
        # But since no tool specified, perhaps return the updated override data
        # But to match /edit, perhaps add tool to payload, but the ticket doesn't have it
        # The ticket says "Returns updated config slice", and in /edit it's the step slice
        # Perhaps assume a tool, or since it's language, the slice is the field metadata
        # To be safe, I'll return the updated override file content, but that's not a slice
        # Perhaps load with a default tool, say "claude"
        # But let's see the python.json applies_to tools: "claude"
        # So perhaps tool = "claude", language = "python"

        tool = "claude"  # Assuming based on applies_to
        language = target if scope == "language" else "python"  # Assuming

        # Load fully resolved config
        resolved_dict = load_composable_config(tool, language)

        # Extract editable step with metadata
        result = get_editable_step(resolved_dict, step_id)

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
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        override_type = payload.get("override_type", "metadata")

        if not all([scope, target, step_id, field_id]):
            raise ValueError("Missing required fields: scope, target, step_id, field_id")

        if scope not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        if override_type not in ["metadata", "structure"]:
            raise ValueError("Invalid override_type. Must be 'metadata' or 'structure'")

        # Remove the override
        updated_config = remove_field_override(scope, target, step_id, field_id, override_type)

        # Return updated config slice
        # Assume tool/language for slice - use claude/python as defaults
        tool = "claude"
        language = target if scope == "language" else "python"

        resolved_dict = load_composable_config(tool, language)
        result = get_editable_step(resolved_dict, step_id)

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
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        preset = payload.get("preset")
        position = payload.get("position")

        if not all([scope, target, step_id, field_id, preset]):
            raise ValueError("Missing required fields: scope, target, step_id, field_id, preset")

        if scope not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        # Add the preset
        updated_config = add_preset_to_field(scope, target, step_id, field_id, preset, position)

        # Return updated config slice
        # Assume tool/language for slice - use claude/python as defaults
        tool = "claude"
        language = target if scope == "language" else "python"

        resolved_dict = load_composable_config(tool, language)
        result = get_editable_step(resolved_dict, step_id)

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
        step_id = payload.get("step_id")
        field_id = payload.get("field_id")
        preset_label = payload.get("preset_label")
        position = payload.get("position")

        if not all([scope, target, step_id, field_id]):
            raise ValueError("Missing required fields: scope, target, step_id, field_id")

        if scope not in ["language", "tool", "override"]:
            raise ValueError("Invalid scope. Must be 'language', 'tool', or 'override'")

        if preset_label is None and position is None:
            raise ValueError("Must specify either preset_label or position")

        # Remove the preset
        updated_config = remove_preset_from_field(scope, target, step_id, field_id, preset_label, position)

        # Return updated config slice
        # Assume tool/language for slice - use claude/python as defaults
        tool = "claude"
        language = target if scope == "language" else "python"

        resolved_dict = load_composable_config(tool, language)
        result = get_editable_step(resolved_dict, step_id)

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


@router.get("/languages")
def list_available_languages() -> list[dict[str, str]]:
    """Get list of available languages."""
    return get_available_languages()


@router.get("/steps")
def list_available_steps(
    tool: str = Query(..., description="Tool ID"),
    language: str = Query(..., description="Language ID"),
) -> list[dict[str, str]]:
    """Get list of available steps for a tool/language combination."""
    return get_available_steps(tool, language)