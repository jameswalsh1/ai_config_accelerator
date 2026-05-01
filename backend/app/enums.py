"""
Shared enumerations for the AI Accelerator wizard.

All enums inherit from StrEnum so their values are plain strings — no need to
access `.value` in comparisons, f-strings, or JSON serialisation.
"""

from enum import StrEnum


class FieldType(StrEnum):
    text = "text"
    textarea = "textarea"
    select = "select"
    multi_select = "multi_select"
    checkbox = "checkbox"
    agent_list = "agent_list"  # one-or-more agent definitions; generates one file per agent
    repeatable_group = "repeatable_group"  # one-or-more grouped entries, e.g. multiple rule files


class OutputFormat(StrEnum):
    text = "text"  # key: value pairs (generic fallback)
    markdown = "markdown"  # Markdown with heading + section per field
    markdown_frontmatter = "markdown_frontmatter"  # YAML frontmatter + Markdown body
    verbatim = "verbatim"  # 'content' field rendered as-is


class PresetMode(StrEnum):
    append = "append"  # concat to existing text (text / textarea)
    overwrite = "overwrite"  # replace entire field value
    merge_json = "merge_json"  # deep-merge JSON objects (verbatim JSON fields)
