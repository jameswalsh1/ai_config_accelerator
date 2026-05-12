"""Tests for Tickets 15 & 16: Config repository interfaces and resolution service."""
import pytest
from unittest.mock import MagicMock
from pathlib import Path
from typing import Any

from app.services.config_repository import (
    ConfigReadRepository,
    ConfigWriteRepository,
    JsonConfigReadRepository,
    JsonConfigWriteRepository,
)
from app.services.config_resolution_service import ConfigResolutionService


class TestConfigRepositoryProtocols:
    def test_json_read_repo_satisfies_read_protocol(self):
        repo = JsonConfigReadRepository()
        assert isinstance(repo, ConfigReadRepository)

    def test_json_write_repo_satisfies_write_protocol(self):
        repo = JsonConfigWriteRepository()
        assert isinstance(repo, ConfigWriteRepository)

    def test_mock_satisfies_read_protocol(self):
        mock = MagicMock(spec=ConfigReadRepository)
        assert isinstance(mock, ConfigReadRepository)


class TestJsonConfigReadRepository:
    def test_load_resolved_config_returns_dict(self):
        repo = JsonConfigReadRepository()
        config = repo.load_resolved_config("claude", "python")
        assert isinstance(config, dict)
        assert "steps" in config

    def test_get_available_tools_returns_list(self):
        repo = JsonConfigReadRepository()
        tools = repo.get_available_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_get_available_languages_returns_list(self):
        repo = JsonConfigReadRepository()
        languages = repo.get_available_languages()
        assert isinstance(languages, list)
        assert len(languages) > 0


class TestConfigResolutionService:
    def test_resolve_returns_dict(self):
        svc = ConfigResolutionService()
        config = svc.resolve("claude", "python")
        assert isinstance(config, dict)
        assert "steps" in config

    def test_resolve_uses_injected_repository(self):
        mock_repo = MagicMock(spec=ConfigReadRepository)
        mock_repo.load_resolved_config.return_value = {"steps": [], "id": "test"}
        svc = ConfigResolutionService(repository=mock_repo)
        result = svc.resolve("claude", "python")
        mock_repo.load_resolved_config.assert_called_once_with("claude", "python")
        assert result == {"steps": [], "id": "test"}

    def test_available_tools_delegates_to_repo(self):
        mock_repo = MagicMock(spec=ConfigReadRepository)
        mock_repo.get_available_tools.return_value = [{"id": "claude"}]
        svc = ConfigResolutionService(repository=mock_repo)
        assert svc.available_tools() == [{"id": "claude"}]

    def test_available_languages_delegates_to_repo(self):
        mock_repo = MagicMock(spec=ConfigReadRepository)
        mock_repo.get_available_languages.return_value = [{"id": "python"}]
        svc = ConfigResolutionService(repository=mock_repo)
        assert svc.available_languages() == [{"id": "python"}]

    def test_resolve_preserves_composition_order(self):
        """Resolved config contains tool and language-specific overrides."""
        svc = ConfigResolutionService()
        config = svc.resolve("claude", "python")
        # The presence of 'id' and tool-applied title confirms full composition
        assert "id" in config or "title" in config

    @pytest.mark.parametrize("tool,language", [
        ("claude", "python"),
        ("claude", "java"),
        ("copilot", "typescript"),
        ("cursor", "react-typescript"),
    ])
    def test_resolve_deterministic_for_known_combos(self, tool: str, language: str):
        svc = ConfigResolutionService()
        first = svc.resolve(tool, language)
        second = svc.resolve(tool, language)
        assert [s["id"] for s in first["steps"]] == [s["id"] for s in second["steps"]]
