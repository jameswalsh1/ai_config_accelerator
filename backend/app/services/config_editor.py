"""
Config Editor Service

Provides functionality to extract and track editable configuration slices
for specific steps, including override sources and editability status.
"""

from typing import Any


def get_editable_step(
    config: dict[str, Any], step_id: str
) -> dict[str, Any]:
    """
    Extract editable configuration slice for a specific step.

    Args:
        config: Fully resolved wizard configuration
        step_id: The step ID to extract

    Returns:
        Dictionary containing:
        - step: Full step with fields enhanced with override/editability metadata
        - source_tracking: Summary of override sources used
        
    Raises:
        ValueError: If step_id not found
    """
    steps = config.get("steps", [])
    step = None
    
    for s in steps:
        if s.get("id") == step_id:
            step = s
            break
    
    if step is None:
        raise ValueError(f"Step '{step_id}' not found in configuration")
    
    # Enhance step fields with editability metadata
    enhanced_step = _enhance_step_with_metadata(step)
    
    # Build source tracking summary
    source_tracking = _extract_source_tracking(enhanced_step)
    
    return {
        "step": enhanced_step,
        "source_tracking": source_tracking,
    }


def _enhance_step_with_metadata(step: dict[str, Any]) -> dict[str, Any]:
    """
    Enhance step fields with editability and override source metadata.
    
    Adds to each field:
    - is_locked: True if field is read-only
    - is_default: True if using schema default (not overridden)
    - override_source: Layer where override came from
    """
    enhanced = {**step}
    enhanced_fields = []
    
    for field in step.get("fields", []):
        enhanced_field = _enhance_field_with_metadata(field)
        enhanced_fields.append(enhanced_field)
    
    enhanced["fields"] = enhanced_fields
    return enhanced


def _enhance_field_with_metadata(field: dict[str, Any]) -> dict[str, Any]:
    """
    Enhance individual field with editability and source tracking.
    """
    enhanced = {**field}
    
    # Track if locked
    editability = field.get("editability", "free")
    enhanced["is_locked"] = (
        editability == "locked" or 
        editability == "readonly"
    )
    
    # Track if using default (not overridden)
    override_source = field.get("override_source", "schema")
    enhanced["is_default"] = override_source == "schema"
    
    # Ensure editability is present
    enhanced["editability"] = editability
    enhanced["override_source"] = override_source
    
    # Include lock_reason if present
    if "lock_reason" in field:
        enhanced["lock_reason"] = field["lock_reason"]
    
    return enhanced


def _extract_source_tracking(step: dict[str, Any]) -> dict[str, Any]:
    """
    Extract summary of override sources used across all fields in step.
    
    Returns:
        Dictionary with counts of fields by source and editability status
    """
    fields = step.get("fields", [])
    sources: dict[str, int] = {}
    editability_counts: dict[str, int] = {"free": 0, "locked": 0, "suggested": 0, "defaulted": 0, "other": 0}
    locked_count = 0
    default_count = 0
    overridden_count = 0
    
    for field in fields:
        # Count by source
        source = field.get("override_source", "schema")
        sources[source] = sources.get(source, 0) + 1
        
        # Count by editability
        editability = field.get("editability", "free")
        if editability in editability_counts:
            editability_counts[editability] += 1
        else:
            editability_counts["other"] += 1
        
        # Count specific statuses
        if field.get("is_locked"):
            locked_count += 1
        if field.get("is_default"):
            default_count += 1
        else:
            overridden_count += 1
    
    return {
        "total_fields": len(fields),
        "by_source": sources,
        "by_editability": {k: v for k, v in editability_counts.items() if v > 0},
        "locked_fields": locked_count,
        "default_fields": default_count,
        "overridden_fields": overridden_count,
    }
