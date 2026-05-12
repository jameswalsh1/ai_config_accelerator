"""Pydantic request models for config editor mutation endpoints.

These models replace the raw ``dict[str, Any]`` payloads previously accepted
by the mutation endpoints, providing:

- Early 422 validation with clear error messages.
- Explicit field contracts for frontend consumers.
- A stable API shape that future database-backed implementations can rely on.

All models preserve the existing field names used by the frontend so that
no frontend changes are required.
"""

from typing import Any, Literal

from pydantic import BaseModel, field_validator

# ── Shared types ──────────────────────────────────────────────────────────────

ScopeType = Literal["tool", "language", "override"]
OverrideType = Literal["metadata", "structure"]
EditabilityType = Literal["free", "locked", "suggested", "defaulted"]


# ── Request models ────────────────────────────────────────────────────────────


class UpdateFieldRequest(BaseModel):
    """Request body for ``POST /config/update``.

    Updates the default value and/or editability of a specific field inside a
    tool, language, or combo override file.
    """

    scope: ScopeType
    target: str
    tool: str
    language: str
    step_id: str
    field_id: str
    changes: dict[str, Any] = {}

    @field_validator("target", "tool", "language", "step_id", "field_id", mode="before")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class ResetFieldRequest(BaseModel):
    """Request body for ``POST /config/reset``.

    Removes a field override from the specified scope, reverting the field to
    the value from a lower-priority layer.
    """

    scope: ScopeType
    target: str
    tool: str
    language: str
    step_id: str
    field_id: str
    override_type: OverrideType = "metadata"

    @field_validator("target", "tool", "language", "step_id", "field_id", mode="before")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class PresetData(BaseModel):
    """A single preset chip definition."""

    label: str
    value: Any
    description: str | None = None
    mode: str = "append"
    tags: list[str] | None = None

    @field_validator("label", mode="before")
    @classmethod
    def _label_not_blank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("preset label must be a non-empty string")
        return v


class AddPresetRequest(BaseModel):
    """Request body for ``POST /config/presets/add``."""

    scope: ScopeType
    target: str
    tool: str
    language: str
    step_id: str
    field_id: str
    preset: PresetData
    position: int | None = None

    @field_validator("target", "tool", "language", "step_id", "field_id", mode="before")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class RemovePresetRequest(BaseModel):
    """Request body for ``POST /config/presets/remove``.

    Either ``preset_label`` or ``position`` must be provided.
    """

    scope: ScopeType
    target: str
    tool: str
    language: str
    step_id: str
    field_id: str
    preset_label: str | None = None
    position: int | None = None

    @field_validator("target", "tool", "language", "step_id", "field_id", mode="before")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v

    def model_post_init(self, __context: Any) -> None:
        if self.preset_label is None and self.position is None:
            raise ValueError("Must specify either preset_label or position")


class CreateLanguageRequest(BaseModel):
    """Request body for ``POST /config/languages``."""

    language_id: str | None = None
    title: str
    description: str = ""
    based_on: str | None = None
    tag_remap: dict[str, str] | None = None

    @field_validator("title", mode="before")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v


class RestoreVersionRequest(BaseModel):
    """Request body for ``POST /config/history/restore``.

    Restores a previous database version snapshot to become the current state.
    Only supported when CONFIG_SOURCE=database.
    """

    scope: ScopeType
    target: str
    version: int

    @field_validator("target", mode="before")
    @classmethod
    def _not_blank(cls, v: str) -> str:
        if not isinstance(v, str) or not v.strip():
            raise ValueError("must be a non-empty string")
        return v

    @field_validator("version", mode="before")
    @classmethod
    def _version_positive(cls, v: int) -> int:
        if not isinstance(v, int) or v < 1:
            raise ValueError("version must be a positive integer")
        return v
