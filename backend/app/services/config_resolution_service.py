"""
Config resolution service (Ticket 16).

Wraps config composition with a clean service boundary.
Preserves the existing composition order:
    schema.json → tool override → language override → combo override → preset expansion

Depends on ConfigReadRepository so the underlying source (JSON or database)
can be swapped without changing callers.
"""
from __future__ import annotations

from typing import Any

from app.services.config_repository import ConfigReadRepository, JsonConfigReadRepository


class ConfigResolutionService:
    """
    Resolves a fully composed wizard configuration for a given tool + language.

    Usage::

        svc = ConfigResolutionService()  # uses JSON by default
        config = svc.resolve("claude", "python")
    """

    def __init__(self, repository: ConfigReadRepository | None = None) -> None:
        self._repo: ConfigReadRepository = repository or JsonConfigReadRepository()

    def resolve(self, tool_id: str, language_id: str) -> dict[str, Any]:
        """
        Return a fully resolved wizard config dict for the given tool + language.

        Composition order (delegated to the repository):
            1. Base schema
            2. Tool overrides
            3. Language overrides
            4. Tool+language combo overrides
            5. Preset file expansion

        Args:
            tool_id: e.g. "claude", "copilot", "cursor"
            language_id: e.g. "python", "java", "react-typescript"

        Returns:
            Composed config dict ready for rendering / editing.
        """
        return self._repo.load_resolved_config(tool_id, language_id)

    def available_tools(self) -> list[dict[str, Any]]:
        """Return available tool summaries from the repository."""
        return self._repo.get_available_tools()

    def available_languages(self) -> list[dict[str, Any]]:
        """Return available language summaries from the repository."""
        return self._repo.get_available_languages()
