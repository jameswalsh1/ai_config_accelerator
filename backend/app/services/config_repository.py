"""
Config repository protocol interfaces (Ticket 15).

Defines read and write repository protocols so future implementations
(database-backed) can be swapped in without changing service layer code.

JSON-backed implementations wrap the existing service functions.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol, runtime_checkable


# ---------------------------------------------------------------------------
# Protocol definitions
# ---------------------------------------------------------------------------


@runtime_checkable
class ConfigReadRepository(Protocol):
    """Protocol for reading wizard configuration data."""

    def load_resolved_config(self, tool_id: str, language_id: str) -> dict[str, Any]:
        """Return a fully resolved (composed) wizard config dict."""
        ...

    def get_available_tools(self) -> list[dict[str, Any]]:
        """Return list of available tool summaries."""
        ...

    def get_available_languages(self) -> list[dict[str, Any]]:
        """Return list of available language summaries."""
        ...


@runtime_checkable
class ConfigWriteRepository(Protocol):
    """Protocol for persisting wizard configuration overrides."""

    def save_override(
        self,
        file_path: Path,
        data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        """Persist an override file atomically."""
        ...


# ---------------------------------------------------------------------------
# JSON-backed implementations
# ---------------------------------------------------------------------------


class JsonConfigReadRepository:
    """Reads configuration from JSON files on disk (current runtime default)."""

    def load_resolved_config(self, tool_id: str, language_id: str) -> dict[str, Any]:
        from app.services.config_loader_composable import load_composable_config

        return load_composable_config(tool_id, language_id)

    def get_available_tools(self) -> list[dict[str, Any]]:
        from app.services.config_loader_composable import get_available_tools

        tools = get_available_tools()
        return [t.model_dump() if hasattr(t, "model_dump") else dict(t) for t in tools]

    def get_available_languages(self) -> list[dict[str, Any]]:
        from app.services.config_loader_composable import get_available_languages

        langs = get_available_languages()
        return [la.model_dump() if hasattr(la, "model_dump") else dict(la) for la in langs]


class JsonConfigWriteRepository:
    """Persists configuration overrides to JSON files on disk."""

    def save_override(
        self,
        file_path: Path,
        data: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> None:
        from app.services.config_persistence import save_config

        save_config(file_path, data, validate=False, create_backup=True, context=context)
