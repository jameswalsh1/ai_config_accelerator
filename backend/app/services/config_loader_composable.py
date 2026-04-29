"""
Composable configuration loader for wizard configs.

Implements identity + overrides architecture:
- Load canonical schema (defines all possible fields)
- Apply tool overrides
- Apply language overrides
- Apply tool+language overrides
- Merge deterministically
"""

import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Literal, cast

from app.models.wizard import WizardConfig, WizardField, WizardStep
from app.services.config_validator import (
    validate_wizard_schema,
    validate_tool_override,
    validate_language_override,
    validate_combo_override,
    SchemaValidationError,
)

DATA_DIR = Path(__file__).parent.parent / "data" / "wizard_configs"

# Merge mode for presets and options
MergeMode = Literal["append", "merge_by_label", "replace"]


def _resolve_preset_files(data: Any) -> Any:
    """Recursively resolve preset_files references to inline presets."""
    if isinstance(data, dict):
        if "preset_files" in data and isinstance(data["preset_files"], list):
            presets = list(data.get("presets", []))
            for preset_path in data["preset_files"]:
                preset_file = DATA_DIR / preset_path
                if not preset_file.exists():
                    raise FileNotFoundError(f"Preset file not found: {preset_file}")
                with preset_file.open(encoding="utf-8") as f:
                    file_presets = json.load(f)
                if not isinstance(file_presets, list):
                    raise ValueError(f"Preset file must contain a JSON array: {preset_file}")
                presets.extend(file_presets)
            data["presets"] = presets
        return {key: _resolve_preset_files(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_resolve_preset_files(value) for value in data]
    return data


def _get_field_by_id(steps: list[dict[str, Any]], field_id: str) -> dict[str, Any] | None:
    """
    Find a field in steps by field_id path: 'step_id.field_id' or nested.
    
    Returns the field dict or None if not found.
    """
    parts = field_id.split(".", 1)
    if len(parts) != 2:
        return None
    
    step_id, rest = parts
    
    # Find the step
    for step in steps:
        if step.get("id") == step_id:
            # Navigate nested fields
            fields = step.get("fields", [])
            return _find_nested_field(fields, rest)
    
    return None


def _find_nested_field(fields: list[dict[str, Any]], path: str) -> dict[str, Any] | None:
    """Recursively find a nested field by path."""
    parts = path.split(".", 1)
    field_id = parts[0]
    
    # Find field with this id
    for field in fields:
        if field.get("id") == field_id:
            if len(parts) == 1:
                # Found it
                return field
            else:
                # Recurse into nested fields
                nested_path = parts[1]
                nested_fields = field.get("fields", [])
                return _find_nested_field(nested_fields, nested_path)
    
    return None


def _merge_presets(
    existing: list[dict[str, Any]] | None,
    new_presets: list[dict[str, Any]],
    mode: MergeMode = "append",
) -> list[dict[str, Any]]:
    """
    Merge presets according to mode.
    
    Args:
        existing: Current preset list
        new_presets: Presets to add/merge
        mode: "append" (add to end), "merge_by_label" (update existing by label), "replace" (replace all)
    """
    if mode == "replace":
        return new_presets
    
    if mode == "merge_by_label":
        result = list(existing or [])
        for new_preset in new_presets:
            label = new_preset.get("label")
            found = False
            for i, existing_preset in enumerate(result):
                if existing_preset.get("label") == label:
                    result[i] = new_preset
                    found = True
                    break
            if not found:
                result.append(new_preset)
        return result
    
    # append mode (default)
    return list(existing or []) + new_presets


def _apply_metadata_override(field: dict[str, Any], override: dict[str, Any], source: str) -> None:
    """
    Apply metadata override to a field dict.
    
    Metadata overrides change: default, editability, required, hidden, lock_reason.
    """
    if "default" in override:
        field["default"] = override["default"]
    
    if "editability" in override:
        field["editability"] = override["editability"]
    
    if "required" in override:
        field["required"] = override["required"]
    
    if "hidden" in override:
        field["hidden"] = override["hidden"]
    
    if "lock_reason" in override:
        field["lock_reason"] = override["lock_reason"]
    
    # Track where this value came from
    if "override_source" not in field:
        field["override_source"] = source


def _apply_field_override(field: dict[str, Any], override: dict[str, Any], source: str) -> None:
    """
    Apply structural field override to a field dict.
    
    Structural overrides change: options, presets, validation, etc.
    """
    merge_mode: MergeMode = override.get("merge_mode", "append")
    
    # Handle options
    if "replace_options_with" in override:
        field["options"] = override["replace_options_with"]
    elif "merge_options" in override:
        existing = field.get("options", [])
        field["options"] = existing + override["merge_options"]
    
    # Handle presets
    if "replace_presets_with" in override:
        field["presets"] = override["replace_presets_with"]
    elif "merge_presets" in override:
        existing = field.get("presets", [])
        field["presets"] = _merge_presets(existing, override["merge_presets"], merge_mode)
    
    # Handle preset files
    if "preset_files_to_add" in override:
        existing_files = field.get("preset_files", [])
        field["preset_files"] = existing_files + override["preset_files_to_add"]
    
    # Track where this came from
    if "override_source" not in field:
        field["override_source"] = source


def _apply_overrides(
    config: dict[str, Any],
    overrides: dict[str, Any],
    source: str,
    applies_to_tool: str | None = None,
    applies_to_language: str | None = None,
) -> None:
    """
    Apply an override config to the current config.
    
    Args:
        config: Config to modify in-place
        overrides: Override config with metadata_overrides, field_overrides, step_overrides
        source: Name of this layer (e.g., "tool:claude", "language:python")
        applies_to_tool: If set, only apply if override's applies_to.tools matches
        applies_to_language: If set, only apply if override's applies_to.languages matches
    """
    applies_to = overrides.get("applies_to", {})
    
    # Check if this override applies to the current tool
    if applies_to_tool:
        applies_to_tools = applies_to.get("tools", [])
        if applies_to_tools and applies_to_tool not in applies_to_tools:
            return
    
    # Check if this override applies to the current language
    if applies_to_language:
        applies_to_languages = applies_to.get("languages", [])
        if applies_to_languages and applies_to_language not in applies_to_languages:
            return
    
    steps = config.get("steps", [])
    
    # Apply metadata overrides
    for metadata_override in overrides.get("metadata_overrides", []):
        field_id = metadata_override.get("field_id")
        if not field_id:
            continue
        
        field = _get_field_by_id(steps, field_id)
        if field:
            _apply_metadata_override(field, metadata_override, source)
    
    # Apply field overrides
    for field_override in overrides.get("field_overrides", []):
        field_id = field_override.get("field_id")
        if not field_id:
            continue
        
        field = _get_field_by_id(steps, field_id)
        if field:
            _apply_field_override(field, field_override, source)
    
    # Apply step overrides
    for step_override in overrides.get("step_overrides", []):
        step_id = step_override.get("step_id")
        if not step_id:
            continue
        
        # Find the step
        for step in steps:
            if step.get("id") == step_id:
                if "hidden" in step_override:
                    step["hidden"] = step_override["hidden"]
                if "title_override" in step_override:
                    step["title"] = step_override["title_override"]
                if "description_override" in step_override:
                    step["description"] = step_override["description_override"]
                if "hint_override" in step_override:
                    step["hint"] = step_override["hint_override"]
                break


def load_composable_config(tool_id: str, language_id: str) -> dict[str, Any]:
    """
    Load and compose a wizard config from layered overrides.
    
    Composition order:
    1. Load schema.json (canonical config)
    2. Apply tool/{tool_id}.json overrides (extracting tool_metadata to top level)
    3. Apply languages/{language_id}.json overrides
    4. Apply overrides/{tool_id}+{language_id}.json if exists
    5. Resolve all preset_files
    6. Return composed config
    
    Args:
        tool_id: Tool identifier (e.g., 'claude', 'copilot')
        language_id: Language identifier (e.g., 'python', 'dotnet')
    
    Returns:
        Composed WizardConfig dict with id, title, target at top level
    """
    # Load canonical schema
    schema_file = DATA_DIR / "schema.json"
    if not schema_file.exists():
        raise FileNotFoundError(f"Schema file not found: {schema_file}")
    
    with schema_file.open(encoding="utf-8") as f:
        config = deepcopy(json.load(f))
    
    # Validate schema
    try:
        validate_wizard_schema(config)
    except SchemaValidationError as e:
        raise ValueError(f"Invalid schema.json: {e}")
    
    # Apply tool overrides
    tool_override_file = DATA_DIR / "tools" / f"{tool_id}.json"
    if tool_override_file.exists():
        with tool_override_file.open(encoding="utf-8") as f:
            tool_overrides = json.load(f)
        
        # Validate tool overrides
        try:
            validate_tool_override(tool_overrides)
        except SchemaValidationError as e:
            raise ValueError(f"Invalid {tool_override_file.name}: {e}")
        
        # Extract tool_metadata and merge into top level
        if "tool_metadata" in tool_overrides:
            metadata = tool_overrides["tool_metadata"]
            if "title" in metadata:
                config["title"] = metadata["title"]
            if "description" in metadata:
                config["description"] = metadata["description"]
            if "target" in metadata:
                config["target"] = metadata["target"]
            # Use tool_id as config id
            config["id"] = tool_id
        
        _apply_overrides(
            config, 
            tool_overrides, 
            source=f"tool:{tool_id}",
            applies_to_tool=tool_id
        )
    
    # Apply language overrides
    language_override_file = DATA_DIR / "languages" / f"{language_id}.json"
    if language_override_file.exists():
        with language_override_file.open(encoding="utf-8") as f:
            language_overrides = json.load(f)
        
        # Validate language overrides
        try:
            validate_language_override(language_overrides)
        except SchemaValidationError as e:
            raise ValueError(f"Invalid {language_override_file.name}: {e}")
        
        _apply_overrides(
            config,
            language_overrides,
            source=f"language:{language_id}",
            applies_to_language=language_id
        )
    
    # Apply tool+language overrides (highest priority)
    combo_override_file = DATA_DIR / "overrides" / f"{tool_id}+{language_id}.json"
    if combo_override_file.exists():
        with combo_override_file.open(encoding="utf-8") as f:
            combo_overrides = json.load(f)
        
        # Validate combo overrides
        try:
            validate_combo_override(combo_overrides)
        except SchemaValidationError as e:
            raise ValueError(f"Invalid {combo_override_file.name}: {e}")
        
        _apply_overrides(
            config,
            combo_overrides,
            source=f"override:{tool_id}+{language_id}",
            applies_to_tool=tool_id,
            applies_to_language=language_id
        )
    
    # Resolve all preset_files references
    config = cast(dict[str, Any], _resolve_preset_files(config))

    return config


def load_config_legacy_path(config_id: str) -> dict[str, Any] | None:
    """
    DEPRECATED: Load a config from the old monolithic directory structure (base + language variants).
    
    This exists for backwards compatibility during migration.
    New code should use load_composable_config() instead.
    """
    config_dir = DATA_DIR / config_id
    if not config_dir.is_dir():
        return None
    
    base_file = config_dir / "_base.json"
    if not base_file.exists():
        return None
    
    # Load base config
    with base_file.open(encoding="utf-8") as f:
        base_config = json.load(f)
    
    # Load and merge language-specific configs
    languages_dir = config_dir / "languages"
    if languages_dir.is_dir():
        for lang_file in sorted(languages_dir.glob("*.json")):
            with lang_file.open(encoding="utf-8") as f:
                lang_config = json.load(f)
            
            # OLD MERGE LOGIC (preserved for backwards compat)
            # This is what we're replacing
            if "step_overrides" in lang_config:
                for override in lang_config["step_overrides"]:
                    step_id = override.get("step_id")
                    field_id = override.get("field_id")
                    presets_to_add = override.get("presets_to_add", [])
                    
                    if not step_id or not field_id or not presets_to_add:
                        continue
                    
                    # Find the step and field
                    for step in base_config.get("steps", []):
                        if step.get("id") == step_id:
                            for field in step.get("fields", []):
                                if field.get("id") == field_id:
                                    if "presets" not in field:
                                        field["presets"] = []
                                    field["presets"].extend(presets_to_add)
                                    break
                            break
    
    # Resolve preset files
    base_config = cast(dict[str, Any], _resolve_preset_files(base_config))

    return base_config


def extract_presets_from_config(config: dict[str, Any], tool_id: str, language_id: str) -> dict[str, list[dict[str, Any]]]:
    """
    Extract all presets from a resolved wizard config and categorize them.
    
    Args:
        config: Resolved wizard config dict
        tool_id: Tool identifier (e.g., 'claude', 'copilot')
        language_id: Language identifier (e.g., 'python', 'java')
    
    Returns:
        Dict with keys 'shared', 'language', 'tool' containing lists of preset dicts
    """
    shared_presets: list[dict[str, Any]] = []
    language_presets: list[dict[str, Any]] = []
    tool_presets: list[dict[str, Any]] = []
    
    # Traverse all steps and fields to collect presets
    for step in config.get("steps", []):
        for field in step.get("fields", []):
            _collect_presets_from_field(field, shared_presets, language_presets, tool_presets, tool_id, language_id)
    
    return {
        "shared": shared_presets,
        "language": language_presets,
        "tool": tool_presets
    }


def _collect_presets_from_field(
    field: dict[str, Any],
    shared_presets: list[dict[str, Any]],
    language_presets: list[dict[str, Any]],
    tool_presets: list[dict[str, Any]],
    tool_id: str,
    language_id: str
) -> None:
    """Recursively collect presets from a field and its nested fields."""
    # Collect presets from this field
    for preset in field.get("presets", []):
        categorized = False
        
        # Check if it's a shared preset (has multiple tool tags)
        tags = preset.get("tags", [])
        if len(tags) > 1 and tool_id in tags:
            shared_presets.append(preset)
            categorized = True
        
        # Check if it's a language preset (has language tag)
        if language_id in tags:
            language_presets.append(preset)
            categorized = True
        
        # If not categorized yet, it's likely a tool-specific preset
        if not categorized:
            tool_presets.append(preset)
    
    # Recurse into nested fields
    for nested_field in field.get("fields", []):
        _collect_presets_from_field(nested_field, shared_presets, language_presets, tool_presets, tool_id, language_id)


def get_available_tools() -> list[dict[str, str]]:
    """Get list of available tools with their metadata."""
    tools = []
    tools_dir = DATA_DIR / "tools"
    if tools_dir.exists():
        for tool_file in sorted(tools_dir.glob("*.json")):
            try:
                with tool_file.open(encoding="utf-8") as f:
                    tool_data = json.load(f)
                
                tool_id = tool_data.get("tool_id")
                metadata = tool_data.get("tool_metadata", {})
                
                if tool_id:
                    tools.append({
                        "id": tool_id,
                        "title": metadata.get("title", tool_id),
                        "description": metadata.get("description", ""),
                        "target": metadata.get("target", tool_id),
                    })
            except (json.JSONDecodeError, KeyError):
                continue
    
    return tools


def get_available_languages() -> list[dict[str, str]]:
    """Get list of available languages with their metadata."""
    languages = []
    languages_dir = DATA_DIR / "languages"
    if languages_dir.exists():
        for lang_file in sorted(languages_dir.glob("*.json")):
            try:
                with lang_file.open(encoding="utf-8") as f:
                    lang_data = json.load(f)

                language_id = lang_data.get("language_id")
                if not language_id:
                    continue

                metadata = lang_data.get("metadata", {})
                # Fall back to capitalised id when no title stored
                title = metadata.get("title") or language_id.replace("-", " ").title()
                description = metadata.get("description", "")

                languages.append({
                    "id": language_id,
                    "title": title,
                    "description": description,
                })
            except (json.JSONDecodeError, KeyError):
                continue

    return languages


def get_available_steps(tool_id: str, language_id: str) -> list[dict[str, str]]:
    """Get list of available steps for a tool/language combination."""
    try:
        config = load_composable_config(tool_id, language_id)
        steps = []
        for step in config.get("steps", []):
            if step.get("hidden", False):
                continue
            steps.append({
                "id": step.get("id"),
                "title": step.get("title", step.get("id")),
                "description": step.get("description", ""),
            })
        return steps
    except (FileNotFoundError, ValueError):
        return []


# ---------------------------------------------------------------------------
# Coverage matrix
# ---------------------------------------------------------------------------

def _get_tool_visible_step_ids(tool_data: dict[str, Any], all_step_ids: list[str]) -> set[str]:
    """Return the set of step IDs visible for a tool (not hidden, excluding language_selection)."""
    hidden: set[str] = {
        so.get("step_id")
        for so in tool_data.get("step_overrides", [])
        if so.get("hidden")
    }
    return {sid for sid in all_step_ids if sid not in hidden and sid != "language_selection"}


def get_coverage_matrix() -> dict[str, Any]:
    """Compute the tool × language coverage matrix.

    For each tool+language pair the response reports:
    - ``status``: ``'full'`` (≥2 relevant field overrides), ``'partial'`` (1),
      or ``'none'`` (0)
    - ``field_count``: number of matching field overrides
    - ``fields``: list of matching field_id strings

    A field override is *relevant* for a tool when its step prefix
    (e.g. ``claude_md`` from ``claude_md.tech_stack``) appears in the tool's
    visible steps (all schema steps minus the tool's hidden ones, and minus
    the universal ``language_selection`` step).

    Returns:
        {
            "tools":     [{"id": ..., "title": ...}, ...],
            "languages": [{"id": ..., "title": ...}, ...],
            "matrix":    { tool_id: { language_id: { status, field_count, fields } } }
        }
    """
    schema_path = DATA_DIR / "schema.json"
    with schema_path.open(encoding="utf-8") as f:
        schema = json.load(f)

    all_step_ids: list[str] = [
        s.get("id", s.get("step_id"))
        for s in schema.get("steps", [])
        if s.get("id") or s.get("step_id")
    ]

    tools = get_available_tools()
    languages = get_available_languages()

    # Pre-compute visible steps per tool
    tool_visible_steps: dict[str, set[str]] = {}
    for tool in tools:
        tool_id = tool["id"]
        tool_path = DATA_DIR / "tools" / f"{tool_id}.json"
        try:
            with tool_path.open(encoding="utf-8") as f:
                tool_data = json.load(f)
            tool_visible_steps[tool_id] = _get_tool_visible_step_ids(tool_data, all_step_ids)
        except (FileNotFoundError, json.JSONDecodeError):
            tool_visible_steps[tool_id] = set()

    # Pre-compute field overrides per language (step_prefix → [field_ids])
    lang_step_fields: dict[str, dict[str, list[str]]] = {}
    for lang in languages:
        lang_id = lang["id"]
        lang_path = DATA_DIR / "languages" / f"{lang_id}.json"
        try:
            with lang_path.open(encoding="utf-8") as f:
                lang_data = json.load(f)
            step_fields: dict[str, list[str]] = {}
            for fo in lang_data.get("field_overrides", []):
                field_id: str = fo.get("field_id", "")
                step_prefix = field_id.split(".")[0] if "." in field_id else field_id
                step_fields.setdefault(step_prefix, []).append(field_id)
            lang_step_fields[lang_id] = step_fields
        except (FileNotFoundError, json.JSONDecodeError):
            lang_step_fields[lang_id] = {}

    # Build matrix
    matrix: dict[str, dict[str, dict[str, Any]]] = {}
    for tool in tools:
        tool_id = tool["id"]
        visible = tool_visible_steps[tool_id]
        matrix[tool_id] = {}
        for lang in languages:
            lang_id = lang["id"]
            step_fields = lang_step_fields.get(lang_id, {})
            relevant: list[str] = []
            for step_prefix, fields in step_fields.items():
                if step_prefix in visible:
                    relevant.extend(fields)
            count = len(relevant)
            matrix[tool_id][lang_id] = {
                "status": "full" if count >= 2 else ("partial" if count == 1 else "none"),
                "field_count": count,
                "fields": relevant,
            }

    return {
        "tools": [{"id": t["id"], "title": t["title"]} for t in tools],
        "languages": [{"id": l["id"], "title": l["title"]} for l in languages],
        "matrix": matrix,
    }
