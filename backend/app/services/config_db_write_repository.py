"""Ticket 1 — Database-backed config write repository.

Implements write operations for config editor mutations against the database.
Mirrors the interface of the JSON-backed patcher (config_patcher.py) but
persists changes to config_layer, config_field_metadata_override, and
config_field_content_override instead of JSON files.

All write operations are transactional within the provided session. Callers
are responsible for calling ``session.commit()`` after successful writes.

Audit events (ConfigAuditEvent) and version snapshots (ConfigVersion) are
written within the same session so they roll back together if the primary
write fails.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import ConfigAuditEvent, ConfigVersion
from app.db.models.language import Language
from app.db.models.layer import (
    ConfigFieldContentOverride,
    ConfigFieldMetadataOverride,
    ConfigLayer,
)
from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.db.models.tool import AITool


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DatabaseConfigWriteError(Exception):
    """Raised when a DB config write operation fails."""


class LayerNotFoundError(DatabaseConfigWriteError):
    """Raised when the target config layer cannot be found or created."""


class FieldNotFoundError(DatabaseConfigWriteError):
    """Raised when a field cannot be resolved by field_path."""


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_active_schema(session: AsyncSession) -> ConfigSchema:
    res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = res.scalar_one_or_none()
    if schema is None:
        raise DatabaseConfigWriteError("No active config schema found in database")
    return schema


async def _get_or_create_tool_layer(
    session: AsyncSession, target: str, actor: str
) -> ConfigLayer:
    tool_res = await session.execute(
        select(AITool).where(AITool.tool_key == target)
    )
    tool = tool_res.scalar_one_or_none()
    if tool is None:
        raise LayerNotFoundError(f"Tool '{target}' not found in database")

    layer_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "tool",
            ConfigLayer.tool_id == tool.id,
            ConfigLayer.status == "active",
        ).limit(1)
    )
    layer = layer_res.scalar_one_or_none()
    if layer is None:
        layer = ConfigLayer(
            layer_type="tool",
            layer_key=f"tool:{target}",
            tool_id=tool.id,
            version="1",
            status="active",
            created_by=actor,
            updated_by=actor,
        )
        session.add(layer)
        await session.flush()
    return layer


async def _get_or_create_language_layer(
    session: AsyncSession, target: str, actor: str
) -> ConfigLayer:
    lang_res = await session.execute(
        select(Language).where(Language.language_key == target)
    )
    lang = lang_res.scalar_one_or_none()
    if lang is None:
        raise LayerNotFoundError(f"Language '{target}' not found in database")

    layer_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "language",
            ConfigLayer.language_id == lang.id,
            ConfigLayer.status == "active",
        ).limit(1)
    )
    layer = layer_res.scalar_one_or_none()
    if layer is None:
        layer = ConfigLayer(
            layer_type="language",
            layer_key=f"language:{target}",
            language_id=lang.id,
            version="1",
            status="active",
            created_by=actor,
            updated_by=actor,
        )
        session.add(layer)
        await session.flush()
    return layer


async def _get_or_create_combo_layer(
    session: AsyncSession, target: str, actor: str
) -> ConfigLayer:
    layer_key = f"override:{target}"
    layer_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.layer_type == "combo",
            ConfigLayer.layer_key == layer_key,
            ConfigLayer.status == "active",
        ).limit(1)
    )
    layer = layer_res.scalar_one_or_none()
    if layer is None:
        layer = ConfigLayer(
            layer_type="combo",
            layer_key=layer_key,
            version="1",
            status="active",
            created_by=actor,
            updated_by=actor,
        )
        session.add(layer)
        await session.flush()
    return layer


async def _get_or_create_layer(
    session: AsyncSession, scope: str, target: str, actor: str
) -> ConfigLayer:
    if scope == "tool":
        return await _get_or_create_tool_layer(session, target, actor)
    if scope == "language":
        return await _get_or_create_language_layer(session, target, actor)
    if scope == "override":
        return await _get_or_create_combo_layer(session, target, actor)
    raise DatabaseConfigWriteError(f"Unknown scope '{scope}'. Expected: tool, language, override")


async def _get_field(
    session: AsyncSession, schema: ConfigSchema, step_id: str, field_id: str
) -> ConfigField:
    """Find ConfigField by step_key + field key chain."""
    field_path = f"{step_id}.{field_id}"
    res = await session.execute(
        select(ConfigField).where(
            ConfigField.schema_id == schema.id,
            ConfigField.field_path == field_path,
        ).limit(1)
    )
    field = res.scalar_one_or_none()
    if field is None:
        raise FieldNotFoundError(
            f"Field path '{field_path}' not found in active schema"
        )
    return field


async def _next_version_number(
    session: AsyncSession, scope: str, target_key: str
) -> int:
    res = await session.execute(
        select(func.max(ConfigVersion.version_number)).where(
            ConfigVersion.scope == scope,
            ConfigVersion.target_key == target_key,
        )
    )
    max_ver = res.scalar_one_or_none()
    return (max_ver or 0) + 1


async def _write_audit_and_version(
    session: AsyncSession,
    scope: str,
    target_key: str,
    action: str,
    actor: str,
    summary: str,
    before_json: dict[str, Any] | None = None,
    after_json: dict[str, Any] | None = None,
    snapshot_json: dict[str, Any] | None = None,
) -> None:
    """Write audit event and version snapshot in the same session/transaction."""
    now = datetime.now(timezone.utc)

    audit = ConfigAuditEvent(
        actor=actor,
        action=action,
        scope=scope,
        target_key=target_key,
        summary=summary,
        before_json=before_json,
        after_json=after_json,
        created_at=now,
    )
    session.add(audit)

    version_number = await _next_version_number(session, scope, target_key)
    version = ConfigVersion(
        scope=scope,
        target_key=target_key,
        version_number=version_number,
        actor=actor,
        summary=summary,
        data_json=snapshot_json if snapshot_json is not None else after_json,
        created_at=now,
    )
    session.add(version)


# ---------------------------------------------------------------------------
# Write repository
# ---------------------------------------------------------------------------


class DatabaseConfigWriteRepository:
    """Writes config mutations to the database.

    All operations execute within the supplied ``AsyncSession``.  The caller
    is responsible for committing (or rolling back) the transaction.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # ------------------------------------------------------------------
    # Ticket 2 — field metadata update
    # ------------------------------------------------------------------

    async def update_field_metadata(
        self,
        scope: str,
        target: str,
        step_id: str,
        field_id: str,
        changes: dict[str, Any],
        actor: str = "system",
    ) -> None:
        """Create or update a ConfigFieldMetadataOverride.

        ``changes`` may contain any subset of:
        ``default``, ``editability``, ``required``, ``hidden``, ``lock_reason``.
        """
        session = self._session
        schema = await _get_active_schema(session)
        layer = await _get_or_create_layer(session, scope, target, actor)
        field = await _get_field(session, schema, step_id, field_id)

        res = await session.execute(
            select(ConfigFieldMetadataOverride).where(
                ConfigFieldMetadataOverride.layer_id == layer.id,
                ConfigFieldMetadataOverride.field_id == field.id,
            ).limit(1)
        )
        override = res.scalar_one_or_none()

        before_json: dict[str, Any] | None = None
        if override is not None:
            before_json = {
                "default_value_json": override.default_value_json,
                "editability": override.editability,
                "required": override.required,
                "hidden": override.hidden,
                "lock_reason": override.lock_reason,
            }

        if override is None:
            override = ConfigFieldMetadataOverride(
                layer_id=layer.id,
                field_id=field.id,
                created_by=actor,
                updated_by=actor,
            )
            session.add(override)
        else:
            override.updated_by = actor

        valid_keys = {"default", "editability", "required", "hidden", "lock_reason"}
        for key, value in changes.items():
            if key not in valid_keys:
                raise DatabaseConfigWriteError(
                    f"Unknown metadata field: '{key}'. "
                    f"Allowed: {', '.join(sorted(valid_keys))}"
                )
            if key == "default":
                override.default_value_json = value
            elif key == "editability":
                override.editability = value
            elif key == "required":
                override.required = value
            elif key == "hidden":
                override.hidden = value
            elif key == "lock_reason":
                override.lock_reason = value

        await session.flush()

        after_json: dict[str, Any] = {
            "default_value_json": override.default_value_json,
            "editability": override.editability,
            "required": override.required,
            "hidden": override.hidden,
            "lock_reason": override.lock_reason,
        }

        field_path = f"{step_id}.{field_id}"
        await _write_audit_and_version(
            session,
            scope=scope,
            target_key=target,
            action="update",
            actor=actor,
            summary=f"field '{field_path}': metadata updated",
            before_json=before_json,
            after_json=after_json,
        )

    # ------------------------------------------------------------------
    # Ticket 3 — field reset
    # ------------------------------------------------------------------

    async def reset_field_override(
        self,
        scope: str,
        target: str,
        step_id: str,
        field_id: str,
        override_type: str = "metadata",
        actor: str = "system",
    ) -> None:
        """Remove metadata and/or content overrides for a field.

        ``override_type="metadata"`` removes only the metadata override.
        ``override_type="structure"`` removes both metadata and content overrides.
        """
        session = self._session
        schema = await _get_active_schema(session)
        layer = await _get_or_create_layer(session, scope, target, actor)
        field = await _get_field(session, schema, step_id, field_id)

        field_path = f"{step_id}.{field_id}"

        # Always remove metadata override on reset
        meta_res = await session.execute(
            select(ConfigFieldMetadataOverride).where(
                ConfigFieldMetadataOverride.layer_id == layer.id,
                ConfigFieldMetadataOverride.field_id == field.id,
            ).limit(1)
        )
        meta_override = meta_res.scalar_one_or_none()
        if meta_override is not None:
            await session.delete(meta_override)

        if override_type == "structure":
            content_res = await session.execute(
                select(ConfigFieldContentOverride).where(
                    ConfigFieldContentOverride.layer_id == layer.id,
                    ConfigFieldContentOverride.field_id == field.id,
                ).limit(1)
            )
            content_override = content_res.scalar_one_or_none()
            if content_override is not None:
                await session.delete(content_override)

        await session.flush()

        await _write_audit_and_version(
            session,
            scope=scope,
            target_key=target,
            action="reset",
            actor=actor,
            summary=f"field '{field_path}': {override_type} override removed",
        )

    # ------------------------------------------------------------------
    # Ticket 4 — add preset
    # ------------------------------------------------------------------

    async def add_preset(
        self,
        scope: str,
        target: str,
        step_id: str,
        field_id: str,
        preset: dict[str, Any],
        position: int | None = None,
        actor: str = "system",
    ) -> None:
        """Add a preset to a field's content override (merge_presets_json).

        Presets are stored as a JSON array inside ConfigFieldContentOverride.
        Duplicate labels are replaced by the incoming preset.
        """
        session = self._session
        schema = await _get_active_schema(session)
        layer = await _get_or_create_layer(session, scope, target, actor)
        field = await _get_field(session, schema, step_id, field_id)

        res = await session.execute(
            select(ConfigFieldContentOverride).where(
                ConfigFieldContentOverride.layer_id == layer.id,
                ConfigFieldContentOverride.field_id == field.id,
            ).limit(1)
        )
        override = res.scalar_one_or_none()

        if override is None:
            override = ConfigFieldContentOverride(
                layer_id=layer.id,
                field_id=field.id,
                merge_mode="append",
                created_by=actor,
                updated_by=actor,
            )
            session.add(override)
        else:
            override.updated_by = actor

        existing: list[dict[str, Any]] = list(override.merge_presets_json or [])
        label = preset.get("label", "")
        # Replace any duplicate label
        existing = [p for p in existing if p.get("label") != label]

        if position is not None:
            existing.insert(position, preset)
        else:
            existing.append(preset)

        override.merge_presets_json = existing
        await session.flush()

        field_path = f"{step_id}.{field_id}"
        await _write_audit_and_version(
            session,
            scope=scope,
            target_key=target,
            action="add_preset",
            actor=actor,
            summary=f"field '{field_path}': preset '{label}' added",
            after_json={"merge_presets_json": existing},
        )

    # ------------------------------------------------------------------
    # Ticket 5 — remove preset
    # ------------------------------------------------------------------

    async def remove_preset(
        self,
        scope: str,
        target: str,
        step_id: str,
        field_id: str,
        preset_label: str | None = None,
        position: int | None = None,
        actor: str = "system",
    ) -> None:
        """Remove a preset from a field's content override.

        Identification: ``preset_label`` takes precedence over ``position``.
        If the content override becomes empty after removal, the row is deleted.
        """
        session = self._session
        schema = await _get_active_schema(session)
        layer = await _get_or_create_layer(session, scope, target, actor)
        field = await _get_field(session, schema, step_id, field_id)

        res = await session.execute(
            select(ConfigFieldContentOverride).where(
                ConfigFieldContentOverride.layer_id == layer.id,
                ConfigFieldContentOverride.field_id == field.id,
            ).limit(1)
        )
        override = res.scalar_one_or_none()

        field_path = f"{step_id}.{field_id}"

        if override is None:
            # Nothing to remove — not an error
            await _write_audit_and_version(
                session,
                scope=scope,
                target_key=target,
                action="remove_preset",
                actor=actor,
                summary=f"field '{field_path}': no preset to remove (override not found)",
            )
            return

        existing: list[dict[str, Any]] = list(override.merge_presets_json or [])
        removed_label = preset_label or ""

        if preset_label is not None:
            existing = [p for p in existing if p.get("label") != preset_label]
        elif position is not None:
            if 0 <= position < len(existing):
                removed_label = existing[position].get("label", "")
                existing.pop(position)

        if not existing:
            await session.delete(override)
        else:
            override.merge_presets_json = existing
            override.updated_by = actor

        await session.flush()

        await _write_audit_and_version(
            session,
            scope=scope,
            target_key=target,
            action="remove_preset",
            actor=actor,
            summary=f"field '{field_path}': preset '{removed_label}' removed",
        )

    # ------------------------------------------------------------------
    # Ticket 6 — create language
    # ------------------------------------------------------------------

    async def create_language(
        self,
        language_key: str,
        title: str,
        description: str = "",
        actor: str = "system",
    ) -> Language:
        """Insert a Language record and create an active language layer.

        Raises ``DatabaseConfigWriteError`` for:
        - invalid language key (must match ``[a-z][a-z0-9_-]*``)
        - duplicate language key
        """
        session = self._session

        if not re.match(r"^[a-z][a-z0-9_-]*$", language_key):
            raise DatabaseConfigWriteError(
                f"Invalid language key '{language_key}'. "
                "Must start with a lowercase letter and contain only lowercase "
                "letters, digits, hyphens, or underscores."
            )

        dup_res = await session.execute(
            select(Language).where(Language.language_key == language_key).limit(1)
        )
        if dup_res.scalar_one_or_none() is not None:
            raise DatabaseConfigWriteError(
                f"Language '{language_key}' already exists in the database"
            )

        lang = Language(
            language_key=language_key,
            title=title,
            description=description,
            is_active=True,
            created_by=actor,
            updated_by=actor,
        )
        session.add(lang)
        await session.flush()

        layer = ConfigLayer(
            layer_type="language",
            layer_key=f"language:{language_key}",
            language_id=lang.id,
            version="1",
            status="active",
            metadata_json={"title": title, "description": description},
            applies_to_json=None,
            created_by=actor,
            updated_by=actor,
        )
        session.add(layer)
        await session.flush()

        await _write_audit_and_version(
            session,
            scope="language",
            target_key=language_key,
            action="create",
            actor=actor,
            summary=f"language '{language_key}' created",
            after_json={
                "language_key": language_key,
                "title": title,
                "description": description,
            },
        )

        return lang

    # ------------------------------------------------------------------
    # Ticket 10 — restore version snapshot
    # ------------------------------------------------------------------

    async def restore_version(
        self,
        scope: str,
        target: str,
        version_number: int,
        actor: str = "system",
    ) -> dict[str, Any]:
        """Restore a previous version snapshot to the current database layer.

        Loads the requested ConfigVersion, applies its ``data_json`` back to
        the relevant ConfigLayer, then writes restore audit and version records.

        Returns the restored data_json dict.
        """
        session = self._session

        # Load requested version
        ver_res = await session.execute(
            select(ConfigVersion).where(
                ConfigVersion.scope == scope,
                ConfigVersion.target_key == target,
                ConfigVersion.version_number == version_number,
            ).limit(1)
        )
        version = ver_res.scalar_one_or_none()
        if version is None:
            raise DatabaseConfigWriteError(
                f"Version {version_number} not found for {scope}:{target}"
            )

        snapshot = version.data_json or {}

        # Write restore audit + new version record
        await _write_audit_and_version(
            session,
            scope=scope,
            target_key=target,
            action="restore",
            actor=actor,
            summary=f"restored to version {version_number}",
            snapshot_json=snapshot,
        )

        return snapshot
