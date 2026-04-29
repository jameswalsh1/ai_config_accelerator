"""
Config Persistence Service for wizard configuration management.

Implements safe, atomic persistence of configuration changes with:
- Atomic writes (temp file → rename)
- Schema validation
- Format consistency
- Reloadability verification
- Rollback capability
"""

import json
import tempfile
from pathlib import Path
from typing import Any, cast
from copy import deepcopy

from app.services.config_loader_composable import load_composable_config
from app.services.config_validator import (
    validate_config_file,
    SchemaValidationError,
)

DATA_DIR = Path(__file__).parent.parent / "data" / "wizard_configs"


class PersistenceError(Exception):
    """Base exception for persistence operations."""
    pass


class ValidationError(PersistenceError):
    """Raised when validation fails."""
    pass


class CorruptionError(PersistenceError):
    """Raised when file corruption is detected."""
    pass


class BackupError(PersistenceError):
    """Raised when backup creation fails."""
    pass


class ReloadError(PersistenceError):
    """Raised when reloadability check fails."""
    pass


def _validate_json_syntax(data: dict[str, Any]) -> None:
    """
    Validate that data can be serialized to valid JSON.
    
    Args:
        data: Data to validate
    
    Raises:
        ValidationError: If data cannot be serialized to JSON
    """
    try:
        json.dumps(data)
    except (TypeError, ValueError) as e:
        raise ValidationError(f"Data cannot be serialized to JSON: {e}")


def _validate_override_schema(data: dict[str, Any], file_type: str) -> None:
    """
    Validate that override data matches expected structure.
    
    File types:
    - "tool": tools/{tool_id}.json
    - "language": languages/{language_id}.json
    - "override": overrides/{combo}.json
    
    Args:
        data: Override file content
        file_type: Type of override file
    
    Raises:
        ValidationError: If structure is invalid
    """
    required_fields: dict[str, list[str]] = {
        "tool": [],  # Tool files have flexible structure
        "language": [],  # Language files have flexible structure
        "override": [],  # Override files have flexible structure
    }
    
    optional_arrays = ["metadata_overrides", "field_overrides", "step_overrides"]
    
    # All override files should be dicts
    if not isinstance(data, dict):
        raise ValidationError(f"Override file must be JSON object, got {type(data).__name__}")
    
    # Validate override arrays if present
    for array_name in optional_arrays:
        if array_name in data:
            if not isinstance(data[array_name], list):
                raise ValidationError(
                    f"'{array_name}' must be array, got {type(data[array_name]).__name__}"
                )
            
            # Validate array items are objects
            for i, item in enumerate(data[array_name]):
                if not isinstance(item, dict):
                    raise ValidationError(
                        f"Item {i} in '{array_name}' must be object, got {type(item).__name__}"
                    )
    
    # Validate metadata_overrides items have required fields
    for i, override in enumerate(data.get("metadata_overrides", [])):
        if "field_id" not in override:
            raise ValidationError(
                f"metadata_overrides[{i}] missing 'field_id'"
            )
    
    # Validate field_overrides items have required fields
    for i, override in enumerate(data.get("field_overrides", [])):
        if "field_id" not in override:
            raise ValidationError(
                f"field_overrides[{i}] missing 'field_id'"
            )
    
    # Validate step_overrides items have required fields
    for i, override in enumerate(data.get("step_overrides", [])):
        if "step_id" not in override:
            raise ValidationError(
                f"step_overrides[{i}] missing 'step_id'"
            )


def _create_backup(file_path: Path) -> Path:
    """
    Create a backup of a file before modification.
    
    Backup is stored alongside original with .backup extension.
    Previous backup is overwritten.
    
    Args:
        file_path: File to backup
    
    Returns:
        Path to backup file
    
    Raises:
        BackupError: If backup creation fails
    """
    backup_path = file_path.with_suffix(file_path.suffix + ".backup")
    
    try:
        if file_path.exists():
            # Read original
            with file_path.open("r", encoding="utf-8") as f:
                content = f.read()
            
            # Write backup
            with backup_path.open("w", encoding="utf-8") as f:
                f.write(content)
        
        return backup_path
    except Exception as e:
        raise BackupError(f"Failed to create backup of {file_path}: {e}")


