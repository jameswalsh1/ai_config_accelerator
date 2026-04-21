"""
Tests for JSON Patch Engine (config_patcher.py)

Tests ID-based updates with:
- Only modifying relevant files
- Preserving existing content
- Safe concurrent access
- Minimal rewrites
"""

import json
import tempfile
import pytest
from pathlib import Path
from copy import deepcopy

from app.services.config_patcher import (
    update_field_metadata,
    update_field_structure,
    update_step_visibility,
    apply_patch,
    remove_field_override,
    PatchError,
    ConfigNotFoundError,
    _get_target_file,
    _get_field_override_index,
    _get_step_override_index,
)


class TestPatchEngine:
    """Test suite for JSON Patch Engine."""

    def test_get_target_file_tool_scope(self):
        """Test file path resolution for tool scope."""
        path = _get_target_file("tool", "claude")
        assert path.name == "claude.json"
        assert "tools" in str(path)

    def test_get_target_file_language_scope(self):
        """Test file path resolution for language scope."""
        path = _get_target_file("language", "python")
        assert path.name == "python.json"
        assert "languages" in str(path)

    def test_get_target_file_override_scope(self):
        """Test file path resolution for override scope."""
        path = _get_target_file("override", "claude+python")
        assert path.name == "claude+python.json"
        assert "overrides" in str(path)

    def test_get_target_file_invalid_scope(self):
        """Test that invalid scope raises error."""
        with pytest.raises(PatchError):
            _get_target_file("invalid", "python")

    def test_get_field_override_index_found(self):
        """Test finding field override by ID."""
        overrides = [
            {"field_id": "step1.field1"},
            {"field_id": "step1.field2"},
            {"field_id": "step2.field1"},
        ]
        idx = _get_field_override_index(overrides, "step1.field2")
        assert idx == 1

    def test_get_field_override_index_not_found(self):
        """Test when field override not found."""
        overrides = [{"field_id": "step1.field1"}]
        idx = _get_field_override_index(overrides, "step2.field1")
        assert idx is None

    def test_get_step_override_index_found(self):
        """Test finding step override by ID."""
        overrides = [
            {"step_id": "step1"},
            {"step_id": "step2"},
            {"step_id": "step3"},
        ]
        idx = _get_step_override_index(overrides, "step2")
        assert idx == 1

    def test_get_step_override_index_not_found(self):
        """Test when step override not found."""
        overrides = [{"step_id": "step1"}]
        idx = _get_step_override_index(overrides, "step2")
        assert idx is None

    def test_update_field_metadata_new_override(self):
        """Test creating a new metadata override."""
        # Use actual language file
        result = update_field_metadata(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            changes={"default": "pytest+poetry"},
        )

        # Verify the override was added
        assert "metadata_overrides" in result
        found = any(
            o.get("field_id") == "claude_md.tech_stack"
            for o in result["metadata_overrides"]
        )
        assert found

        # Verify the override has the change
        override = next(
            o
            for o in result["metadata_overrides"]
            if o.get("field_id") == "claude_md.tech_stack"
        )
        assert override.get("default") == "pytest+poetry"

    def test_update_field_metadata_existing_override(self):
        """Test updating an existing metadata override."""
        # First, create an override
        update_field_metadata(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            changes={"default": "pytest"},
        )

        # Update it
        result = update_field_metadata(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            changes={"default": "ruff", "editability": "locked"},
        )

        # Verify exactly one override exists
        overrides = [
            o
            for o in result.get("metadata_overrides", [])
            if o.get("field_id") == "claude_md.tech_stack"
        ]
        assert len(overrides) == 1

        # Verify both changes were applied
        override = overrides[0]
        assert override.get("default") == "ruff"
        assert override.get("editability") == "locked"

    def test_update_field_metadata_invalid_key(self):
        """Test that invalid metadata keys raise error."""
        with pytest.raises(PatchError):
            update_field_metadata(
                scope="language",
                target="python",
                step_id="step1",
                field_id="field1",
                changes={"invalid_key": "value"},
            )

    def test_update_field_structure_new_override(self):
        """Test creating a new structure override."""
        result = update_field_structure(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            changes={"merge_mode": "replace"},
        )

        # Verify the override was added
        assert "field_overrides" in result
        found = any(
            o.get("field_id") == "claude_md.tech_stack"
            for o in result["field_overrides"]
        )
        assert found

    def test_update_field_structure_with_presets(self):
        """Test adding presets via structure update."""
        result = update_field_structure(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            changes={
                "merge_presets": [{"label": "Django", "value": "django"}],
                "merge_mode": "append",
            },
        )

        override = next(
            o
            for o in result["field_overrides"]
            if o.get("field_id") == "claude_md.tech_stack"
        )
        assert override.get("merge_mode") == "append"
        assert len(override.get("merge_presets", [])) > 0

    def test_update_field_structure_invalid_key(self):
        """Test that invalid structure keys raise error."""
        with pytest.raises(PatchError):
            update_field_structure(
                scope="language",
                target="python",
                step_id="step1",
                field_id="field1",
                changes={"invalid_key": "value"},
            )

    def test_update_step_visibility_new_override(self):
        """Test creating a new step override."""
        result = update_step_visibility(
            scope="tool",
            target="claude",
            step_id="hooks",
            changes={"hidden": True},
        )

        # Verify the override was added
        assert "step_overrides" in result
        found = any(
            o.get("step_id") == "hooks" for o in result["step_overrides"]
        )
        assert found

    def test_update_step_visibility_with_title(self):
        """Test updating step title override."""
        result = update_step_visibility(
            scope="language",
            target="python",
            step_id="language_selection",
            changes={"title_override": "Python Settings"},
        )

        override = next(
            o for o in result["step_overrides"] if o.get("step_id") == "language_selection"
        )
        assert override.get("title_override") == "Python Settings"

    def test_update_step_visibility_invalid_key(self):
        """Test that invalid step keys raise error."""
        with pytest.raises(PatchError):
            update_step_visibility(
                scope="tool",
                target="claude",
                step_id="step1",
                changes={"invalid_key": "value"},
            )

    def test_apply_patch_metadata_update(self):
        """Test apply_patch with metadata update."""
        patch = {
            "scope": "language",
            "target": "python",
            "step_id": "claude_md",
            "field_id": "tech_stack",
            "changes": {"default": "pytest+poetry"},
        }

        result = apply_patch(patch)
        assert "metadata_overrides" in result

    def test_apply_patch_structure_update(self):
        """Test apply_patch with structure update."""
        patch = {
            "scope": "language",
            "target": "python",
            "step_id": "claude_md",
            "field_id": "tech_stack",
            "changes": {"merge_mode": "replace"},
        }

        result = apply_patch(patch)
        assert "field_overrides" in result

    def test_apply_patch_step_update(self):
        """Test apply_patch with step update."""
        patch = {
            "scope": "tool",
            "target": "claude",
            "step_id": "hooks",
            "changes": {"hidden": True},
        }

        result = apply_patch(patch)
        assert "step_overrides" in result

    def test_apply_patch_explicit_update_type(self):
        """Test apply_patch with explicit update_type."""
        patch = {
            "scope": "language",
            "target": "python",
            "step_id": "claude_md",
            "field_id": "tech_stack",
            "update_type": "metadata",
            "changes": {"default": "pytest"},
        }

        result = apply_patch(patch)
        assert "metadata_overrides" in result

    def test_apply_patch_missing_scope(self):
        """Test that missing scope raises error."""
        patch = {
            "target": "python",
            "step_id": "step1",
            "changes": {"default": "value"},
        }

        with pytest.raises(PatchError):
            apply_patch(patch)

    def test_apply_patch_missing_target(self):
        """Test that missing target raises error."""
        patch = {
            "scope": "language",
            "step_id": "step1",
            "changes": {"default": "value"},
        }

        with pytest.raises(PatchError):
            apply_patch(patch)

    def test_apply_patch_missing_changes(self):
        """Test that missing changes raises error."""
        patch = {
            "scope": "language",
            "target": "python",
            "step_id": "step1",
        }

        with pytest.raises(PatchError):
            apply_patch(patch)

    def test_apply_patch_invalid_scope(self):
        """Test that invalid scope raises error."""
        patch = {
            "scope": "invalid",
            "target": "python",
            "step_id": "step1",
            "changes": {"default": "value"},
        }

        with pytest.raises(PatchError):
            apply_patch(patch)

    def test_remove_field_metadata_override(self):
        """Test removing a metadata override."""
        # First create one
        update_field_metadata(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            changes={"default": "pytest"},
        )

        # Remove it
        result = remove_field_override(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            override_type="metadata",
        )

        # Verify it's gone
        found = any(
            o.get("field_id") == "claude_md.tech_stack"
            for o in result.get("metadata_overrides", [])
        )
        assert not found

    def test_remove_field_structure_override(self):
        """Test removing a structure override."""
        # First create one
        update_field_structure(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            changes={"merge_mode": "replace"},
        )

        # Remove it
        result = remove_field_override(
            scope="language",
            target="python",
            step_id="claude_md",
            field_id="tech_stack",
            override_type="structure",
        )

        # Verify it's gone
        found = any(
            o.get("field_id") == "claude_md.tech_stack"
            for o in result.get("field_overrides", [])
        )
        assert not found

    def test_config_not_found_raises_error(self):
        """Test that non-existent config raises ConfigNotFoundError."""
        with pytest.raises(ConfigNotFoundError):
            update_field_metadata(
                scope="language",
                target="nonexistent_language_xyz",
                step_id="step1",
                field_id="field1",
                changes={"default": "value"},
            )

    def test_only_modifies_target_file(self):
        """Test that patch only modifies the target file, not others."""
        # Get initial state of other files
        claude_tool_path = _get_target_file("tool", "claude")
        copilot_tool_path = _get_target_file("tool", "copilot")

        with claude_tool_path.open() as f:
            claude_initial = json.load(f)
        with copilot_tool_path.open() as f:
            copilot_initial = json.load(f)

        # Apply patch to python language
        apply_patch(
            {
                "scope": "language",
                "target": "python",
                "step_id": "claude_md",
                "field_id": "tech_stack",
                "changes": {"default": "test_value_xyz"},
            }
        )

        # Verify other files unchanged
        with claude_tool_path.open() as f:
            claude_after = json.load(f)
        with copilot_tool_path.open() as f:
            copilot_after = json.load(f)

        assert claude_initial == claude_after
        assert copilot_initial == copilot_after

    def test_preserves_existing_overrides(self):
        """Test that patching preserves existing overrides."""
        # Add first override
        result1 = update_field_metadata(
            scope="language",
            target="python",
            step_id="step1",
            field_id="field1",
            changes={"default": "value1"},
        )

        # Add second override
        result2 = update_field_metadata(
            scope="language",
            target="python",
            step_id="step2",
            field_id="field2",
            changes={"default": "value2"},
        )

        # Verify both exist
        metadata = result2.get("metadata_overrides", [])
        step1_override = any(
            o.get("field_id") == "step1.field1" for o in metadata
        )
        step2_override = any(
            o.get("field_id") == "step2.field2" for o in metadata
        )

        assert step1_override
        assert step2_override


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
