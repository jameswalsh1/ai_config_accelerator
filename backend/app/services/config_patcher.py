"""
JSON Patch Engine for wizard configuration updates.

Implements ID-based targeted updates to configuration files with:
- Atomic operations on specific fields/steps
- Safe concurrent access (file locking + retry logic)
- Minimal file rewrites (only modifies relevant override)
- Format preservation where practical
"""

import json
import time
from pathlib import Path
from typing import Any, Literal
from copy import deepcopy

DATA_DIR = Path(__file__).parent.parent / "data" / "wizard_configs"

# Scope types
PatchScope = Literal["tool", "language", "override"]


class PatchError(Exception):
    """Base exception for patching operations."""
    pass


class ConfigNotFoundError(PatchError):
    """Raised when a target configuration file is not found."""
    pass


class FieldNotFoundError(PatchError):
    """Raised when a field is not found in the schema."""
    pass


class FileLockError(PatchError):
    """Raised when unable to acquire file lock."""
    pass


def _get_target_file(scope: PatchScope, target: str) -> Path:
    """
    Resolve the target file path based on scope and target.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool ID (e.g., "claude"), language ID (e.g., "python"), 
                or override combo (e.g., "claude+python")
    
    Returns:
        Path to the configuration file
    
    Raises:
        ConfigNotFoundError: If scope is invalid
    """
    if scope == "tool":
        target_file = DATA_DIR / "tools" / f"{target}.json"
    elif scope == "language":
        target_file = DATA_DIR / "languages" / f"{target}.json"
    elif scope == "override":
        target_file = DATA_DIR / "overrides" / f"{target}.json"
    else:
        raise PatchError(f"Invalid scope: {scope}. Must be 'tool', 'language', or 'override'")
    
    return target_file


def _get_field_override_index(
    overrides: list[dict[str, Any]], 
    field_id: str
) -> int | None:
    """
    Find the index of a field override by field_id.
    
    Args:
        overrides: List of override dicts with 'field_id' keys
        field_id: The field ID to find (e.g., "step_id.field_id")
    
    Returns:
        Index if found, None otherwise
    """
    for i, override in enumerate(overrides):
        if override.get("field_id") == field_id:
            return i
    return None


def _get_step_override_index(
    overrides: list[dict[str, Any]], 
    step_id: str
) -> int | None:
    """
    Find the index of a step override by step_id.
    
    Args:
        overrides: List of override dicts with 'step_id' keys
        step_id: The step ID to find
    
    Returns:
        Index if found, None otherwise
    """
    for i, override in enumerate(overrides):
        if override.get("step_id") == step_id:
            return i
    return None


def _acquire_file_lock(file_path: Path, timeout: float = 5.0, retry_delay: float = 0.1) -> None:
    """
    Acquire a lock for file modification.
    
    Uses a simple lock file approach: creates a .lock file next to the target.
    Retries until timeout is exceeded.
    
    Args:
        file_path: File to lock
        timeout: Maximum time to wait for lock (seconds)
        retry_delay: Time between lock attempts (seconds)
    
    Raises:
        FileLockError: If unable to acquire lock within timeout
    """
    lock_file = file_path.with_suffix(file_path.suffix + ".lock")
    start_time = time.time()
    
    while True:
        try:
            # Atomic operation: create only if doesn't exist
            lock_file.touch(exist_ok=False)
            return
        except FileExistsError:
            if time.time() - start_time > timeout:
                raise FileLockError(
                    f"Could not acquire lock for {file_path} within {timeout}s"
                )
            time.sleep(retry_delay)


def _release_file_lock(file_path: Path) -> None:
    """
    Release the lock for a file.
    
    Args:
        file_path: File to unlock
    """
    lock_file = file_path.with_suffix(file_path.suffix + ".lock")
    try:
        lock_file.unlink()
    except FileNotFoundError:
        pass  # Lock already gone, that's fine