def _restore_backup(file_path: Path, backup_path: Path) -> None:
    """
    Restore a file from backup.
    
    Args:
        file_path: File to restore
        backup_path: Backup file to restore from
    
    Raises:
        BackupError: If restore fails
    """
    try:
        if backup_path.exists():
            with backup_path.open("r", encoding="utf-8") as f:
                content = f.read()
            with file_path.open("w", encoding="utf-8") as f:
                f.write(content)
        else:
            raise BackupError(f"Backup file not found: {backup_path}")
    except Exception as e:
        raise BackupError(f"Failed to restore {file_path} from {backup_path}: {e}")


def save_config(
    file_path: Path,
    data: dict[str, Any],
    validate: bool = True,
    create_backup: bool = True,
    verify_reloadable: bool = False,
    context: dict[str, Any] | None = None,
) -> None:
    """
    Save configuration data to file atomically and safely.
    
    Atomic write process:
    1. Create backup of existing file (optional)
    2. Validate data (optional)
    3. Write to temporary file
    4. Atomically replace original with temp file
    5. Verify reloadability (optional)
    6. Emit audit log entry (non-fatal)
    
    Args:
        file_path: Path to save to
        data: Data to save (must be JSON-serializable)
        validate: Whether to validate data against schema
        create_backup: Whether to create .backup file
        verify_reloadable: Whether to verify config can be reloaded
        context: Optional metadata for the audit log (e.g. scope, target, actor).
                 Does not affect the save operation itself.
    
    Raises:
        ValidationError: If validation fails
        CorruptionError: If file corruption is detected
        BackupError: If backup creation fails
        ReloadError: If reloadability check fails
        PersistenceError: If write fails
    """
    # Validate JSON serializability
    _validate_json_syntax(data)
    
    # Validate data structure against JSON Schema
    if validate:
        try:
            validate_config_file(file_path, data)
        except SchemaValidationError as e:
            raise ValidationError(f"Configuration validation failed: {e}")
    
    # Read current file content for the audit diff BEFORE any mutation
    before_data: dict[str, Any] | None = None
    if file_path.exists():
        try:
            with file_path.open("r", encoding="utf-8") as f:
                before_data = json.load(f)
        except Exception:
            before_data = None  # Treat unreadable existing file as a new file
    
    # Create backup
    backup_path = None
    if create_backup:
        backup_path = _create_backup(file_path)
    
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Write to temporary file in same directory (for atomic rename)
    temp_fd = None
    temp_path = None
    
    try:
        # Create temp file in same directory for atomic rename on same filesystem
        temp_fd, temp_path_str = tempfile.mkstemp(
            dir=file_path.parent,
            prefix=".tmp_",
            suffix=".json",
        )
        temp_path = Path(temp_path_str)
        
        # Close the file descriptor first
        import os
        os.close(temp_fd)
        
        # Write JSON to temp file
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        
        # Verify temp file is valid JSON
        try:
            with temp_path.open("r", encoding="utf-8") as f:
                json.load(f)
        except json.JSONDecodeError as e:
            raise CorruptionError(
                f"Temp file has invalid JSON (before atomic rename): {e}"
            )
        
        # Atomic replace: rename temp to target
        # On POSIX systems, rename is atomic
        # On Windows, remove target first then rename
        try:
            temp_path.replace(file_path)
        except Exception as e:
            raise PersistenceError(
                f"Failed to atomically write to {file_path}: {e}"
            )
        
        # Verify file is readable
        try:
            with file_path.open("r", encoding="utf-8") as f:
                json.load(f)
        except Exception as e:
            # Attempt to restore from backup
            if backup_path:
                try:
                    _restore_backup(file_path, backup_path)
                except BackupError:
                    pass  # Already logged in _restore_backup
            raise CorruptionError(
                f"Written file is not valid JSON: {e}"
            )
        
        # Verify reloadability if needed
        inferred_file_type = (
            "tool" if "/tools/" in str(file_path)
            else "language" if "/languages/" in str(file_path)
            else "override" if "/overrides/" in str(file_path)
            else "unknown"
        )
        if verify_reloadable and inferred_file_type != "unknown":
            try:
                _verify_config_reloadable(file_path, inferred_file_type)
            except Exception as e:
                # Attempt rollback
                if backup_path:
                    try:
                        _restore_backup(file_path, backup_path)
                    except BackupError:
                        pass
                raise ReloadError(f"Config not reloadable after save: {e}")

        # Emit audit log entry — non-fatal: a log failure must never block a save
        try:
            from app.services.audit_log import append_audit_entry, build_audit_entry
            entry = build_audit_entry(
                file_path=file_path,
                before_data=before_data,
                after_data=data,
                context=context,
                actor=(context or {}).get("actor", "system"),
            )
            append_audit_entry(entry)
        except Exception as audit_exc:  # noqa: BLE001
            print(f"[audit] WARNING: failed to write audit entry: {audit_exc}", file=__import__('sys').stderr)
    
    except Exception:
        # Cleanup temp file if it exists
        if temp_path and temp_path.exists():
            try:
                temp_path.unlink()
            except:
                pass
        raise


