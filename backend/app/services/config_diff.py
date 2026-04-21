"""
Config Diff Utility - Compare JSON configuration file versions.

Provides readable, UI-friendly diffs showing changes between configuration versions
with support for:
- Field changes (value modifications)
- Preset changes (additions, removals, modifications)
- Locking changes (editability state changes)
- Step and field granularity
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional


class ChangeType(Enum):
    """Type of change detected."""
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"


class PropertyType(Enum):
    """Type of property that changed."""
    FIELD_VALUE = "field_value"
    PRESET = "preset"
    LOCKING = "locking"
    METADATA = "metadata"


@dataclass
class PresetChange:
    """Represents a change to a preset."""
    change_type: ChangeType
    label: str
    before_value: Optional[Any] = None
    after_value: Optional[Any] = None
    before_mode: Optional[str] = None
    after_mode: Optional[str] = None
    description: Optional[str] = None


@dataclass
class LockingChange:
    """Represents a change to locking/editability."""
    change_type: ChangeType
    before_state: Optional[str] = None
    after_state: Optional[str] = None
    before_locked_value: Optional[str] = None
    after_locked_value: Optional[str] = None


@dataclass
class FieldDiff:
    """Represents all changes to a single field."""
    field_id: str
    field_type: str
    change_type: ChangeType
    
    # Basic field changes
    value_changed: bool = False
    before_value: Optional[Any] = None
    after_value: Optional[Any] = None
    
    # Metadata changes
    label_changed: bool = False
    before_label: Optional[str] = None
    after_label: Optional[str] = None
    
    description_changed: bool = False
    before_description: Optional[str] = None
    after_description: Optional[str] = None
    
    required_changed: bool = False
    before_required: Optional[bool] = None
    after_required: Optional[bool] = None
    
    # Preset changes
    preset_changes: list[PresetChange] = field(default_factory=list)
    
    # Locking/editability changes
    locking_changes: Optional[LockingChange] = None
    
    # Visibility changes
    hidden_changed: bool = False
    before_hidden: Optional[bool] = None
    after_hidden: Optional[bool] = None
    
    # Override source tracking
    before_override_source: Optional[str] = None
    after_override_source: Optional[str] = None
    
    def has_changes(self) -> bool:
        """Check if this field has any changes."""
        return (
            self.value_changed
            or self.label_changed
            or self.description_changed
            or self.required_changed
            or bool(self.preset_changes)
            or self.locking_changes is not None
            or self.hidden_changed
        )
    
    def get_summary(self) -> str:
        """Get a one-line summary of all changes."""
        changes = []
        if self.value_changed:
            changes.append("value")
        if self.label_changed:
            changes.append("label")
        if self.description_changed:
            changes.append("description")
        if self.required_changed:
            changes.append("required")
        if self.preset_changes:
            changes.append(f"presets ({len(self.preset_changes)})")
        if self.locking_changes:
            changes.append("locking")
        if self.hidden_changed:
            changes.append("visibility")
        
        return ", ".join(changes) if changes else "no changes"


@dataclass
class StepDiff:
    """Represents all changes to a single step."""
    step_id: str
    change_type: ChangeType
    
    # Step metadata changes
    title_changed: bool = False
    before_title: Optional[str] = None
    after_title: Optional[str] = None
    
    description_changed: bool = False
    before_description: Optional[str] = None
    after_description: Optional[str] = None
    
    # Field changes within step
    field_diffs: list[FieldDiff] = field(default_factory=list)
    fields_added: list[str] = field(default_factory=list)
    fields_removed: list[str] = field(default_factory=list)
    
    def has_changes(self) -> bool:
        """Check if this step has any changes."""
        return (
            self.title_changed
            or self.description_changed
            or bool(self.field_diffs)
            or bool(self.fields_added)
            or bool(self.fields_removed)
        )
    
    def get_change_summary(self) -> str:
        """Get summary of changes in this step."""
        summaries = []
        
        if self.title_changed:
            summaries.append(f"title changed")
        if self.description_changed:
            summaries.append(f"description changed")
        
        modified_fields = [d for d in self.field_diffs if d.has_changes()]
        if modified_fields:
            summaries.append(f"{len(modified_fields)} field(s) modified")
        
        if self.fields_added:
            summaries.append(f"{len(self.fields_added)} field(s) added")
        if self.fields_removed:
            summaries.append(f"{len(self.fields_removed)} field(s) removed")
        
        return " | ".join(summaries) if summaries else "no changes"


@dataclass
class ConfigDiff:
    """Represents all changes between two configurations."""
    before_id: str
    after_id: str
    
    # Config-level metadata changes
    title_changed: bool = False
    before_title: Optional[str] = None
    after_title: Optional[str] = None
    
    description_changed: bool = False
    before_description: Optional[str] = None
    after_description: Optional[str] = None
    
    # Step changes
    step_diffs: list[StepDiff] = field(default_factory=list)
    steps_added: list[str] = field(default_factory=list)
    steps_removed: list[str] = field(default_factory=list)
    
    def has_changes(self) -> bool:
        """Check if configs have any differences."""
        return (
            self.title_changed
            or self.description_changed
            or bool(self.step_diffs)
            or bool(self.steps_added)
            or bool(self.steps_removed)
        )
    
    def get_total_changes(self) -> int:
        """Get total number of changes."""
        count = 0
        if self.title_changed:
            count += 1
        if self.description_changed:
            count += 1
        
        for step_diff in self.step_diffs:
            if step_diff.has_changes():
                count += 1
        
        count += len(self.steps_added)
        count += len(self.steps_removed)
        
        return count


def compare_values(before: Any, after: Any) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Compare two values and return change status.
    
    Returns:
        Tuple of (changed, before_str, after_str) where strings are None if values unchanged
    """
    # Normalize for comparison
    before_norm = before
    after_norm = after
    
    if before_norm == after_norm:
        return False, None, None
    
    # Convert to strings for display
    before_str = str(before_norm) if before_norm is not None else None
    after_str = str(after_norm) if after_norm is not None else None
    
    return True, before_str, after_str


