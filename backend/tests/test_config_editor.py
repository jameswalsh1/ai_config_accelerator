"""Tests for config_editor service."""

import pytest

from app.services.config_editor import (
    get_editable_step,
    _enhance_field_with_metadata,
    _extract_source_tracking,
)


class TestGetEditableStep:
    def test_returns_step_and_source_tracking(self):
        """Verify returned structure."""
        config = {
            "id": "test",
            "steps": [
                {
                    "id": "test_step",
                    "title": "Test Step",
                    "fields": [
                        {
                            "id": "field1",
                            "type": "text",
                            "label": "Field 1",
                            "default": "value1",
                            "editability": "free",
                            "override_source": "schema",
                        }
                    ],
                }
            ],
        }
        
        result = get_editable_step(config, "test_step")
        
        assert "step" in result
        assert "source_tracking" in result
        assert result["step"]["id"] == "test_step"
    
    def test_raises_on_missing_step(self):
        """Verify ValueError when step not found."""
        config = {"id": "test", "steps": []}
        
        with pytest.raises(ValueError) as exc_info:
            get_editable_step(config, "nonexistent")
        
        assert "nonexistent" in str(exc_info.value)
        assert "not found" in str(exc_info.value).lower()
    
    def test_enhances_fields_with_metadata(self):
        """Verify fields get enhanced with editability metadata."""
        config = {
            "id": "test",
            "steps": [
                {
                    "id": "test_step",
                    "title": "Test",
                    "fields": [
                        {
                            "id": "field1",
                            "type": "text",
                            "label": "Field",
                            "editability": "free",
                            "override_source": "schema",
                        }
                    ],
                }
            ],
        }
        
        result = get_editable_step(config, "test_step")
        field = result["step"]["fields"][0]
        
        assert "is_locked" in field
        assert "is_default" in field
        assert "override_source" in field
    
    def test_extracts_source_tracking(self):
        """Verify source_tracking is extracted."""
        config = {
            "id": "test",
            "steps": [
                {
                    "id": "test_step",
                    "title": "Test",
                    "fields": [
                        {
                            "id": "field1",
                            "type": "text",
                            "label": "Field",
                            "editability": "free",
                            "override_source": "schema",
                        },
                        {
                            "id": "field2",
                            "type": "text",
                            "label": "Field 2",
                            "editability": "locked",
                            "override_source": "tool:claude",
                        },
                    ],
                }
            ],
        }
        
        result = get_editable_step(config, "test_step")
        tracking = result["source_tracking"]
        
        assert tracking["total_fields"] == 2
        assert "schema" in tracking["by_source"]
        assert "tool:claude" in tracking["by_source"]
        assert tracking["locked_fields"] == 1


class TestEnhanceFieldWithMetadata:
    def test_adds_is_locked_true_for_locked_editability(self):
        """Verify is_locked=True when editability is 'locked'."""
        field = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "editability": "locked",
            "override_source": "schema",
        }
        
        enhanced = _enhance_field_with_metadata(field)
        assert enhanced["is_locked"] is True
    
    def test_adds_is_locked_false_for_free_editability(self):
        """Verify is_locked=False when editability is 'free'."""
        field = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "editability": "free",
            "override_source": "schema",
        }
        
        enhanced = _enhance_field_with_metadata(field)
        assert enhanced["is_locked"] is False
    
    def test_adds_is_locked_true_for_locked_value(self):
        """Verify locked_value alone does NOT set is_locked (editability is authoritative)."""
        field = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "locked_value": "readonly_content",
            "editability": "free",
            "override_source": "schema",
        }
        
        enhanced = _enhance_field_with_metadata(field)
        assert enhanced["is_locked"] is False
    
    def test_adds_is_default_true_for_schema_source(self):
        """Verify is_default=True when override_source is 'schema'."""
        field = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "editability": "free",
            "override_source": "schema",
        }
        
        enhanced = _enhance_field_with_metadata(field)
        assert enhanced["is_default"] is True
    
    def test_adds_is_default_false_for_overridden_source(self):
        """Verify is_default=False when override_source is not 'schema'."""
        field = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "editability": "free",
            "override_source": "tool:claude",
        }
        
        enhanced = _enhance_field_with_metadata(field)
        assert enhanced["is_default"] is False
    
    def test_preserves_override_source(self):
        """Verify override_source is preserved on enhanced field."""
        field = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "editability": "free",
            "override_source": "language:python",
        }
        
        enhanced = _enhance_field_with_metadata(field)
        assert enhanced["override_source"] == "language:python"
    
    def test_preserves_existing_field_data(self):
        """Verify original field data is preserved."""
        field = {
            "id": "field1",
            "type": "textarea",
            "label": "My Field",
            "description": "A field",
            "default": "some_value",
            "required": True,
            "editability": "free",
            "override_source": "schema",
        }
        
        enhanced = _enhance_field_with_metadata(field)
        
        assert enhanced["id"] == field["id"]
        assert enhanced["type"] == field["type"]
        assert enhanced["label"] == field["label"]
        assert enhanced["description"] == field["description"]
        assert enhanced["default"] == field["default"]
        assert enhanced["required"] == field["required"]