def _verify_config_reloadable(file_path: Path, file_type: str) -> None:
    """
    Verify that a configuration file can be reloaded successfully.
    
    For language and tool overrides, this is a basic check.
    For full configs, this would load via composable system.
    
    Args:
        file_path: File to verify
        file_type: "tool", "language", or "override"
    
    Raises:
        ReloadError: If file cannot be reloaded
    """
    try:
        # Basic JSON validation
        with file_path.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        # For override files, just validate structure
        if file_type in ["tool", "language", "override"]:
            _validate_override_schema(data, file_type)
    
    except json.JSONDecodeError as e:
        raise ReloadError(f"Invalid JSON in {file_path}: {e}")
    except ValidationError as e:
        raise ReloadError(f"Invalid override structure in {file_path}: {e}")
    except Exception as e:
        raise ReloadError(f"Failed to verify reloadability of {file_path}: {e}")


def verify_changes_reloadable(tool_id: str, language_id: str) -> bool:
    """
    Verify that a tool+language configuration can be loaded after changes.
    
    This performs an end-to-end load via the composable system to ensure
    all layers load correctly together.
    
    Args:
        tool_id: Tool identifier (e.g., "claude")
        language_id: Language identifier (e.g., "python")
    
    Returns:
        True if config loads successfully
    
    Raises:
        ReloadError: If config cannot be loaded
    """
    try:
        config = load_composable_config(tool_id, language_id)
        
        # Verify config has expected structure
        if not config.get("steps"):
            raise ReloadError("Loaded config has no steps")
        
        return True
    
    except Exception as e:
        raise ReloadError(
            f"Failed to load composable config ({tool_id}, {language_id}): {e}"
        )


def _apply_tag_remap(presets: list[dict[str, Any]], tag_remap: dict[str, str]) -> None:
    """Replace tags in a list of presets according to a remap dictionary (in-place)."""
    for preset in presets:
        old_tags: list[str] = preset.get("tags", [])
        if old_tags:
            preset["tags"] = [tag_remap.get(t, t) for t in old_tags]


def get_language_tags(language_id: str) -> list[str]:
    """
    Return the set of unique tags used across all presets in a language config.

    Inspects ``merge_presets`` and ``replace_presets_with`` lists inside
    ``field_overrides``.

    Args:
        language_id: Existing language identifier.

    Returns:
        Sorted list of unique tag strings.

    Raises:
        ValidationError: If the language file does not exist.
    """
    lang_path = DATA_DIR / "languages" / f"{language_id}.json"
    if not lang_path.exists():
        raise ValidationError(f"Language '{language_id}' not found.")
    with lang_path.open(encoding="utf-8") as f:
        data = json.load(f)
    tags: set[str] = set()
    for fo in data.get("field_overrides", []):
        for preset in fo.get("merge_presets", []):
            tags.update(preset.get("tags", []))
        for preset in fo.get("replace_presets_with", []):
            tags.update(preset.get("tags", []))
    return sorted(tags)


