"""Tests for app/enums.py — StrEnum definitions."""

import pytest

from app.enums import FieldType, OutputFormat, PresetMode


class TestFieldType:
    def test_values_are_strings(self):
        for member in FieldType:
            assert isinstance(member, str)

    def test_equality_with_plain_string(self):
        assert FieldType.text == "text"
        assert FieldType.textarea == "textarea"
        assert FieldType.select == "select"
        assert FieldType.multi_select == "multi_select"
        assert FieldType.checkbox == "checkbox"
        assert FieldType.agent_list == "agent_list"

    def test_usable_in_f_string_without_dot_value(self):
        assert f"{FieldType.text}" == "text"
        assert f"{FieldType.agent_list}" == "agent_list"

    def test_lookup_by_value(self):
        assert FieldType("textarea") is FieldType.textarea

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            FieldType("unknown_field_type")

    def test_all_members_present(self):
        members = {m.value for m in FieldType}
        assert members == {"text", "textarea", "select", "multi_select", "checkbox", "agent_list", "repeatable_group"}


class TestOutputFormat:
    def test_values_are_strings(self):
        for member in OutputFormat:
            assert isinstance(member, str)

    def test_equality_with_plain_string(self):
        assert OutputFormat.text == "text"
        assert OutputFormat.markdown == "markdown"
        assert OutputFormat.markdown_frontmatter == "markdown_frontmatter"
        assert OutputFormat.verbatim == "verbatim"

    def test_usable_in_f_string_without_dot_value(self):
        assert f"{OutputFormat.verbatim}" == "verbatim"

    def test_lookup_by_value(self):
        assert OutputFormat("markdown") is OutputFormat.markdown

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            OutputFormat("html")

    def test_all_members_present(self):
        members = {m.value for m in OutputFormat}
        assert members == {"text", "markdown", "markdown_frontmatter", "verbatim"}


class TestPresetMode:
    def test_values_are_strings(self):
        for member in PresetMode:
            assert isinstance(member, str)

    def test_equality_with_plain_string(self):
        assert PresetMode.append == "append"
        assert PresetMode.replace == "replace"
        assert PresetMode.merge_json == "merge_json"

    def test_usable_in_f_string_without_dot_value(self):
        assert f"{PresetMode.replace}" == "replace"

    def test_lookup_by_value(self):
        assert PresetMode("append") is PresetMode.append

    def test_invalid_value_raises(self):
        with pytest.raises(ValueError):
            PresetMode("upsert")

    def test_all_members_present(self):
        members = {m.value for m in PresetMode}
        assert members == {"append", "replace", "merge_json"}