class TestExtractSourceTracking:
    def test_counts_total_fields(self):
        """Verify total_fields count."""
        step = {
            "id": "test",
            "fields": [
                {
                    "id": "f1",
                    "override_source": "schema",
                    "is_locked": False,
                    "is_default": True,
                    "editability": "free",
                },
                {
                    "id": "f2",
                    "override_source": "tool:claude",
                    "is_locked": False,
                    "is_default": False,
                    "editability": "free",
                },
            ],
        }
        
        tracking = _extract_source_tracking(step)
        assert tracking["total_fields"] == 2
    
    def test_counts_by_source(self):
        """Verify by_source counts."""
        step = {
            "id": "test",
            "fields": [
                {"id": "f1", "override_source": "schema", "is_locked": False, "is_default": True, "editability": "free"},
                {"id": "f2", "override_source": "schema", "is_locked": False, "is_default": True, "editability": "free"},
                {"id": "f3", "override_source": "tool:claude", "is_locked": False, "is_default": False, "editability": "free"},
            ],
        }
        
        tracking = _extract_source_tracking(step)
        assert tracking["by_source"]["schema"] == 2
        assert tracking["by_source"]["tool:claude"] == 1
    
    def test_counts_by_editability(self):
        """Verify by_editability counts."""
        step = {
            "id": "test",
            "fields": [
                {"id": "f1", "override_source": "schema", "is_locked": False, "is_default": True, "editability": "free"},
                {"id": "f2", "override_source": "schema", "is_locked": True, "is_default": True, "editability": "locked"},
                {"id": "f3", "override_source": "tool:claude", "is_locked": False, "is_default": False, "editability": "suggested"},
            ],
        }
        
        tracking = _extract_source_tracking(step)
        assert tracking["by_editability"]["free"] == 1
        assert tracking["by_editability"]["locked"] == 1
        assert tracking["by_editability"]["suggested"] == 1
    
    def test_counts_locked_fields(self):
        """Verify locked_fields count."""
        step = {
            "id": "test",
            "fields": [
                {"id": "f1", "source_file": "schema.json", "is_locked": False, "is_default": True, "editability": "free"},
                {"id": "f2", "source_file": "schema.json", "is_locked": True, "is_default": True, "editability": "locked"},
                {"id": "f3", "source_file": "tools/claude.json", "is_locked": True, "is_default": False, "editability": "free"},
            ],
        }
        
        tracking = _extract_source_tracking(step)
        assert tracking["locked_fields"] == 2
    
    def test_counts_default_fields(self):
        """Verify default_fields count."""
        step = {
            "id": "test",
            "fields": [
                {"id": "f1", "source_file": "schema.json", "is_locked": False, "is_default": True, "editability": "free"},
                {"id": "f2", "source_file": "schema.json", "is_locked": True, "is_default": True, "editability": "locked"},
                {"id": "f3", "source_file": "tools/claude.json", "is_locked": False, "is_default": False, "editability": "free"},
            ],
        }
        
        tracking = _extract_source_tracking(step)
        assert tracking["default_fields"] == 2
    
    def test_counts_overridden_fields(self):
        """Verify overridden_fields count."""
        step = {
            "id": "test",
            "fields": [
                {"id": "f1", "source_file": "schema.json", "is_locked": False, "is_default": True, "editability": "free"},
                {"id": "f2", "source_file": "schema.json", "is_locked": True, "is_default": True, "editability": "locked"},
                {"id": "f3", "source_file": "tools/claude.json", "is_locked": False, "is_default": False, "editability": "free"},
                {"id": "f4", "source_file": "languages/python.json", "is_locked": False, "is_default": False, "editability": "free"},
            ],
        }
        
        tracking = _extract_source_tracking(step)
        assert tracking["overridden_fields"] == 2
    
    def test_empty_step_returns_zero_counts(self):
        """Verify empty step handling."""
        step = {"id": "test", "fields": []}
        
        tracking = _extract_source_tracking(step)
        assert tracking["total_fields"] == 0
        assert len(tracking["by_source"]) == 0
        assert tracking["locked_fields"] == 0
        assert tracking["default_fields"] == 0
        assert tracking["overridden_fields"] == 0
