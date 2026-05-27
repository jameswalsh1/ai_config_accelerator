"""Shared result type for all JSON → DB import services."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ImportResult:
    """Counts returned by each import function."""

    created: int = 0
    updated: int = 0
    unchanged: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)

    def merge(self, other: "ImportResult") -> "ImportResult":
        """Return a new ImportResult combining self and other."""
        return ImportResult(
            created=self.created + other.created,
            updated=self.updated + other.updated,
            unchanged=self.unchanged + other.unchanged,
            skipped=self.skipped + other.skipped,
            errors=self.errors + other.errors,
        )

    def __str__(self) -> str:  # pragma: no cover
        return (
            f"created={self.created} updated={self.updated} "
            f"unchanged={self.unchanged} skipped={self.skipped} "
            f"errors={len(self.errors)}"
        )