def extract_field_dict(field_obj: dict[str, Any]) -> dict[str, Any]:
    """Extract field data for comparison."""
    return {
        "id": field_obj.get("id"),
        "type": field_obj.get("type"),
        "label": field_obj.get("label"),
        "description": field_obj.get("description"),
        "default": field_obj.get("default"),
        "required": field_obj.get("required", False),
        "presets": field_obj.get("presets"),
        "editability": field_obj.get("editability", "free"),
        "hidden": field_obj.get("hidden", False),
        "locked_value": field_obj.get("locked_value"),
        "override_source": field_obj.get("override_source"),
    }


def compare_presets(
    before_presets: Optional[list[dict]] = None,
    after_presets: Optional[list[dict]] = None,
) -> list[PresetChange]:
    """Compare preset lists and return changes."""
    changes = []
    
    before_presets = before_presets or []
    after_presets = after_presets or []
    
    # Create maps by label for easier comparison
    before_map = {p.get("label"): p for p in before_presets}
    after_map = {p.get("label"): p for p in after_presets}
    
    # Check for removed and modified presets
    for label, before_preset in before_map.items():
        if label not in after_map:
            changes.append(
                PresetChange(
                    change_type=ChangeType.REMOVED,
                    label=label,
                    before_value=before_preset.get("value"),
                    before_mode=before_preset.get("mode", "append"),
                    description=before_preset.get("description"),
                )
            )
        else:
            after_preset = after_map[label]
            # Check if preset modified
            if before_preset.get("value") != after_preset.get("value") or \
               before_preset.get("mode", "append") != after_preset.get("mode", "append"):
                changes.append(
                    PresetChange(
                        change_type=ChangeType.MODIFIED,
                        label=label,
                        before_value=before_preset.get("value"),
                        after_value=after_preset.get("value"),
                        before_mode=before_preset.get("mode", "append"),
                        after_mode=after_preset.get("mode", "append"),
                        description=after_preset.get("description"),
                    )
                )
    
    # Check for added presets
    for label, after_preset in after_map.items():
        if label not in before_map:
            changes.append(
                PresetChange(
                    change_type=ChangeType.ADDED,
                    label=label,
                    after_value=after_preset.get("value"),
                    after_mode=after_preset.get("mode", "append"),
                    description=after_preset.get("description"),
                )
            )
    
    return changes


