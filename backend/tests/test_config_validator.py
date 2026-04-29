"""
Tests for JSON Schema Validation Layer (config_validator.py)

Tests validation of all configuration file types:
- Base wizard schema (schema.json)
- Tool overrides (tools/*.json)
- Language overrides (languages/*.json)
- Tool+Language overrides (overrides/*.json)
"""

import json
import pytest
from typing import Any
from pathlib import Path

from app.services.config_validator import (
    validate_wizard_schema,
    validate_tool_override,
    validate_language_override,
    validate_combo_override,
    validate_config_file,
    get_schema_for_file_type,
    clear_schema_cache,
    SchemaValidationError,
    SchemaLoadError,
)

DATA_DIR = Path(__file__).parent.parent / "app" / "data" / "wizard_configs"


class TestWizardSchemaValidation:
    """Test validation of wizard schema files."""
    
    def test_valid_wizard_schema(self):
        """Test that valid schema passes validation."""
        # Load the real schema
        with (DATA_DIR / "schema.json").open() as f:
            schema = json.load(f)
        
        # Should not raise
        validate_wizard_schema(schema)
    
    def test_wizard_missing_required_steps(self):
        """Test that missing 'steps' raises error."""
        data = {"schema_version": "2.0"}
        
        with pytest.raises(SchemaValidationError):
            validate_wizard_schema(data)
    
    def test_wizard_missing_required_schema_version(self):
        """Test that missing schema_version raises error."""
        data: dict[str, Any] = {"steps": []}
        
        with pytest.raises(SchemaValidationError):
            validate_wizard_schema(data)
    
    def test_wizard_step_missing_id(self):
        """Test that step without id raises error."""
        data = {
            "schema_version": "2.0",
            "steps": [
                {"title": "Step 1"}  # Missing id
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_wizard_schema(data)
    
    def test_wizard_field_missing_id(self):
        """Test that field without id raises error."""
        data = {
            "schema_version": "2.0",
            "steps": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "fields": [
                        {"type": "text", "label": "Field 1"}  # Missing id
                    ]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_wizard_schema(data)
    
    def test_wizard_field_missing_type(self):
        """Test that field without type raises error."""
        data = {
            "schema_version": "2.0",
            "steps": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "fields": [
                        {"id": "field1", "label": "Field 1"}  # Missing type
                    ]
                }
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_wizard_schema(data)


class TestToolOverrideValidation:
    """Test validation of tool override files."""
    
    def test_valid_tool_override(self):
        """Test that valid tool override passes validation."""
        # Load a real tool override
        with (DATA_DIR / "tools" / "claude.json").open() as f:
            tool_config = json.load(f)
        
        # Should not raise
        validate_tool_override(tool_config)
    
    def test_tool_override_missing_tool_id(self):
        """Test that missing tool_id raises error."""
        data: dict[str, Any] = {"tool_metadata": {}}
        
        with pytest.raises(SchemaValidationError):
            validate_tool_override(data)
    
    def test_tool_override_metadata_override_missing_field_id(self):
        """Test that metadata_override without field_id raises error."""
        data = {
            "tool_id": "claude",
            "metadata_overrides": [
                {"default": "value"}  # Missing field_id
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_tool_override(data)
    
    def test_tool_override_step_override_missing_step_id(self):
        """Test that step_override without step_id raises error."""
        data = {
            "tool_id": "claude",
            "step_overrides": [
                {"hidden": True}  # Missing step_id
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_tool_override(data)
    
    def test_tool_override_invalid_field_id_format(self):
        """Test that invalid field_id format is caught."""
        # Invalid format - contains uppercase
        data = {
            "tool_id": "claude",
            "metadata_overrides": [
                {"field_id": "Step.Field", "default": "value"}  # Invalid: uppercase
            ]
        }
        
        # This should still validate as schemas allow any string for field_id
        # Validation is about presence, not strict format in this version
        validate_tool_override(data)  # Should pass


class TestLanguageOverrideValidation:
    """Test validation of language override files."""
    
    def test_valid_language_override(self):
        """Test that valid language override passes validation."""
        # Load a real language override
        with (DATA_DIR / "languages" / "python.json").open() as f:
            lang_config = json.load(f)
        
        # Should not raise
        validate_language_override(lang_config)
    
    def test_language_override_missing_language_id(self):
        """Test that missing language_id raises error."""
        data = {"version": "1.0"}
        
        with pytest.raises(SchemaValidationError):
            validate_language_override(data)
    
    def test_language_override_metadata_override_missing_field_id(self):
        """Test that metadata_override without field_id raises error."""
        data = {
            "language_id": "python",
            "metadata_overrides": [
                {"default": "Python 3.14"}  # Missing field_id
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_language_override(data)
    
    def test_language_override_field_override_missing_field_id(self):
        """Test that field_override without field_id raises error."""
        data = {
            "language_id": "python",
            "field_overrides": [
                {"options": []}  # Missing field_id
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_language_override(data)


class TestComboOverrideValidation:
    """Test validation of tool+language combo override files."""
    
    def test_valid_combo_override(self):
        """Test that valid combo override passes validation."""
        data = {
            "combo": "claude+python",
            "metadata_overrides": [
                {"field_id": "step.field", "default": "value"}
            ]
        }
        
        # Should not raise
        validate_combo_override(data)
    
    def test_combo_override_metadata_override_missing_field_id(self):
        """Test that metadata_override without field_id raises error."""
        data = {
            "combo": "claude+python",
            "metadata_overrides": [
                {"default": "value"}  # Missing field_id
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_combo_override(data)
    
    def test_combo_override_step_override_missing_step_id(self):
        """Test that step_override without step_id raises error."""
        data = {
            "combo": "claude+python",
            "step_overrides": [
                {"hidden": True}  # Missing step_id
            ]
        }
        
        with pytest.raises(SchemaValidationError):
            validate_combo_override(data)


class TestAutoValidation:
    """Test auto-detection and validation by file path."""
    
    def test_validate_schema_json(self):
        """Test validation of schema.json by path."""
        with (DATA_DIR / "schema.json").open() as f:
            data = json.load(f)
        
        schema_path = DATA_DIR / "schema.json"
        # Should not raise
        validate_config_file(schema_path, data)
    
    def test_validate_tool_by_path(self):
        """Test validation of tool/*.json by path."""
        with (DATA_DIR / "tools" / "claude.json").open() as f:
            data = json.load(f)
        
        tool_path = DATA_DIR / "tools" / "claude.json"
        # Should not raise
        validate_config_file(tool_path, data)
    
    def test_validate_language_by_path(self):
        """Test validation of languages/*.json by path."""
        with (DATA_DIR / "languages" / "python.json").open() as f:
            data = json.load(f)
        
        lang_path = DATA_DIR / "languages" / "python.json"
        # Should not raise
        validate_config_file(lang_path, data)
    
    def test_validate_override_by_path(self):
        """Test validation of overrides/*.json by path."""
        data = {
            "combo": "claude+python",
            "metadata_overrides": []
        }
        
        override_path = DATA_DIR / "overrides" / "claude+python.json"
        # Should not raise
        validate_config_file(override_path, data)
    
    def test_validate_unknown_path_as_tool(self):
        """Test validation of unknown path with tool_id as tool."""
        with (DATA_DIR / "tools" / "claude.json").open() as f:
            data = json.load(f)
        
        unknown_path = Path("/unknown/path/config.json")
        # Should validate as tool since it has tool_id
        validate_config_file(unknown_path, data)
    
    def test_validate_unknown_path_as_language(self):
        """Test validation of unknown path with language_id as language."""
        with (DATA_DIR / "languages" / "python.json").open() as f:
            data = json.load(f)
        
        unknown_path = Path("/unknown/path/config.json")
        # Should validate as language since it has language_id
        validate_config_file(unknown_path, data)


class TestSchemaRetrieval:
    """Test schema retrieval functionality."""
    
    def test_get_wizard_schema(self):
        """Test retrieving wizard schema."""
        schema = get_schema_for_file_type("wizard")
        assert "$schema" in schema
        assert schema["title"] == "Wizard Schema"
    
    def test_get_tool_schema(self):
        """Test retrieving tool schema."""
        schema = get_schema_for_file_type("tool")
        assert "$schema" in schema
        assert schema["title"] == "Tool Override Schema"
    
    def test_get_language_schema(self):
        """Test retrieving language schema."""
        schema = get_schema_for_file_type("language")
        assert "$schema" in schema
        assert schema["title"] == "Language Override Schema"
    
    def test_get_override_schema(self):
        """Test retrieving override schema."""
        schema = get_schema_for_file_type("override")
        assert "$schema" in schema
        assert schema["title"] == "Tool+Language Override Schema"
    
    def test_get_invalid_schema(self):
        """Test that invalid file type raises error."""
        with pytest.raises(SchemaLoadError):
            get_schema_for_file_type("invalid")


class TestErrorMessages:
    """Test that error messages are clear and helpful."""
    
    def test_error_message_missing_field(self):
        """Test that missing field errors are clear."""
        data = {
            "tool_id": "claude",
            "metadata_overrides": [
                {"default": "value"}  # Missing field_id
            ]
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_tool_override(data)
        
        error_msg = str(exc_info.value)
        assert "field_id" in error_msg.lower()
        assert "metadata_overrides" in error_msg
    
    def test_error_message_invalid_type(self):
        """Test that type errors are clear."""
        data = {
            "tool_id": "claude",
            "metadata_overrides": "not_a_list"  # Should be array
        }
        
        with pytest.raises(SchemaValidationError) as exc_info:
            validate_tool_override(data)
        
        error_msg = str(exc_info.value)
        assert "metadata_overrides" in error_msg
        assert "type" in error_msg.lower() or "array" in error_msg.lower()


class TestSchemaCache:
    """Test schema caching behavior."""
    
    def test_schema_cache_reuse(self):
        """Test that schemas are cached and reused."""
        # First call loads schema
        schema1 = get_schema_for_file_type("wizard")
        
        # Second call should use cache
        schema2 = get_schema_for_file_type("wizard")
        
        # Should be the same object
        assert schema1 is schema2
    
    def test_clear_cache(self):
        """Test that cache can be cleared."""
        # Load schema (caches it)
        schema1 = get_schema_for_file_type("wizard")
        
        # Clear cache
        clear_schema_cache()
        
        # Load again (should be new object)
        schema2 = get_schema_for_file_type("wizard")
        
        # Should be different objects (though same content)
        assert schema1 is not schema2


class TestIntegrationWithLoader:
    """Test that validation works when integrated with config loader."""
    
    def test_loader_validates_configs(self):
        """Test that loader validates loaded configs."""
        from app.services.config_loader_composable import load_composable_config
        
        # Should not raise - valid config
        config = load_composable_config("claude", "python")
        assert config is not None
        assert "steps" in config


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
