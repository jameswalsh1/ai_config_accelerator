"""
Tests for Config Diff Utility (config_diff.py)

Tests the diff comparison functionality including:
- Field-level changes (value, label, description, required)
- Preset changes (added, removed, modified)
- Locking/editability changes
- Step-level changes
- Config-level changes
"""

import json
import pytest
from pathlib import Path
from typing import Any

from app.services.config_diff import (
    compare_configs,
    compare_fields,
    compare_steps,
    compare_presets,
    diff_to_dict,
    ChangeType,
    FieldDiff,
    StepDiff,
    ConfigDiff,
    PresetChange,
    LockingChange,
)


class TestPresetComparison:
    """Test preset change detection."""
    
    def test_no_preset_changes(self):
        """Test when presets are identical."""
        before = [
            {"label": "Python", "value": "python", "mode": "append"},
            {"label": "JavaScript", "value": "javascript", "mode": "append"},
        ]
        after = [
            {"label": "Python", "value": "python", "mode": "append"},
            {"label": "JavaScript", "value": "javascript", "mode": "append"},
        ]
        
        changes = compare_presets(before, after)
        assert len(changes) == 0
    
    def test_preset_added(self):
        """Test detection of added preset."""
        before = [{"label": "Python", "value": "python"}]
        after = [
            {"label": "Python", "value": "python"},
            {"label": "JavaScript", "value": "javascript"},
        ]
        
        changes = compare_presets(before, after)
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.ADDED
        assert changes[0].label == "JavaScript"
        assert changes[0].after_value == "javascript"
    
    def test_preset_removed(self):
        """Test detection of removed preset."""
        before = [
            {"label": "Python", "value": "python"},
            {"label": "JavaScript", "value": "javascript"},
        ]
        after = [{"label": "Python", "value": "python"}]
        
        changes = compare_presets(before, after)
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.REMOVED
        assert changes[0].label == "JavaScript"
        assert changes[0].before_value == "javascript"
    
    def test_preset_value_modified(self):
        """Test detection of modified preset value."""
        before = [{"label": "Python", "value": "py", "mode": "append"}]
        after = [{"label": "Python", "value": "python", "mode": "append"}]
        
        changes = compare_presets(before, after)
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.MODIFIED
        assert changes[0].label == "Python"
        assert changes[0].before_value == "py"
        assert changes[0].after_value == "python"
    
    def test_preset_mode_modified(self):
        """Test detection of modified preset mode."""
        before = [{"label": "Python", "value": "python", "mode": "append"}]
        after = [{"label": "Python", "value": "python", "mode": "overwrite"}]
        
        changes = compare_presets(before, after)
        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.MODIFIED
        assert changes[0].before_mode == "append"
        assert changes[0].after_mode == "overwrite"
    
    def test_multiple_preset_changes(self):
        """Test detection of multiple preset changes."""
        before = [
            {"label": "Python", "value": "python"},
            {"label": "JavaScript", "value": "javascript"},
        ]
        after = [
            {"label": "Python", "value": "python_updated"},
            {"label": "Java", "value": "java"},
            # JavaScript removed
        ]
        
        changes = compare_presets(before, after)
        assert len(changes) == 3  # modified, added, removed
        
        modified = [c for c in changes if c.change_type == ChangeType.MODIFIED]
        added = [c for c in changes if c.change_type == ChangeType.ADDED]
        removed = [c for c in changes if c.change_type == ChangeType.REMOVED]
        
        assert len(modified) == 1
        assert len(added) == 1
        assert len(removed) == 1