def compare_fields(
    before_field: dict[str, Any],
    after_field: dict[str, Any],
) -> FieldDiff:
    """Compare two field definitions and return differences."""
    field_id = after_field.get("id") or before_field.get("id")
    field_type = after_field.get("type") or before_field.get("type")
    
    # Determine if field was added/removed/modified
    if not before_field:
        change_type = ChangeType.ADDED
    elif not after_field:
        change_type = ChangeType.REMOVED
    else:
        change_type = ChangeType.MODIFIED
    
    diff = FieldDiff(
        field_id=field_id,
        field_type=str(field_type),
        change_type=change_type,
    )
    
    if change_type == ChangeType.REMOVED:
        # Field was removed, capture before state
        before_data = extract_field_dict(before_field)
        diff.before_label = before_data["label"]
        diff.before_description = before_data["description"]
        return diff
    
    if change_type == ChangeType.ADDED:
        # Field was added, capture after state
        after_data = extract_field_dict(after_field)
        diff.after_label = after_data["label"]
        diff.after_description = after_data["description"]
        return diff
    
    # Field exists in both, compare properties
    before_data = extract_field_dict(before_field)
    after_data = extract_field_dict(after_field)
    
    # Compare simple fields
    if before_data["label"] != after_data["label"]:
        diff.label_changed = True
        diff.before_label = before_data["label"]
        diff.after_label = after_data["label"]
    
    if before_data["description"] != after_data["description"]:
        diff.description_changed = True
        diff.before_description = before_data["description"]
        diff.after_description = after_data["description"]
    
    if before_data["default"] != after_data["default"]:
        diff.value_changed = True
        diff.before_value = before_data["default"]
        diff.after_value = after_data["default"]
    
    if before_data["required"] != after_data["required"]:
        diff.required_changed = True
        diff.before_required = before_data["required"]
        diff.after_required = after_data["required"]
    
    if before_data["hidden"] != after_data["hidden"]:
        diff.hidden_changed = True
        diff.before_hidden = before_data["hidden"]
        diff.after_hidden = after_data["hidden"]
    
    # Compare presets
    preset_changes = compare_presets(
        before_data["presets"],
        after_data["presets"],
    )
    if preset_changes:
        diff.preset_changes = preset_changes
    
    # Compare locking/editability
    before_editability = before_data["editability"]
    after_editability = after_data["editability"]
    before_locked_value = before_data["locked_value"]
    after_locked_value = after_data["locked_value"]
    
    if before_editability != after_editability or before_locked_value != after_locked_value:
        diff.locking_changes = LockingChange(
            change_type=ChangeType.MODIFIED,
            before_state=before_editability,
            after_state=after_editability,
            before_locked_value=before_locked_value,
            after_locked_value=after_locked_value,
        )
    
    # Track override source
    if before_data["override_source"] != after_data["override_source"]:
        diff.before_override_source = before_data["override_source"]
        diff.after_override_source = after_data["override_source"]
    
    return diff


def compare_steps(
    before_step: dict[str, Any],
    after_step: dict[str, Any],
) -> StepDiff:
    """Compare two step definitions and return differences."""
    step_id = after_step.get("id") or before_step.get("id")
    
    # Determine if step was added/removed/modified
    if not before_step:
        change_type = ChangeType.ADDED
    elif not after_step:
        change_type = ChangeType.REMOVED
    else:
        change_type = ChangeType.MODIFIED
    
    diff = StepDiff(
        step_id=step_id,
        change_type=change_type,
    )
    
    if change_type == ChangeType.REMOVED:
        diff.before_title = before_step.get("title")
        diff.before_description = before_step.get("description")
        return diff
    
    if change_type == ChangeType.ADDED:
        diff.after_title = after_step.get("title")
        diff.after_description = after_step.get("description")
        return diff
    
    # Step exists in both, compare properties
    if before_step.get("title") != after_step.get("title"):
        diff.title_changed = True
        diff.before_title = before_step.get("title")
        diff.after_title = after_step.get("title")
    
    if before_step.get("description") != after_step.get("description"):
        diff.description_changed = True
        diff.before_description = before_step.get("description")
        diff.after_description = after_step.get("description")
    
    # Compare fields within step
    before_fields = before_step.get("fields", []) or []
    after_fields = after_step.get("fields", []) or []
    
    before_field_map = {f.get("id"): f for f in before_fields}
    after_field_map = {f.get("id"): f for f in after_fields}
    
    all_field_ids = set(before_field_map.keys()) | set(after_field_map.keys())
    
    for field_id in sorted(all_field_ids):
        before_field = before_field_map.get(field_id, {})
        after_field = after_field_map.get(field_id, {})
        
        if not before_field:
            diff.fields_added.append(field_id)
        elif not after_field:
            diff.fields_removed.append(field_id)
        else:
            field_diff = compare_fields(before_field, after_field)
            if field_diff.has_changes():
                diff.field_diffs.append(field_diff)
    
    return diff