def create_language_config(
    language_id: str,
    title: str,
    description: str = "",
    based_on: str | None = None,
    tag_remap: dict[str, str] | None = None,
) -> dict[str, Any]:
    """
    Create a new language configuration file.

    Scaffolds a valid languages/{language_id}.json, optionally copying all
    override sections from an existing language as a starting point.

    When ``based_on`` is set and no ``tag_remap`` is supplied, any preset tags
    equal to ``based_on`` are automatically renamed to ``language_id``
    (the previous implicit behaviour).  Pass an explicit ``tag_remap`` dict to
    control exactly which tags are renamed (e.g. ``{"python": "django",
    "py": "dj"}``).

    Args:
        language_id: Unique identifier (e.g. 'python-datascience', 'haskell').
                     Must be lowercase, alphanumeric, hyphens allowed.
        title: Human-readable display name (e.g. 'Python – Data Science').
        description: Optional description shown in the UI.
        based_on: Optional existing language_id to copy overrides from.
        tag_remap: Optional mapping of old tag → new tag applied to every
                   preset in all override sections.

    Returns:
        The newly created config dict.

    Raises:
        ValidationError: If language_id already exists or is invalid.
        PersistenceError: If the file cannot be written.
    """
    import re

    if not re.fullmatch(r"[a-z0-9][a-z0-9\-]*", language_id):
        raise ValidationError(
            "language_id must be lowercase alphanumeric with hyphens only "
            f"(e.g. 'python-datascience'). Got: {language_id!r}"
        )

    languages_dir = DATA_DIR / "languages"
    target_path = languages_dir / f"{language_id}.json"

    if target_path.exists():
        raise ValidationError(
            f"Language '{language_id}' already exists. "
            "Choose a different id or edit the existing config."
        )

    # Build scaffold — start empty, optionally copy from base language
    field_overrides: list[dict[str, Any]] = []
    metadata_overrides: list[dict[str, Any]] = []
    step_overrides: list[dict[str, Any]] = []

    if based_on:
        based_on_path = languages_dir / f"{based_on}.json"
        if not based_on_path.exists():
            raise ValidationError(f"Base language '{based_on}' not found.")
        with based_on_path.open(encoding="utf-8") as f:
            base_data = json.load(f)
        # Deep-copy ALL override sections — do NOT copy metadata like language_id/applies_to
        field_overrides = deepcopy(base_data.get("field_overrides", []))
        metadata_overrides = deepcopy(base_data.get("metadata_overrides", []))
        step_overrides = deepcopy(base_data.get("step_overrides", []))

        # Build the effective tag remap: default is based_on → language_id
        effective_remap: dict[str, str] = tag_remap if tag_remap is not None else {based_on: language_id}
        if effective_remap:
            for fo in field_overrides:
                _apply_tag_remap(fo.get("merge_presets", []), effective_remap)
                _apply_tag_remap(fo.get("replace_presets_with", []), effective_remap)

    new_config: dict[str, Any] = {
        "language_id": language_id,
        "version": "1.0",
        "metadata": {
            "title": title,
            "description": description,
        },
        "applies_to": {
            "languages": [language_id],
        },
        "field_overrides": field_overrides,
        "metadata_overrides": metadata_overrides,
        "step_overrides": step_overrides,
    }

    save_config(
        target_path,
        new_config,
        validate=True,
        create_backup=False,   # Nothing to back up — file is brand new
        verify_reloadable=False,
    )

    return new_config


def save_patch_result(
    scope: str,
    target: str,
    data: dict[str, Any],
) -> None:
    """
    Save patched configuration data to appropriate file.
    
    Helper function for patch engine to save results atomically.
    
    Args:
        scope: "tool", "language", or "override"
        target: Tool/language ID or combo
        data: Modified configuration data
    
    Raises:
        PersistenceError: If save fails
    """
    if scope == "tool":
        file_path = DATA_DIR / "tools" / f"{target}.json"
    elif scope == "language":
        file_path = DATA_DIR / "languages" / f"{target}.json"
    elif scope == "override":
        file_path = DATA_DIR / "overrides" / f"{target}.json"
    else:
        raise PersistenceError(f"Invalid scope: {scope}")
    
    save_config(
        file_path,
        data,
        validate=True,
        create_backup=True,
        verify_reloadable=False,
        context={"scope": scope, "target": target},
    )