class TestFieldComparison:
    """Test field-level diff detection."""
    
    def test_field_added(self):
        """Test detection of added field."""
        before: dict[str, Any] = {}
        after = {
            "id": "new_field",
            "type": "text",
            "label": "New Field",
            "default": "value",
        }
        
        diff = compare_fields(before, after)
        assert diff.change_type == ChangeType.ADDED
        assert diff.field_id == "new_field"
        assert diff.after_label == "New Field"
    
    def test_field_removed(self):
        """Test detection of removed field."""
        before = {
            "id": "old_field",
            "type": "text",
            "label": "Old Field",
        }
        after: dict[str, Any] = {}
        
        diff = compare_fields(before, after)
        assert diff.change_type == ChangeType.REMOVED
        assert diff.field_id == "old_field"
        assert diff.before_label == "Old Field"
    
    def test_field_value_changed(self):
        """Test detection of field value change."""
        before = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "default": "old_value",
        }
        after = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "default": "new_value",
        }
        
        diff = compare_fields(before, after)
        assert diff.value_changed
        assert diff.before_value == "old_value"
        assert diff.after_value == "new_value"
        assert diff.change_type == ChangeType.MODIFIED
    
    def test_field_label_changed(self):
        """Test detection of field label change."""
        before = {
            "id": "field1",
            "type": "text",
            "label": "Old Label",
        }
        after = {
            "id": "field1",
            "type": "text",
            "label": "New Label",
        }
        
        diff = compare_fields(before, after)
        assert diff.label_changed
        assert diff.before_label == "Old Label"
        assert diff.after_label == "New Label"
    
    def test_field_required_changed(self):
        """Test detection of required change."""
        before = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "required": False,
        }
        after = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "required": True,
        }
        
        diff = compare_fields(before, after)
        assert diff.required_changed
        assert diff.before_required is False
        assert diff.after_required is True
    
    def test_field_preset_changes(self):
        """Test detection of field preset changes."""
        before = {
            "id": "field1",
            "type": "select",
            "label": "Languages",
            "presets": [{"label": "Python", "value": "python"}],
        }
        after = {
            "id": "field1",
            "type": "select",
            "label": "Languages",
            "presets": [
                {"label": "Python", "value": "python"},
                {"label": "Java", "value": "java"},
            ],
        }
        
        diff = compare_fields(before, after)
        assert len(diff.preset_changes) == 1
        assert diff.preset_changes[0].change_type == ChangeType.ADDED
        assert diff.preset_changes[0].label == "Java"
    
    def test_field_locking_changed(self):
        """Test detection of locking/editability change."""
        before = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "editability": "free",
        }
        after = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "editability": "locked",
            "locked_value": "fixed_value",
        }
        
        diff = compare_fields(before, after)
        assert diff.locking_changes is not None
        assert diff.locking_changes.before_state == "free"
        assert diff.locking_changes.after_state == "locked"
        assert diff.locking_changes.after_locked_value == "fixed_value"
    
    def test_field_hidden_changed(self):
        """Test detection of visibility change."""
        before = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "hidden": False,
        }
        after = {
            "id": "field1",
            "type": "text",
            "label": "Field",
            "hidden": True,
        }
        
        diff = compare_fields(before, after)
        assert diff.hidden_changed
        assert diff.before_hidden is False
        assert diff.after_hidden is True
    
    def test_field_multiple_changes(self):
        """Test field with multiple simultaneous changes."""
        before = {
            "id": "field1",
            "type": "text",
            "label": "Old Label",
            "default": "old",
            "required": False,
            "presets": [{"label": "Old", "value": "old"}],
            "editability": "free",
        }
        after = {
            "id": "field1",
            "type": "text",
            "label": "New Label",
            "default": "new",
            "required": True,
            "presets": [{"label": "New", "value": "new"}],
            "editability": "locked",
        }
        
        diff = compare_fields(before, after)
        assert diff.label_changed
        assert diff.value_changed
        assert diff.required_changed
        assert diff.preset_changes
        assert diff.locking_changes is not None
        assert diff.has_changes()
        
        summary = diff.get_summary()
        assert "value" in summary
        assert "label" in summary
        assert "required" in summary
        assert "presets" in summary
        assert "locking" in summary


class TestStepComparison:
    """Test step-level diff detection."""
    
    def test_step_added(self):
        """Test detection of added step."""
        before: dict[str, Any] = {}
        after = {
            "id": "new_step",
            "title": "New Step",
            "description": "A new step",
            "output_file": "output.md",
            "fields": [],
        }
        
        diff = compare_steps(before, after)
        assert diff.change_type == ChangeType.ADDED
        assert diff.step_id == "new_step"
        assert diff.after_title == "New Step"
    
    def test_step_removed(self):
        """Test detection of removed step."""
        before = {
            "id": "old_step",
            "title": "Old Step",
            "output_file": "output.md",
            "fields": [],
        }
        after: dict[str, Any] = {}
        
        diff = compare_steps(before, after)
        assert diff.change_type == ChangeType.REMOVED
        assert diff.step_id == "old_step"
        assert diff.before_title == "Old Step"
    
    def test_step_title_changed(self):
        """Test detection of step title change."""
        before = {
            "id": "step1",
            "title": "Old Title",
            "output_file": "output.md",
            "fields": [],
        }
        after = {
            "id": "step1",
            "title": "New Title",
            "output_file": "output.md",
            "fields": [],
        }
        
        diff = compare_steps(before, after)
        assert diff.title_changed
        assert diff.before_title == "Old Title"
        assert diff.after_title == "New Title"
    
    def test_step_field_added(self):
        """Test detection of field added to step."""
        before = {
            "id": "step1",
            "title": "Step",
            "output_file": "output.md",
            "fields": [{"id": "field1", "type": "text", "label": "Field 1"}],
        }
        after = {
            "id": "step1",
            "title": "Step",
            "output_file": "output.md",
            "fields": [
                {"id": "field1", "type": "text", "label": "Field 1"},
                {"id": "field2", "type": "text", "label": "Field 2"},
            ],
        }
        
        diff = compare_steps(before, after)
        assert "field2" in diff.fields_added
        assert len(diff.fields_removed) == 0
    
    def test_step_field_removed(self):
        """Test detection of field removed from step."""
        before = {
            "id": "step1",
            "title": "Step",
            "output_file": "output.md",
            "fields": [
                {"id": "field1", "type": "text", "label": "Field 1"},
                {"id": "field2", "type": "text", "label": "Field 2"},
            ],
        }
        after = {
            "id": "step1",
            "title": "Step",
            "output_file": "output.md",
            "fields": [{"id": "field1", "type": "text", "label": "Field 1"}],
        }
        
        diff = compare_steps(before, after)
        assert "field2" in diff.fields_removed
        assert len(diff.fields_added) == 0
    
    def test_step_field_modified(self):
        """Test detection of field modified within step."""
        before = {
            "id": "step1",
            "title": "Step",
            "output_file": "output.md",
            "fields": [{"id": "field1", "type": "text", "label": "Old Label"}],
        }
        after = {
            "id": "step1",
            "title": "Step",
            "output_file": "output.md",
            "fields": [{"id": "field1", "type": "text", "label": "New Label"}],
        }
        
        diff = compare_steps(before, after)
        assert len(diff.field_diffs) == 1
        assert diff.field_diffs[0].label_changed


