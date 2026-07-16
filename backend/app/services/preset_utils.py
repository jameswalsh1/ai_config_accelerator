"""
Preset extraction utilities.

Operates on resolved wizard config dicts (from any source) to extract
and categorise presets by tool/language/shared.
"""

from typing import Any


def extract_presets_from_config(
    config: dict[str, Any], tool_id: str, language_id: str
) -> dict[str, list[dict[str, Any]]]:
    """
    Extract all presets from a resolved wizard config and categorize them.

    Args:
        config: Resolved wizard config dict
        tool_id: Tool identifier (e.g., 'claude', 'copilot')
        language_id: Language identifier (e.g., 'python', 'java')

    Returns:
        Dict with keys 'shared', 'language', 'tool' containing lists of preset dicts
    """
    shared_presets: list[dict[str, Any]] = []
    language_presets: list[dict[str, Any]] = []
    tool_presets: list[dict[str, Any]] = []

    for step in config.get("steps", []):
        for field in step.get("fields", []):
            _collect_presets_from_field(
                field, shared_presets, language_presets, tool_presets, tool_id, language_id
            )

    return {
        "shared": shared_presets,
        "language": language_presets,
        "tool": tool_presets,
    }


def _collect_presets_from_field(
    field: dict[str, Any],
    shared_presets: list[dict[str, Any]],
    language_presets: list[dict[str, Any]],
    tool_presets: list[dict[str, Any]],
    tool_id: str,
    language_id: str,
) -> None:
    """Recursively collect presets from a field and its nested fields."""
    for preset in field.get("presets", []):
        categorized = False

        tags = preset.get("tags", [])
        if len(tags) > 1 and tool_id in tags:
            shared_presets.append(preset)
            categorized = True

        if language_id in tags:
            language_presets.append(preset)
            categorized = True

        if not categorized:
            tool_presets.append(preset)

    for nested_field in field.get("fields", []):
        _collect_presets_from_field(
            nested_field, shared_presets, language_presets, tool_presets, tool_id, language_id
        )
