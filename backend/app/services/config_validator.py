"""
JSON Schema Validation Layer for configuration files.

Validates all config files against JSON Schema before loading or saving.
Provides clear error messages for validation failures.
"""

import json
from pathlib import Path
from typing import Any, Optional


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    pass


class SchemaLoadError(Exception):
    """Raised when schema file cannot be loaded."""
    pass


class _SchemaCache:
    """Caches loaded JSON schemas to avoid repeated file I/O."""
    
    def __init__(self):
        self._cache: dict[str, dict[str, Any]] = {}
    
    def get(self, schema_name: str) -> dict[str, Any]:
        """Load schema from cache or file."""
        if schema_name not in self._cache:
            schema_path = Path(__file__).parent.parent / "schemas" / f"{schema_name}.json"
            
            if not schema_path.exists():
                raise SchemaLoadError(f"Schema file not found: {schema_path}")
            
            try:
                with schema_path.open() as f:
                    self._cache[schema_name] = json.load(f)
            except json.JSONDecodeError as e:
                raise SchemaLoadError(f"Invalid JSON in schema {schema_name}: {e}")
            except Exception as e:
                raise SchemaLoadError(f"Failed to load schema {schema_name}: {e}")
        
        return self._cache[schema_name]
    
    def clear(self):
        """Clear the cache."""
        self._cache.clear()


# Global schema cache
_schema_cache = _SchemaCache()


def _validate_required_fields(data: Any, required_fields: list[str], path: str = "root") -> None:
    """Validate that required fields are present."""
    if not isinstance(data, dict):
        raise SchemaValidationError(f"Expected object at {path}, got {type(data).__name__}")
    
    missing = [f for f in required_fields if f not in data]
    if missing:
        raise SchemaValidationError(
            f"Missing required field(s) at {path}: {', '.join(sorted(missing))}"
        )


def _validate_array_items(items: Any, item_schema: dict[str, Any], path: str, required_key: str) -> None:
    """Validate array items have required field."""
    if not isinstance(items, list):
        raise SchemaValidationError(
            f"Expected array at {path}, got {type(items).__name__}"
        )
    
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise SchemaValidationError(
                f"Item {i} in {path} must be object, got {type(item).__name__}"
            )
        if required_key not in item:
            raise SchemaValidationError(
                f"Item {i} in {path} missing '{required_key}'"
            )


def validate_wizard_schema(data: dict[str, Any]) -> None:
    """
    Validate base wizard schema (schema.json).
    
    Args:
        data: The schema data to validate
    
    Raises:
        SchemaValidationError: If validation fails
    """
    # Check required fields
    _validate_required_fields(data, ["schema_version", "steps"])
    
    # Validate steps array
    if not isinstance(data.get("steps"), list):
        raise SchemaValidationError("'steps' must be an array")
    
    # Validate each step
    for i, step in enumerate(data["steps"]):
        _validate_required_fields(step, ["id", "title"], f"steps[{i}]")
        
        # Validate fields if present
        if "fields" in step:
            if not isinstance(step["fields"], list):
                raise SchemaValidationError(f"steps[{i}].fields must be an array")
            
            for j, field in enumerate(step["fields"]):
                _validate_required_fields(
                    field, ["id", "type", "label"], 
                    f"steps[{i}].fields[{j}]"
                )


def validate_tool_override(data: dict[str, Any]) -> None:
    """
    Validate tool override file (tools/*.json).
    
    Args:
        data: The tool override data to validate
    
    Raises:
        SchemaValidationError: If validation fails
    """
    # Check required fields
    _validate_required_fields(data, ["tool_id"])
    
    # Validate metadata_overrides if present
    if "metadata_overrides" in data:
        _validate_array_items(
            data["metadata_overrides"], 
            {},
            "metadata_overrides",
            "field_id"
        )
    
    # Validate field_overrides if present
    if "field_overrides" in data:
        _validate_array_items(
            data["field_overrides"],
            {},
            "field_overrides",
            "field_id"
        )
    
    # Validate step_overrides if present
    if "step_overrides" in data:
        _validate_array_items(
            data["step_overrides"],
            {},
            "step_overrides",
            "step_id"
        )


def validate_language_override(data: dict[str, Any]) -> None:
    """
    Validate language override file (languages/*.json).
    
    Args:
        data: The language override data to validate
    
    Raises:
        SchemaValidationError: If validation fails
    """
    # Check required fields
    _validate_required_fields(data, ["language_id"])
    
    # Validate metadata_overrides if present
    if "metadata_overrides" in data:
        _validate_array_items(
            data["metadata_overrides"],
            {},
            "metadata_overrides",
            "field_id"
        )
    
    # Validate field_overrides if present
    if "field_overrides" in data:
        _validate_array_items(
            data["field_overrides"],
            {},
            "field_overrides",
            "field_id"
        )
    
    # Validate step_overrides if present
    if "step_overrides" in data:
        _validate_array_items(
            data["step_overrides"],
            {},
            "step_overrides",
            "step_id"
        )


def validate_combo_override(data: dict[str, Any]) -> None:
    """
    Validate tool+language override file (overrides/*.json).
    
    Args:
        data: The combo override data to validate
    
    Raises:
        SchemaValidationError: If validation fails
    """
    # Validate metadata_overrides if present
    if "metadata_overrides" in data:
        _validate_array_items(
            data["metadata_overrides"],
            {},
            "metadata_overrides",
            "field_id"
        )
    
    # Validate field_overrides if present
    if "field_overrides" in data:
        _validate_array_items(
            data["field_overrides"],
            {},
            "field_overrides",
            "field_id"
        )
    
    # Validate step_overrides if present
    if "step_overrides" in data:
        _validate_array_items(
            data["step_overrides"],
            {},
            "step_overrides",
            "step_id"
        )


def validate_config_file(file_path: Path, data: dict[str, Any]) -> None:
    """
    Automatically detect config file type and validate accordingly.
    
    Args:
        file_path: Path to the config file (used to detect type)
        data: The config data to validate
    
    Raises:
        SchemaValidationError: If validation fails
    """
    path_str = str(file_path)
    
    # Detect file type from path
    if "schema.json" in path_str:
        validate_wizard_schema(data)
    elif "tools/" in path_str or "tools\\" in path_str:
        validate_tool_override(data)
    elif "languages/" in path_str or "languages\\" in path_str:
        validate_language_override(data)
    elif "overrides/" in path_str or "overrides\\" in path_str:
        validate_combo_override(data)
    else:
        # Unknown file type - try to validate as override
        if "tool_id" in data:
            validate_tool_override(data)
        elif "language_id" in data:
            validate_language_override(data)
        else:
            # Assume wizard schema
            validate_wizard_schema(data)


def get_schema_for_file_type(file_type: str) -> dict[str, Any]:
    """
    Get the JSON schema for a specific file type.
    
    Args:
        file_type: One of "wizard", "tool", "language", "override"
    
    Returns:
        The JSON schema object
    
    Raises:
        SchemaLoadError: If schema cannot be loaded
    """
    schema_map = {
        "wizard": "schema_wizard",
        "tool": "schema_tool",
        "language": "schema_language",
        "override": "schema_override",
    }
    
    if file_type not in schema_map:
        raise SchemaLoadError(f"Unknown file type: {file_type}")
    
    return _schema_cache.get(schema_map[file_type])


def clear_schema_cache() -> None:
    """Clear the schema cache. Useful for testing."""
    _schema_cache.clear()

