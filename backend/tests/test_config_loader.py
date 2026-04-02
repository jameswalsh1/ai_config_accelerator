"""Tests for app/services/config_loader.py."""

import pytest

from app.models.wizard import WizardConfig, WizardConfigSummary
from app.services.config_loader import get_all_configs, get_config


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