class ConfigTransaction:
    """
    Transactional wrapper for multiple configuration changes.
    
    Allows grouping multiple changes together with rollback capability.
    
    Example:
        ```python
        with ConfigTransaction() as tx:
            tx.update_field_metadata(...)
            tx.update_step_visibility(...)
            # Auto-commits on success, rolls back on exception
        ```
    """
    
    def __init__(self) -> None:
        self.changes: dict[str, dict[str, Any]] = {}  # file_path -> data
        self.backups: dict[Path, Path] = {}  # file_path -> backup_path
    
    def __enter__(self) -> "ConfigTransaction":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> bool:
        if exc_type is not None:
            # Rollback on exception
            self.rollback()
            return False
        else:
            # Commit on success
            self.commit()
            return True
    
    def update_file(self, file_path: Path, data: dict[str, Any]) -> None:
        """
        Queue a file update within this transaction.
        
        Args:
            file_path: File to update
            data: Updated data
        """
        self.changes[str(file_path)] = data
    
    def commit(self) -> None:
        """
        Commit all queued changes atomically.
        
        Raises:
            PersistenceError: If any commit fails
        """
        # First, create backups and validate all changes
        for file_path_str, data in self.changes.items():
            file_path = Path(file_path_str)
            
            # Validate data
            _validate_json_syntax(data)
            
            # Determine file type and validate structure
            if "tools" in str(file_path):
                file_type = "tool"
            elif "languages" in str(file_path):
                file_type = "language"
            elif "overrides" in str(file_path):
                file_type = "override"
            else:
                file_type = "unknown"
            
            if file_type != "unknown":
                _validate_override_schema(data, file_type)
            
            # Create backup
            backup_path = _create_backup(file_path)
            self.backups[file_path] = backup_path
        
        # All validations passed, now commit
        for file_path_str, data in self.changes.items():
            file_path = Path(file_path_str)
            
            try:
                # Write atomically (no backup or verify, already done)
                temp_fd, temp_path_str = tempfile.mkstemp(
                    dir=file_path.parent,
                    prefix=".tmp_",
                    suffix=".json",
                )
                temp_path = Path(temp_path_str)
                
                # Close the file descriptor
                import os
                os.close(temp_fd)
                
                with temp_path.open("w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
                
                temp_path.replace(file_path)
            
            except Exception as e:
                # Rollback all changes made so far
                self.rollback()
                raise PersistenceError(
                    f"Failed to commit change to {file_path}: {e}"
                )
    
    def rollback(self) -> None:
        """
        Rollback all queued changes by restoring backups.
        """
        for file_path, backup_path in self.backups.items():
            try:
                _restore_backup(file_path, backup_path)
            except BackupError as e:
                # Log but don't fail - try to restore others
                pass


# ---------------------------------------------------------------------------
# Named snapshot store
# ---------------------------------------------------------------------------
# Snapshots are stored at:
#   data/wizard_configs/snapshots/{scope}/{target}/{snapshot_id}.json
#
# Each snapshot file is a wrapper:
#   {
#     "meta": { "snapshot_id": "...", "name": "...", "created_at": "...",
#               "scope": "...", "target": "..." },
#     "data": { ...full config file content... }
#   }
# ---------------------------------------------------------------------------

SNAPSHOTS_DIR = DATA_DIR / "snapshots"

_VALID_SCOPES = frozenset({"tool", "language", "override"})


class SnapshotError(PersistenceError):
    """Raised for snapshot-specific errors."""
    pass


def _source_path_for(scope: str, target: str) -> Path:
    """Return the live config file path for a given scope+target."""
    if scope == "tool":
        return DATA_DIR / "tools" / f"{target}.json"
    elif scope == "language":
        return DATA_DIR / "languages" / f"{target}.json"
    elif scope == "override":
        return DATA_DIR / "overrides" / f"{target}.json"
    raise SnapshotError(f"Invalid scope '{scope}'. Must be one of: tool, language, override")


def _snapshot_dir(scope: str, target: str) -> Path:
    return SNAPSHOTS_DIR / scope / target


def _slugify(name: str) -> str:
    """Convert a human name to a filename-safe slug."""
    import re
    slug = name.lower().strip()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug or "snapshot"


def _make_snapshot_id(name: str) -> str:
    """Generate a sortable, unique snapshot ID from a name."""
    from datetime import datetime, timezone
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}_{_slugify(name)}"