def _read_json_file(file_path: Path) -> dict[str, Any]:
    """
    Read a JSON file with error handling.
    
    Args:
        file_path: File to read
    
    Returns:
        Parsed JSON content
    
    Raises:
        ConfigNotFoundError: If file not found
        PatchError: If JSON is invalid
    """
    if not file_path.exists():
        raise ConfigNotFoundError(f"Configuration file not found: {file_path}")
    
    try:
        with file_path.open(encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        raise PatchError(f"Invalid JSON in {file_path}: {e}")


def _write_json_file(
    file_path: Path,
    data: dict[str, Any],
    indent: int = 2,  # kept for API compatibility; save_config uses indent=2 internally
    context: dict[str, Any] | None = None,
) -> None:
    """
    Write a JSON file atomically, emitting an audit log entry.

    Routes through save_config so every patch write is atomic and audited.
    validate=False because the patcher works on raw override files that may
    not pass the full wizard schema (they're partial by design).
    """
    from app.services.config_persistence import save_config

    save_config(
        file_path,
        data,
        validate=False,
        create_backup=True,
        verify_reloadable=False,
        context=context,
    )


def update_field_metadata(
    scope: PatchScope,
    target: str,
    step_id: str,
    field_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    """
    Update metadata for a specific field in an override file.
    
    Creates or updates a metadata_override entry for the field.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool/language ID or combo (e.g., "python")
        step_id: Step containing the field
        field_id: Field to update
        changes: Dict with keys like "default", "editability", "required", "hidden"
    
    Returns:
        The updated override file content
    
    Raises:
        ConfigNotFoundError: If target file not found
        FileLockError: If unable to acquire lock
        PatchError: If operation fails
    """
    target_file = _get_target_file(scope, target)
    
    # Acquire lock for safe concurrent access
    _acquire_file_lock(target_file)
    
    try:
        # Read current content
        config = _read_json_file(target_file)
        
        # Ensure metadata_overrides list exists
        if "metadata_overrides" not in config:
            config["metadata_overrides"] = []
        
        metadata_overrides = config["metadata_overrides"]
        full_field_id = f"{step_id}.{field_id}"
        
        # Find existing override or create new one
        override_idx = _get_field_override_index(metadata_overrides, full_field_id)
        
        if override_idx is not None:
            # Update existing
            override = metadata_overrides[override_idx]
        else:
            # Create new
            override = {"field_id": full_field_id}
            metadata_overrides.append(override)
        
        # Apply changes to override
        for key, value in changes.items():
            if key in ["default", "editability", "required", "hidden", "lock_reason"]:
                override[key] = value
            else:
                raise PatchError(f"Unknown metadata field: {key}. Use: default, editability, required, hidden, lock_reason")
        
        # Write back
        _write_json_file(target_file, config, context={"scope": scope, "target": target})
        
        return config
        
    finally:
        _release_file_lock(target_file)


def update_field_structure(
    scope: PatchScope,
    target: str,
    step_id: str,
    field_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    """
    Update structure for a specific field (options, presets, validation).
    
    Creates or updates a field_override entry for the field.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool/language ID or combo
        step_id: Step containing the field
        field_id: Field to update
        changes: Dict with keys like "merge_presets", "replace_options_with", "merge_mode", etc.
    
    Returns:
        The updated override file content
    
    Raises:
        ConfigNotFoundError: If target file not found
        FileLockError: If unable to acquire lock
        PatchError: If operation fails
    """
    target_file = _get_target_file(scope, target)
    
    # Acquire lock
    _acquire_file_lock(target_file)
    
    try:
        # Read current content
        config = _read_json_file(target_file)
        
        # Ensure field_overrides list exists
        if "field_overrides" not in config:
            config["field_overrides"] = []
        
        field_overrides = config["field_overrides"]
        full_field_id = f"{step_id}.{field_id}"
        
        # Find existing override or create new one
        override_idx = _get_field_override_index(field_overrides, full_field_id)
        
        if override_idx is not None:
            override = field_overrides[override_idx]
        else:
            override = {"field_id": full_field_id}
            field_overrides.append(override)
        
        # Apply changes
        valid_keys = {
            "merge_presets", "replace_presets_with",
            "merge_options", "replace_options_with",
            "merge_mode", "preset_files_to_add",
            "validation"
        }
        
        for key, value in changes.items():
            if key not in valid_keys:
                raise PatchError(
                    f"Unknown field structure property: {key}. "
                    f"Use: {', '.join(sorted(valid_keys))}"
                )
            override[key] = value
        
        # Write back
        _write_json_file(target_file, config, context={"scope": scope, "target": target})
        
        return config
        
    finally:
        _release_file_lock(target_file)


def update_step_visibility(
    scope: PatchScope,
    target: str,
    step_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    """
    Update visibility or other properties for a step.
    
    Creates or updates a step_override entry.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool/language ID or combo
        step_id: Step to update
        changes: Dict with keys like "hidden", "title_override", "description_override", etc.
    
    Returns:
        The updated override file content
    
    Raises:
        ConfigNotFoundError: If target file not found
        FileLockError: If unable to acquire lock
        PatchError: If operation fails
    """
    target_file = _get_target_file(scope, target)
    
    # Acquire lock
    _acquire_file_lock(target_file)
    
    try:
        # Read current content
        config = _read_json_file(target_file)
        
        # Ensure step_overrides list exists
        if "step_overrides" not in config:
            config["step_overrides"] = []
        
        step_overrides = config["step_overrides"]
        
        # Find existing override or create new one
        override_idx = _get_step_override_index(step_overrides, step_id)
        
        if override_idx is not None:
            override = step_overrides[override_idx]
        else:
            override = {"step_id": step_id}
            step_overrides.append(override)
        
        # Apply changes
        valid_keys = {"hidden", "title_override", "description_override", "hint_override"}
        
        for key, value in changes.items():
            if key not in valid_keys:
                raise PatchError(
                    f"Unknown step property: {key}. "
                    f"Use: {', '.join(sorted(valid_keys))}"
                )
            override[key] = value
        
        # Write back
        _write_json_file(target_file, config, context={"scope": scope, "target": target})
        
        return config
        
    finally:
        _release_file_lock(target_file)


def apply_patch(patch: dict[str, Any]) -> dict[str, Any]:
    """
    Apply a patch to a configuration file.
    
    Dispatches to appropriate update function based on patch structure.
    
    Patch format:
    ```json
    {
      "scope": "language|tool|override",
      "target": "python|claude|claude+python",
      "step_id": "step_name",
      "field_id": "field_name",  # optional, required for field updates
      "update_type": "metadata|structure|step",  # optional, auto-detected
      "changes": {
        "default": "new_value",
        "editability": "locked",
        ...
      }
    }
    ```
    
    Args:
        patch: Patch specification dict
    
    Returns:
        The updated configuration file content
    
    Raises:
        PatchError: If patch is invalid or operation fails
    """
    # Validate required fields
    scope = patch.get("scope")
    target = patch.get("target")
    step_id = patch.get("step_id")
    changes = patch.get("changes")
    
    if not scope or not target or not step_id or not changes:
        raise PatchError(
            "Patch must include: scope, target, step_id, changes. "
            "field_id required for field updates."
        )
    
    if scope not in ["tool", "language", "override"]:
        raise PatchError(f"Invalid scope: {scope}")
    
    field_id = patch.get("field_id")
    update_type = patch.get("update_type")
    
    # Auto-detect update type if not specified
    if not update_type:
        if field_id:
            # Determine if this is metadata or structure update
            metadata_keys = {"default", "editability", "required", "hidden"}
            structure_keys = {
                "merge_presets", "replace_presets_with",
                "merge_options", "replace_options_with",
                "merge_mode", "preset_files_to_add", "validation"
            }
            
            changes_keys = set(changes.keys())
            
            if changes_keys & metadata_keys:
                update_type = "metadata"
            elif changes_keys & structure_keys:
                update_type = "structure"
            else:
                raise PatchError(
                    f"Unknown change type in {changes_keys}. "
                    f"Valid: {metadata_keys | structure_keys}"
                )
        else:
            update_type = "step"
    
    # Dispatch to appropriate handler
    if update_type == "metadata":
        if not field_id:
            raise PatchError("field_id required for metadata updates")
        return update_field_metadata(scope, target, step_id, field_id, changes)
    
    elif update_type == "structure":
        if not field_id:
            raise PatchError("field_id required for structure updates")
        return update_field_structure(scope, target, step_id, field_id, changes)
    
    elif update_type == "step":
        return update_step_visibility(scope, target, step_id, changes)
    
    else:
        raise PatchError(f"Unknown update_type: {update_type}")


def remove_field_override(
    scope: PatchScope,
    target: str,
    step_id: str,
    field_id: str,
    override_type: Literal["metadata", "structure"] = "metadata",
) -> dict[str, Any]:
    """
    Remove an override entry for a field.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool/language ID or combo
        step_id: Step containing the field
        field_id: Field to remove override for
        override_type: "metadata" or "structure"
    
    Returns:
        The updated override file content
    
    Raises:
        ConfigNotFoundError: If target file not found
        FileLockError: If unable to acquire lock
    """
    target_file = _get_target_file(scope, target)
    
    # Acquire lock
    _acquire_file_lock(target_file)
    
    try:
        # Read current content
        config = _read_json_file(target_file)
        
        full_field_id = f"{step_id}.{field_id}"
        
        # Remove from appropriate list
        if override_type == "metadata":
            if "metadata_overrides" in config:
                config["metadata_overrides"] = [
                    o for o in config["metadata_overrides"]
                    if o.get("field_id") != full_field_id
                ]
        
        elif override_type == "structure":
            if "field_overrides" in config:
                config["field_overrides"] = [
                    o for o in config["field_overrides"]
                    if o.get("field_id") != full_field_id
                ]
        
        # Write back
        _write_json_file(target_file, config, context={"scope": scope, "target": target})
        
        return config
        
    finally:
        _release_file_lock(target_file)


def add_preset_to_field(
    scope: PatchScope,
    target: str,
    step_id: str,
    field_id: str,
    preset: dict[str, Any],
    position: int | None = None,
) -> dict[str, Any]:
    """
    Add a preset to a field's presets list at the specified position.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool/language ID or combo
        step_id: Step containing the field
        field_id: Field to add preset to
        preset: Preset dict with label, value, etc.
        position: Position to insert at (None = append)
    
    Returns:
        The updated override file content
    
    Raises:
        ConfigNotFoundError: If target file not found
        FileLockError: If unable to acquire lock
        PatchError: If operation fails
    """
    target_file = _get_target_file(scope, target)
    
    # Acquire lock
    _acquire_file_lock(target_file)
    
    try:
        # Read current content
        config = _read_json_file(target_file)
        
        # Ensure field_overrides list exists
        if "field_overrides" not in config:
            config["field_overrides"] = []
        
        field_overrides = config["field_overrides"]
        full_field_id = f"{step_id}.{field_id}"
        
        # Find existing override or create new one
        override_idx = _get_field_override_index(field_overrides, full_field_id)
        
        if override_idx is not None:
            override = field_overrides[override_idx]
        else:
            override = {"field_id": full_field_id}
            field_overrides.append(override)
        
        # Get current presets from override or initialize
        current_presets = override.get("replace_presets_with", [])
        
        # Insert preset at position
        if position is None or position >= len(current_presets):
            current_presets.append(preset)
        else:
            current_presets.insert(position, preset)
        
        # Update override
        override["replace_presets_with"] = current_presets
        
        # Write back
        _write_json_file(target_file, config, context={"scope": scope, "target": target})
        
        return config
        
    finally:
        _release_file_lock(target_file)


def remove_preset_from_field(
    scope: PatchScope,
    target: str,
    step_id: str,
    field_id: str,
    preset_label: str | None = None,
    position: int | None = None,
) -> dict[str, Any]:
    """
    Remove a preset from a field's presets list.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool/language ID or combo
        step_id: Step containing the field
        field_id: Field to remove preset from
        preset_label: Label of preset to remove (if specified)
        position: Position to remove from (if specified, takes precedence over label)
    
    Returns:
        The updated override file content
    
    Raises:
        ConfigNotFoundError: If target file not found
        FileLockError: If unable to acquire lock
        PatchError: If operation fails
    """
    target_file = _get_target_file(scope, target)
    
    # Acquire lock
    _acquire_file_lock(target_file)
    
    try:
        # Read current content
        config = _read_json_file(target_file)
        
        # Ensure field_overrides list exists
        if "field_overrides" not in config:
            config["field_overrides"] = []
        
        field_overrides = config["field_overrides"]
        full_field_id = f"{step_id}.{field_id}"
        
        # Find existing override
        override_idx = _get_field_override_index(field_overrides, full_field_id)
        
        if override_idx is None:
            raise PatchError(f"No override found for field {full_field_id}")
        
        override = field_overrides[override_idx]
        current_presets = override.get("replace_presets_with", [])
        
        # Remove preset
        if position is not None:
            if 0 <= position < len(current_presets):
                current_presets.pop(position)
            else:
                raise PatchError(f"Invalid position {position} for presets list of length {len(current_presets)}")
        elif preset_label is not None:
            # Find by label
            found = False
            for i, p in enumerate(current_presets):
                if p.get("label") == preset_label:
                    current_presets.pop(i)
                    found = True
                    break
            if not found:
                raise PatchError(f"Preset with label '{preset_label}' not found")
        else:
            raise PatchError("Must specify either preset_label or position")
        
        # Update override
        override["replace_presets_with"] = current_presets
        
        # Write back
        _write_json_file(target_file, config, context={"scope": scope, "target": target})
        
        return config
        
    finally:
        _release_file_lock(target_file)