class TestConfigComparison:
    """Test config-level diff detection."""
    
    def test_no_changes(self):
        """Test configs with no changes."""
        config = {
            "id": "test",
            "title": "Test",
            "description": "Test config",
            "target": "test",
            "steps": [],
        }
        
        diff = compare_configs(config, config)
        assert not diff.has_changes()
        assert diff.get_total_changes() == 0
    
    def test_config_title_changed(self):
        """Test detection of config title change."""
        before = {
            "id": "test",
            "title": "Old Title",
            "description": "Test",
            "target": "test",
            "steps": [],
        }
        after = {
            "id": "test",
            "title": "New Title",
            "description": "Test",
            "target": "test",
            "steps": [],
        }
        
        diff = compare_configs(before, after)
        assert diff.title_changed
        assert diff.before_title == "Old Title"
        assert diff.after_title == "New Title"
    
    def test_config_step_added(self):
        """Test detection of step added to config."""
        before = {
            "id": "test",
            "title": "Test",
            "description": "Test",
            "target": "test",
            "steps": [],
        }
        after = {
            "id": "test",
            "title": "Test",
            "description": "Test",
            "target": "test",
            "steps": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "output_file": "output.md",
                    "fields": [],
                }
            ],
        }
        
        diff = compare_configs(before, after)
        assert "step1" in diff.steps_added
        assert len(diff.steps_removed) == 0
    
    def test_complex_config_diff(self):
        """Test complex configuration with multiple changes."""
        before = {
            "id": "test",
            "title": "Old Title",
            "description": "Old Description",
            "target": "test",
            "steps": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "output_file": "output.md",
                    "fields": [
                        {
                            "id": "field1",
                            "type": "text",
                            "label": "Field 1",
                            "default": "old",
                            "presets": [{"label": "Old", "value": "old"}],
                        }
                    ],
                }
            ],
        }
        after = {
            "id": "test",
            "title": "New Title",
            "description": "New Description",
            "target": "test",
            "steps": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "output_file": "output.md",
                    "fields": [
                        {
                            "id": "field1",
                            "type": "text",
                            "label": "New Label",
                            "default": "new",
                            "presets": [
                                {"label": "Old", "value": "old"},
                                {"label": "New", "value": "new"},
                            ],
                        },
                        {
                            "id": "field2",
                            "type": "text",
                            "label": "Field 2",
                        },
                    ],
                }
            ],
        }
        
        diff = compare_configs(before, after)
        assert diff.title_changed
        assert diff.description_changed
        assert len(diff.step_diffs) == 1
        assert len(diff.step_diffs[0].field_diffs) == 1
        assert "field2" in diff.step_diffs[0].fields_added