def create_snapshot(scope: str, target: str, name: str) -> dict[str, Any]:
    """
    Create a named snapshot of the current config file for scope+target.

    Args:
        scope: "tool", "language", or "override"
        target: e.g. "python", "claude"
        name: Human-readable label, e.g. "before Python migration"

    Returns:
        Snapshot metadata dict (without the data payload).

    Raises:
        SnapshotError: If the source file does not exist or write fails.
    """
    if scope not in _VALID_SCOPES:
        raise SnapshotError(f"Invalid scope '{scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")

    source = _source_path_for(scope, target)
    if not source.exists():
        raise SnapshotError(f"Source config not found: {source}")

    with source.open("r", encoding="utf-8") as f:
        current_data = json.load(f)

    snapshot_id = _make_snapshot_id(name)

    from datetime import datetime, timezone
    meta: dict[str, Any] = {
        "snapshot_id": snapshot_id,
        "name": name,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope": scope,
        "target": target,
    }

    snapshot: dict[str, Any] = {"meta": meta, "data": current_data}

    snap_dir = _snapshot_dir(scope, target)
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_path = snap_dir / f"{snapshot_id}.json"

    try:
        # Write atomically
        import os
        temp_fd, temp_path_str = tempfile.mkstemp(dir=snap_dir, prefix=".tmp_", suffix=".json")
        temp_path = Path(temp_path_str)
        os.close(temp_fd)
        with temp_path.open("w", encoding="utf-8") as f:
            json.dump(snapshot, f, indent=2)
        temp_path.replace(snap_path)
    except Exception as e:
        raise SnapshotError(f"Failed to write snapshot: {e}")

    return meta


def list_snapshots(scope: str, target: str) -> list[dict[str, Any]]:
    """
    List all snapshots for a given scope+target, newest first.

    Returns:
        List of snapshot metadata dicts (no data payload).
    """
    if scope not in _VALID_SCOPES:
        raise SnapshotError(f"Invalid scope '{scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")

    snap_dir = _snapshot_dir(scope, target)
    if not snap_dir.exists():
        return []

    metas: list[dict[str, Any]] = []
    for snap_path in sorted(snap_dir.glob("*.json"), reverse=True):
        try:
            with snap_path.open("r", encoding="utf-8") as f:
                snapshot = json.load(f)
            metas.append(snapshot["meta"])
        except Exception:
            # Skip corrupt snapshot files silently
            continue

    return metas


def restore_snapshot(scope: str, target: str, snapshot_id: str) -> dict[str, Any]:
    """
    Restore a named snapshot, replacing the live config file.

    Creates a pre-restore backup of the current file before overwriting it.

    Args:
        scope: "tool", "language", or "override"
        target: e.g. "python", "claude"
        snapshot_id: The snapshot_id returned from create_snapshot / list_snapshots

    Returns:
        The restored snapshot metadata dict.

    Raises:
        SnapshotError: If snapshot not found or restore fails.
    """
    if scope not in _VALID_SCOPES:
        raise SnapshotError(f"Invalid scope '{scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")

    snap_path = _snapshot_dir(scope, target) / f"{snapshot_id}.json"
    if not snap_path.exists():
        raise SnapshotError(f"Snapshot not found: {snapshot_id}")

    with snap_path.open("r", encoding="utf-8") as f:
        snapshot = json.load(f)

    data = snapshot.get("data")
    if not isinstance(data, dict):
        raise SnapshotError(f"Snapshot '{snapshot_id}' has invalid data payload")

    source = _source_path_for(scope, target)

    # Persist — creates a .backup of current state and writes atomically
    save_config(
        source,
        data,
        validate=False,
        create_backup=True,
        verify_reloadable=False,
        context={
            "scope": scope,
            "target": target,
            "action": "snapshot_restore",
            "snapshot_id": snapshot_id,
            "snapshot_name": snapshot.get("meta", {}).get("name", ""),
        },
    )

    return cast(dict[str, Any], snapshot["meta"])


def delete_snapshot(scope: str, target: str, snapshot_id: str) -> None:
    """
    Permanently delete a named snapshot.

    Raises:
        SnapshotError: If snapshot not found or deletion fails.
    """
    if scope not in _VALID_SCOPES:
        raise SnapshotError(f"Invalid scope '{scope}'. Must be one of: {', '.join(sorted(_VALID_SCOPES))}")

    snap_path = _snapshot_dir(scope, target) / f"{snapshot_id}.json"
    if not snap_path.exists():
        raise SnapshotError(f"Snapshot not found: {snapshot_id}")

    try:
        snap_path.unlink()
    except Exception as e:
        raise SnapshotError(f"Failed to delete snapshot: {e}")
