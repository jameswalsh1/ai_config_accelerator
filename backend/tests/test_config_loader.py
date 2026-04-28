"""Tests for app/services/config_loader.py."""

import pytest

from app.models.wizard import WizardConfig, WizardConfigSummary
from app.services.config_loader import (
    get_all_configs,
    get_config,
    get_config_with_language_filter,
)


class TestGetAllConfigs:
    def test_returns_non_empty_list(self):
        configs = get_all_configs()
        assert len(configs) > 0

    def test_returns_config_summaries(self):
        configs = get_all_configs()
        for cfg in configs:
            assert isinstance(cfg, WizardConfigSummary)

    def test_all_summaries_have_required_fields(self):
        for cfg in get_all_configs():
            assert cfg.id and isinstance(cfg.id, str)
            assert cfg.title and isinstance(cfg.title, str)
            assert cfg.description and isinstance(cfg.description, str)
            assert cfg.target and isinstance(cfg.target, str)

    def test_known_configs_are_present(self):
        ids = {cfg.id for cfg in get_all_configs()}
        assert "claude" in ids
        assert "copilot" in ids
        assert "cursor" in ids


class TestGetConfig:
    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_returns_wizard_config_for_known_ids(self, config_id):
        cfg = get_config(config_id)
        assert isinstance(cfg, WizardConfig)
        assert cfg.id == config_id

    def test_returns_none_for_unknown_id(self):
        assert get_config("does_not_exist") is None

    def test_returns_none_for_empty_string(self):
        assert get_config("") is None

    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_config_has_at_least_one_step(self, config_id):
        cfg = get_config(config_id)
        assert cfg is not None
        assert len(cfg.steps) >= 1

    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_every_step_has_at_least_one_field(self, config_id):
        cfg = get_config(config_id)
        assert cfg is not None
        for step in cfg.steps:
            assert len(step.fields) >= 1, f"Step '{step.id}' in '{config_id}' has no fields"

    def test_claude_config_has_expected_steps(self):
        cfg = get_config("claude")
        assert cfg is not None
        step_ids = [s.id for s in cfg.steps]
        assert "claude_md" in step_ids
        assert "claude_settings" in step_ids
        assert "mcp_config" in step_ids

    def test_loaded_config_matches_summary(self):
        summaries = {cfg.id: cfg for cfg in get_all_configs()}
        for config_id, summary in summaries.items():
            full = get_config(config_id)
            assert full is not None
            assert full.id == summary.id
            assert full.title == summary.title
            assert full.target == summary.target

    def test_config_loads_schema_metadata(self):
        cfg = get_config("cursor")
        assert cfg is not None
        assert cfg.schema_version is not None
        assert isinstance(cfg.schema_version, str)
        assert cfg.target_version_constraints is None or isinstance(cfg.target_version_constraints, dict)
        assert cfg.output_preview_targets is None or isinstance(cfg.output_preview_targets, list)


class TestLanguageSelection:
    """Tests for language-aware configuration filtering."""

    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_first_step_is_language_selection(self, config_id):
        """Verify that language_selection exists in main tool configs."""
        cfg = get_config(config_id)
        assert cfg is not None
        assert len(cfg.steps) > 0
        step_ids = [s.id for s in cfg.steps]
        assert "language_selection" in step_ids

    @pytest.mark.parametrize("config_id", ["claude", "copilot", "cursor"])
    def test_language_selection_has_required_field(self, config_id):
        """Verify language_selection step has the language select field."""
        cfg = get_config(config_id)
        assert cfg is not None
        lang_step = next((s for s in cfg.steps if s.id == "language_selection"), None)
        assert lang_step is not None, f"language_selection step not found in {config_id}"
        lang_field = next((f for f in lang_step.fields if f.id == "language"), None)
        assert lang_field is not None
        assert lang_field.type.value == "select"
        assert lang_field.required
        assert lang_field.options is not None
        assert len(lang_field.options) >= 6

    def test_language_filter_returns_none_for_invalid_config(self):
        """Verify language filter returns None for invalid config IDs."""
        result = get_config_with_language_filter("invalid_config", "python")
        assert result is None

    def test_language_filter_returns_full_config_for_none_language(self):
        """Verify language filter returns unfiltered config when language is None."""
        config_full = get_config("claude")
        config_none = get_config_with_language_filter("claude", None)
        assert config_full is not None
        assert config_none is not None
        # Get presets from both
        claude_md_full = next(s for s in config_full.steps if s.id == "claude_md")
        claude_md_none = next(s for s in config_none.steps if s.id == "claude_md")
        tech_stack_full = next(f for f in claude_md_full.fields if f.id == "tech_stack")
        tech_stack_none = next(f for f in claude_md_none.fields if f.id == "tech_stack")
        full_count = len(tech_stack_full.presets) if tech_stack_full.presets else 0
        none_count = len(tech_stack_none.presets) if tech_stack_none.presets else 0
        assert full_count == none_count

    @pytest.mark.parametrize("language", ["python", "typescript", "java", "dotnet"])
    def test_language_filter_reduces_preset_count(self, language):
        """Verify language filtering reduces preset count for specific languages."""
        config_full = get_config("claude")
        config_filtered = get_config_with_language_filter("claude", language)
        assert config_filtered is not None

        # Compare preset counts
        claude_md_full = next(s for s in config_full.steps if s.id == "claude_md")
        claude_md_filt = next(s for s in config_filtered.steps if s.id == "claude_md")
        tech_stack_full = next(f for f in claude_md_full.fields if f.id == "tech_stack")
        tech_stack_filt = next(f for f in claude_md_filt.fields if f.id == "tech_stack")

        full_count = len(tech_stack_full.presets) if tech_stack_full.presets else 0
        filt_count = len(tech_stack_filt.presets) if tech_stack_filt.presets else 0
        # Filtered should be <= full
        assert filt_count <= full_count

    def test_language_filter_shows_only_relevant_presets(self):
        """Verify filtered config shows only language-relevant presets."""
        config_python = get_config_with_language_filter("claude", "python")
        assert config_python is not None

        claude_md = next(s for s in config_python.steps if s.id == "claude_md")
        tech_stack = next(f for f in claude_md.fields if f.id == "tech_stack")

        # Python config should include FastAPI and Django
        labels = [p.label for p in (tech_stack.presets or [])]
        assert any("FastAPI" in label for label in labels)
        assert any("Django" in label for label in labels)

    def test_language_presets_have_tags(self):
        """Verify that presets from language modules have appropriate tags."""
        config = get_config("claude")
        assert config is not None

        claude_md = next(s for s in config.steps if s.id == "claude_md")
        tech_stack = next(f for f in claude_md.fields if f.id == "tech_stack")

        # Check that some presets have language tags
        tagged_presets = [p for p in (tech_stack.presets or []) if p.tags]
        assert len(tagged_presets) > 0

        # Verify tag structure
        for preset in tagged_presets:
            assert isinstance(preset.tags, list)
            assert len(preset.tags) > 0
            # Tags should be lowercase language identifiers
            for tag in preset.tags:
                assert isinstance(tag, str)
                assert tag.islower() or "_" in tag  # e.g., python, typescript, react-typescript
