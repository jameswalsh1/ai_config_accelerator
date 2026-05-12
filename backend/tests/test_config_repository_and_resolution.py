"""Tests for Tickets 15 & 16: Config repository interfaces and resolution service."""
import pytest
from unittest.mock import MagicMock
from typing import Any

from app.services.config_repository import ConfigReadRepository
from app.services.config_resolution_service import ConfigResolutionService


class TestConfigRepositoryProtocols:
    def test_mock_satisfies_read_protocol(self):
        mock = MagicMock(spec=ConfigReadRepository)
        assert isinstance(mock, ConfigReadRepository)


class TestConfigResolutionService:
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