def compare_configs(before: dict[str, Any], after: dict[str, Any]) -> ConfigDiff:
    """
    Compare two configuration dictionaries and return detailed diff.
    
    Args:
        before: The original/previous configuration
        after: The new/current configuration
    
    Returns:
        ConfigDiff object containing all differences
    """
    before_id = before.get("id", "unknown")
    after_id = after.get("id", "unknown")
    
    diff = ConfigDiff(
        before_id=before_id,
        after_id=after_id,
    )
    
    # Compare config-level metadata
    if before.get("title") != after.get("title"):
        diff.title_changed = True
        diff.before_title = before.get("title")
        diff.after_title = after.get("title")
    
    if before.get("description") != after.get("description"):
        diff.description_changed = True
        diff.before_description = before.get("description")
        diff.after_description = after.get("description")
    
    # Compare steps
    before_steps = before.get("steps", []) or []
    after_steps = after.get("steps", []) or []
    
    before_step_map = {s.get("id"): s for s in before_steps}
    after_step_map = {s.get("id"): s for s in after_steps}
    
    all_step_ids = set(before_step_map.keys()) | set(after_step_map.keys())
    
    for step_id in sorted(all_step_ids):
        before_step = before_step_map.get(step_id, {})
        after_step = after_step_map.get(step_id, {})
        
        if not before_step:
            diff.steps_added.append(step_id)
        elif not after_step:
            diff.steps_removed.append(step_id)
        else:
            step_diff = compare_steps(before_step, after_step)
            if step_diff.has_changes():
                diff.step_diffs.append(step_diff)
    
    return diff


def diff_to_dict(diff: ConfigDiff) -> dict[str, Any]:
    """
    Convert ConfigDiff to a dictionary suitable for JSON serialization and UI display.
    
    This provides a clean, nested structure that's easy to consume in UI/API responses.
    """
    return {
        "before_id": diff.before_id,
        "after_id": diff.after_id,
        "has_changes": diff.has_changes(),
        "total_changes": diff.get_total_changes(),
        "metadata_changes": {
            "title": {
                "changed": diff.title_changed,
                "before": diff.before_title,
                "after": diff.after_title,
            } if diff.title_changed else None,
            "description": {
                "changed": diff.description_changed,
                "before": diff.before_description,
                "after": diff.after_description,
            } if diff.description_changed else None,
        },
        "steps": {
            "added": diff.steps_added,
            "removed": diff.steps_removed,
            "modified": [
                {
                    "id": step_diff.step_id,
                    "changes": step_diff.get_change_summary(),
                    "title": {
                        "changed": step_diff.title_changed,
                        "before": step_diff.before_title,
                        "after": step_diff.after_title,
                    } if step_diff.title_changed else None,
                    "description": {
                        "changed": step_diff.description_changed,
                        "before": step_diff.before_description,
                        "after": step_diff.after_description,
                    } if step_diff.description_changed else None,
                    "fields": {
                        "added": step_diff.fields_added,
                        "removed": step_diff.fields_removed,
                        "modified": [
                            {
                                "id": field_diff.field_id,
                                "type": field_diff.field_type,
                                "changes": field_diff.get_summary(),
                                "value": {
                                    "changed": field_diff.value_changed,
                                    "before": field_diff.before_value,
                                    "after": field_diff.after_value,
                                } if field_diff.value_changed else None,
                                "label": {
                                    "changed": field_diff.label_changed,
                                    "before": field_diff.before_label,
                                    "after": field_diff.after_label,
                                } if field_diff.label_changed else None,
                                "description": {
                                    "changed": field_diff.description_changed,
                                    "before": field_diff.before_description,
                                    "after": field_diff.after_description,
                                } if field_diff.description_changed else None,
                                "required": {
                                    "changed": field_diff.required_changed,
                                    "before": field_diff.before_required,
                                    "after": field_diff.after_required,
                                } if field_diff.required_changed else None,
                                "hidden": {
                                    "changed": field_diff.hidden_changed,
                                    "before": field_diff.before_hidden,
                                    "after": field_diff.after_hidden,
                                } if field_diff.hidden_changed else None,
                                "presets": [
                                    {
                                        "type": preset_change.change_type.value,
                                        "label": preset_change.label,
                                        "before": {
                                            "value": preset_change.before_value,
                                            "mode": preset_change.before_mode,
                                        } if preset_change.before_value is not None else None,
                                        "after": {
                                            "value": preset_change.after_value,
                                            "mode": preset_change.after_mode,
                                        } if preset_change.after_value is not None else None,
                                    }
                                    for preset_change in field_diff.preset_changes
                                ] if field_diff.preset_changes else None,
                                "locking": {
                                    "changed": field_diff.locking_changes is not None,
                                    "before_state": field_diff.locking_changes.before_state if field_diff.locking_changes else None,
                                    "after_state": field_diff.locking_changes.after_state if field_diff.locking_changes else None,
                                    "before_locked_value": field_diff.locking_changes.before_locked_value if field_diff.locking_changes else None,
                                    "after_locked_value": field_diff.locking_changes.after_locked_value if field_diff.locking_changes else None,
                                } if field_diff.locking_changes is not None else None,
                            }
                            for field_diff in step_diff.field_diffs
                        ] if step_diff.field_diffs else [],
                    },
                }
                for step_diff in diff.step_diffs
            ],
        },
    }