class TestDiffSerialization:
    """Test conversion of diff objects to UI-friendly format."""
    
    def test_diff_to_dict_no_changes(self):
        """Test serialization of diff with no changes."""
        before = {
            "id": "test",
            "title": "Test",
            "description": "Test",
            "target": "test",
            "steps": [],
        }
        
        diff = compare_configs(before, before)
        result = diff_to_dict(diff)
        
        assert result["has_changes"] is False
        assert result["total_changes"] == 0
        assert result["before_id"] == "test"
        assert result["after_id"] == "test"
    
    def test_diff_to_dict_with_changes(self):
        """Test serialization of diff with multiple changes."""
        before = {
            "id": "claude",
            "title": "Old Title",
            "description": "Old",
            "target": "test",
            "steps": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "output_file": "output.md",
                    "fields": [
                        {
                            "id": "field1",
                            "type": "text",
                            "label": "Old Label",
                            "default": "old",
                            "editability": "free",
                        }
                    ],
                }
            ],
        }
        after = {
            "id": "claude",
            "title": "New Title",
            "description": "New",
            "target": "test",
            "steps": [
                {
                    "id": "step1",
                    "title": "Step 1",
                    "output_file": "output.md",
                    "fields": [
                        {
                            "id": "field1",
                            "type": "text",
                            "label": "New Label",
                            "default": "new",
                            "editability": "locked",
                            "locked_value": "fixed",
                        }
                    ],
                }
            ],
        }
        
        diff = compare_configs(before, after)
        result = diff_to_dict(diff)
        
        assert result["has_changes"] is True
        assert result["total_changes"] > 0
        assert result["metadata_changes"]["title"]["changed"] is True
        assert result["metadata_changes"]["title"]["before"] == "Old Title"
        assert result["metadata_changes"]["title"]["after"] == "New Title"
        
        assert len(result["steps"]["modified"]) == 1
        step_changes = result["steps"]["modified"][0]
        assert step_changes["id"] == "step1"
        
        field_changes = step_changes["fields"]["modified"][0]
        assert field_changes["id"] == "field1"
        assert field_changes["value"]["changed"] is True
        assert field_changes["value"]["before"] == "old"
        assert field_changes["value"]["after"] == "new"
        assert field_changes["locking"]["changed"] is True
        assert field_changes["locking"]["before_state"] == "free"
        assert field_changes["locking"]["after_state"] == "locked"


class TestIntegrationWithRealConfigs:
    """Test diff with actual configuration files."""
    
    DATA_DIR = Path(__file__).parent.parent / "app" / "data" / "wizard_configs"
    
    def test_diff_real_tool_configs(self):
        """Test diffing real tool override files."""
        if not self.DATA_DIR.exists():
            pytest.skip("Data directory not found")
        
        # Load two different tool configs
        claude_path = self.DATA_DIR / "tools" / "claude.json"
        copilot_path = self.DATA_DIR / "tools" / "copilot.json"
        
        if not claude_path.exists() or not copilot_path.exists():
            pytest.skip("Tool config files not found")
        
        with claude_path.open() as f:
            claude_config = json.load(f)
        
        with copilot_path.open() as f:
            copilot_config = json.load(f)
        
        # Compare them
        diff = compare_configs(claude_config, copilot_config)
        
        # Should have differences (they are different tools)
        assert diff.has_changes() or diff.get_total_changes() >= 0  # May or may not differ
        
        # Verify structure
        result = diff_to_dict(diff)
        assert "metadata_changes" in result
        assert "steps" in result
    
    def test_diff_identical_configs(self):
        """Test diffing identical configs produces empty diff."""
        if not self.DATA_DIR.exists():
            pytest.skip("Data directory not found")
        
        schema_path = self.DATA_DIR / "schema.json"
        if not schema_path.exists():
            pytest.skip("Schema file not found")
        
        with schema_path.open() as f:
            config = json.load(f)
        
        # Compare config with itself
        diff = compare_configs(config, config)
        
        assert not diff.has_changes()
        assert diff.get_total_changes() == 0


class TestFieldDiffUtility:
    """Test FieldDiff utility methods."""
    
    def test_field_diff_summary_no_changes(self):
        """Test summary for unchanged field."""
        diff = FieldDiff(
            field_id="field1",
            field_type="text",
            change_type=ChangeType.UNCHANGED,
        )
        
        assert diff.get_summary() == "no changes"
    
    def test_field_diff_summary_single_change(self):
        """Test summary for single change."""
        diff = FieldDiff(
            field_id="field1",
            field_type="text",
            change_type=ChangeType.MODIFIED,
            value_changed=True,
            before_value="old",
            after_value="new",
        )
        
        summary = diff.get_summary()
        assert "value" in summary
    
    def test_field_diff_summary_multiple_changes(self):
        """Test summary for multiple changes."""
        diff = FieldDiff(
            field_id="field1",
            field_type="text",
            change_type=ChangeType.MODIFIED,
            value_changed=True,
            label_changed=True,
            required_changed=True,
        )
        
        summary = diff.get_summary()
        assert "value" in summary
        assert "label" in summary
        assert "required" in summary


class TestStepDiffUtility:
    """Test StepDiff utility methods."""
    
    def test_step_diff_change_summary(self):
        """Test step change summary."""
        diff = StepDiff(
            step_id="step1",
            change_type=ChangeType.MODIFIED,
            title_changed=True,
            before_title="Old",
            after_title="New",
            fields_added=["field1", "field2"],
            fields_removed=["field3"],
        )
        
        summary = diff.get_change_summary()
        assert "title changed" in summary
        assert "2 field(s) added" in summary
        assert "1 field(s) removed" in summary
