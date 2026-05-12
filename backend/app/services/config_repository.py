"""
Config repository protocol interfaces (Ticket 15).

Defines read and write repository protocols so the database-backed
implementations can be swapped or extended without changing service layer code.
"""
from __future__ import annotations

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
