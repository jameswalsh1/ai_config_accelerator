"""
JSON Schema Validation Layer for configuration files.

Validates all config files against JSON Schema before loading or saving.
Provides clear error messages for validation failures.
"""

import json
from pathlib import Path
from typing import Any, Optional, cast

DATA_DIR = Path(__file__).parent.parent.parent / "tests" / "wizard_configs"


class SchemaValidationError(Exception):
    """Raised when schema validation fails."""
    pass


class SchemaLoadError(Exception):
    """Raised when schema file cannot be loaded."""
    pass


class _SchemaCache:
    """Caches loaded JSON schemas to avoid repeated file I/O."""
    
    def __init__(self) -> None:
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
    
    def clear(self) -> None:
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


def _validate_override_arrays(data: dict[str, Any]) -> None:
    """Validate the three standard override arrays shared by all override file types."""
    for key, required_key in [
        ("metadata_overrides", "field_id"),
        ("field_overrides", "field_id"),
        ("step_overrides", "step_id"),
    ]:
        if key in data:
            _validate_array_items(data[key], {}, key, required_key)


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
    _validate_required_fields(data, ["tool_id"])
    _validate_override_arrays(data)


def validate_language_override(data: dict[str, Any]) -> None:
    """
    Validate language override file (languages/*.json).
    
    Args:
        data: The language override data to validate
    
    Raises:
        SchemaValidationError: If validation fails
    """
    _validate_required_fields(data, ["language_id"])
    _validate_override_arrays(data)


def validate_combo_override(data: dict[str, Any]) -> None:
    """
    Validate tool+language override file (overrides/*.json).
    
    Args:
        data: The combo override data to validate
    
    Raises:
        SchemaValidationError: If validation fails
    """
    _validate_override_arrays(data)


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


def validate_override_references(schema_data: dict[str, Any], override_data: dict[str, Any], source: str) -> list[str]:
    """
    Validate that field_id and step_id references in an override file
    actually exist in the base schema.

    Args:
        schema_data: The base wizard schema dict (must have 'steps')
        override_data: The override dict to validate
        source: Human-readable source name for error messages

    Returns:
        List of warning strings for unresolvable references.
        Empty list means all references are valid.
    """
    # Build index of valid step IDs and field paths
    valid_step_ids: set[str] = set()
    valid_field_paths: set[str] = set()

    for step in schema_data.get("steps", []):
        step_id = step.get("id", "")
        if step_id:
            valid_step_ids.add(step_id)
            for field in step.get("fields", []):
                _collect_field_paths(step_id, field, valid_field_paths)

    warnings: list[str] = []

    # Check metadata_overrides
    for entry in override_data.get("metadata_overrides", []):
        field_id = entry.get("field_id", "")
        if field_id and field_id not in valid_field_paths:
            warnings.append(f"{source}: metadata_overrides references unknown field '{field_id}'")

    # Check field_overrides
    for entry in override_data.get("field_overrides", []):
        field_id = entry.get("field_id", "")
        if field_id and field_id not in valid_field_paths:
            warnings.append(f"{source}: field_overrides references unknown field '{field_id}'")

    # Check step_overrides
    for entry in override_data.get("step_overrides", []):
        step_id = entry.get("step_id", "")
        if step_id and step_id not in valid_step_ids:
            warnings.append(f"{source}: step_overrides references unknown step '{step_id}'")

    return warnings


def _collect_field_paths(prefix: str, field: dict[str, Any], paths: set[str]) -> None:
    """Recursively collect valid field paths like 'step_id.field_id'."""
    field_id = field.get("id", "")
    if field_id:
        path = f"{prefix}.{field_id}"
        paths.add(path)
        for nested in field.get("fields", []):
            _collect_field_paths(path, nested, paths)


def _load_schema_steps() -> list[dict[str, Any]]:
    """Load steps from schema.json for reference validation."""
    schema_file = DATA_DIR / "schema.json"
    if not schema_file.exists():
        return []
    with schema_file.open(encoding="utf-8") as f:
        schema = json.load(f)
    return cast(list[dict[str, Any]], schema.get("steps", []))


def _build_valid_step_ids(steps: list[dict[str, Any]]) -> set[str]:
    return {step["id"] for step in steps if "id" in step}


def _build_valid_field_paths(steps: list[dict[str, Any]]) -> set[str]:
    paths: set[str] = set()
    for step in steps:
        step_id = step.get("id", "")
        if step_id:
            for field in step.get("fields", []):
                _collect_field_paths(step_id, field, paths)
    return paths


def validate_step_id_exists(step_id: str) -> None:
    """
    Raise SchemaValidationError if step_id does not exist in schema.json.

    Args:
        step_id: The step ID to check.

    Raises:
        SchemaValidationError: When step_id is not found.
    """
    steps = _load_schema_steps()
    valid = _build_valid_step_ids(steps)
    if step_id not in valid:
        raise SchemaValidationError(
            f"step_id '{step_id}' does not exist in schema. "
            f"Valid step IDs: {sorted(valid)}"
        )


def validate_field_id_exists(step_id: str, field_id: str) -> None:
    """
    Raise SchemaValidationError if the field path (step_id.field_id) does not
    exist in schema.json.

    Args:
        step_id: The step containing the field.
        field_id: The field ID within the step (may be nested with dots).

    Raises:
        SchemaValidationError: When the field path is not found.
    """
    steps = _load_schema_steps()
    valid_steps = _build_valid_step_ids(steps)

    if step_id not in valid_steps:
        raise SchemaValidationError(
            f"step_id '{step_id}' does not exist in schema. "
            f"Valid step IDs: {sorted(valid_steps)}"
        )

    valid_fields = _build_valid_field_paths(steps)
    full_path = f"{step_id}.{field_id}"
    if full_path not in valid_fields:
        raise SchemaValidationError(
            f"field_id '{field_id}' does not exist in step '{step_id}'. "
            f"Valid field paths: {sorted(p for p in valid_fields if p.startswith(step_id + '.'))}"
        )

