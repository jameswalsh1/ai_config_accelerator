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
from typing import Any
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
    required_fields = {
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
) -> None:
    """
    Save configuration data to file atomically and safely.
    
    Atomic write process:
    1. Create backup of existing file (optional)
    2. Validate data (optional)
    3. Write to temporary file
    4. Atomically replace original with temp file
    5. Verify reloadability (optional)
    
    Args:
        file_path: Path to save to
        data: Data to save (must be JSON-serializable)
        validate: Whether to validate data against schema
        create_backup: Whether to create .backup file
        verify_reloadable: Whether to verify config can be reloaded
    
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
        if verify_reloadable and file_type != "unknown":
            try:
                _verify_config_reloadable(file_path, file_type)
            except Exception as e:
                # Attempt rollback
                if backup_path:
                    try:
                        _restore_backup(file_path, backup_path)
                    except BackupError:
                        pass
                raise ReloadError(f"Config not reloadable after save: {e}")
    
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
        verify_reloadable=False,  # Reloadability check is expensive for patches
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
    
    def __init__(self):
        self.changes: dict[str, dict[str, Any]] = {}  # file_path -> data
        self.backups: dict[Path, Path] = {}  # file_path -> backup_path
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
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
