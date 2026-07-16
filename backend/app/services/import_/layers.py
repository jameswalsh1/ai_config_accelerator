"""Tickets 13–15 — JSON import service for tool, language, and combo layers.

Reads:
  - ``{data_dir}/tools/{tool_id}.json``        → tool layer + overrides
  - ``{data_dir}/languages/{language_id}.json`` → language layer + overrides
  - (Future) combo override files               → combo layers

All override records resolve ``step_key`` → ``config_step.id`` and
``field_path`` → ``config_field.id`` using the already-imported schema.
A clear error is recorded if a referenced step or field does not exist in the DB.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.language import Language
from app.db.models.layer import (
    ConfigFieldContentOverride,
    ConfigFieldMetadataOverride,
    ConfigLayer,
    ConfigStepOverride,
)
from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.db.models.tool import AITool
from app.services.import_.result import ImportResult


# ---------------------------------------------------------------------------
# Lookup helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _track_outcome(result: ImportResult, outcome: str) -> None:
    if outcome == "created":
        result.created += 1
    elif outcome == "updated":
        result.updated += 1
    else:
        result.unchanged += 1


async def _load_schema(session: AsyncSession) -> ConfigSchema | None:
    """Return the first active ConfigSchema (there should be exactly one)."""
    res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    return res.scalar_one_or_none()


async def _build_step_index(
    session: AsyncSession, schema: ConfigSchema
) -> dict[str, int]:
    """Return mapping step_key → config_step.id for the given schema."""
    result = await session.execute(
        select(ConfigStep.step_key, ConfigStep.id).where(ConfigStep.schema_id == schema.id)
    )
    return {row.step_key: row.id for row in result}


async def _build_field_index(
    session: AsyncSession, schema: ConfigSchema
) -> dict[str, int]:
    """Return mapping field_path → config_field.id for the given schema."""
    result = await session.execute(
        select(ConfigField.field_path, ConfigField.id).where(ConfigField.schema_id == schema.id)
    )
    return {row.field_path: row.id for row in result}


# ---------------------------------------------------------------------------
# Layer upsert
# ---------------------------------------------------------------------------


async def _upsert_layer(
    session: AsyncSession,
    layer_type: str,
    layer_key: str,
    version: str,
    tool_id: int | None,
    language_id: int | None,
    metadata_json: Any,
    applies_to_json: Any,
    source_path: str,
    source_checksum: str,
    dry_run: bool,
) -> tuple[ConfigLayer | None, str]:
    res = await session.execute(
        select(ConfigLayer).where(ConfigLayer.layer_key == layer_key)
    )
    existing = res.scalar_one_or_none()

    if existing is None:
        if dry_run:
            return None, "created"
        layer = ConfigLayer(
            layer_type=layer_type,
            layer_key=layer_key,
            version=version,
            tool_id=tool_id,
            language_id=language_id,
            status="active",
            metadata_json=metadata_json,
            applies_to_json=applies_to_json,
            source_path=source_path,
            source_checksum=source_checksum,
        )
        session.add(layer)
        await session.flush()
        return layer, "created"

    changed = existing.source_checksum != source_checksum
    if changed and not dry_run:
        existing.version = version
        existing.metadata_json = metadata_json
        existing.applies_to_json = applies_to_json
        existing.source_path = source_path
        existing.source_checksum = source_checksum
        await session.flush()
    return existing, "updated" if changed else "unchanged"


# ---------------------------------------------------------------------------
# Override importers
# ---------------------------------------------------------------------------


async def _import_step_overrides(
    session: AsyncSession,
    layer: ConfigLayer,
    step_overrides: list[dict[str, Any]],
    step_index: dict[str, int],
    dry_run: bool,
    result: ImportResult,
) -> None:
    for so in step_overrides:
        step_key: str = so.get("step_id", "")
        step_db_id = step_index.get(step_key)
        if step_db_id is None:
            result.errors.append(f"step_override: step '{step_key}' not found in schema")
            continue

        if dry_run:
            result.created += 1
            continue

        res = await session.execute(
            select(ConfigStepOverride).where(
                ConfigStepOverride.layer_id == layer.id,
                ConfigStepOverride.step_id == step_db_id,
            )
        )
        existing = res.scalar_one_or_none()

        attrs: dict[str, Any] = {
            "hidden": so.get("hidden"),
            "title_override": so.get("title"),
            "description_override": so.get("description"),
            "hint_override": so.get("hint"),
        }

        if existing is None:
            session.add(ConfigStepOverride(layer_id=layer.id, step_id=step_db_id, **attrs))
            result.created += 1
        else:
            changed = any(getattr(existing, k) != v for k, v in attrs.items())
            if changed:
                for k, v in attrs.items():
                    setattr(existing, k, v)
                result.updated += 1
            else:
                result.unchanged += 1


async def _import_field_metadata_overrides(
    session: AsyncSession,
    layer: ConfigLayer,
    metadata_overrides: list[dict[str, Any]],
    field_index: dict[str, int],
    dry_run: bool,
    result: ImportResult,
) -> None:
    for mo in metadata_overrides:
        field_path: str = mo.get("field_id", "")
        field_db_id = field_index.get(field_path)
        if field_db_id is None:
            result.errors.append(
                f"metadata_override: field '{field_path}' not found in schema"
            )
            continue

        if dry_run:
            result.created += 1
            continue

        res = await session.execute(
            select(ConfigFieldMetadataOverride).where(
                ConfigFieldMetadataOverride.layer_id == layer.id,
                ConfigFieldMetadataOverride.field_id == field_db_id,
            )
        )
        existing = res.scalar_one_or_none()

        attrs: dict[str, Any] = {
            "default_value_json": mo.get("default"),
            "editability": mo.get("editability"),
            "required": mo.get("required"),
            "hidden": mo.get("hidden"),
            "lock_reason": mo.get("lock_reason"),
        }

        if existing is None:
            session.add(
                ConfigFieldMetadataOverride(layer_id=layer.id, field_id=field_db_id, **attrs)
            )
            result.created += 1
        else:
            changed = any(getattr(existing, k) != v for k, v in attrs.items())
            if changed:
                for k, v in attrs.items():
                    setattr(existing, k, v)
                result.updated += 1
            else:
                result.unchanged += 1


async def _import_field_content_overrides(
    session: AsyncSession,
    layer: ConfigLayer,
    field_overrides: list[dict[str, Any]],
    field_index: dict[str, int],
    dry_run: bool,
    result: ImportResult,
) -> None:
    for fo in field_overrides:
        field_path: str = fo.get("field_id", "")
        field_db_id = field_index.get(field_path)
        if field_db_id is None:
            result.errors.append(
                f"field_override: field '{field_path}' not found in schema"
            )
            continue

        if dry_run:
            result.created += 1
            continue

        res = await session.execute(
            select(ConfigFieldContentOverride).where(
                ConfigFieldContentOverride.layer_id == layer.id,
                ConfigFieldContentOverride.field_id == field_db_id,
            )
        )
        existing = res.scalar_one_or_none()

        attrs: dict[str, Any] = {
            "replace_options_with_json": fo.get("replace_options"),
            "merge_options_json": fo.get("merge_options"),
            "replace_presets_with_json": fo.get("replace_presets"),
            "merge_presets_json": fo.get("merge_presets"),
            "preset_files_to_add_json": fo.get("preset_files"),
            "merge_mode": fo.get("merge_mode", "append"),
        }

        if existing is None:
            session.add(
                ConfigFieldContentOverride(layer_id=layer.id, field_id=field_db_id, **attrs)
            )
            result.created += 1
        else:
            changed = any(getattr(existing, k) != v for k, v in attrs.items())
            if changed:
                for k, v in attrs.items():
                    setattr(existing, k, v)
                result.updated += 1
            else:
                result.unchanged += 1


# ---------------------------------------------------------------------------
# Tool layer import (Ticket 13)
# ---------------------------------------------------------------------------


async def _import_tool_layer(
    session: AsyncSession,
    json_path: Path,
    step_index: dict[str, int],
    field_index: dict[str, int],
    dry_run: bool,
    result: ImportResult,
) -> None:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    tool_key: str = raw["tool_id"]
    checksum = _sha256(json_path)

    # Resolve AITool DB id
    res = await session.execute(select(AITool).where(AITool.tool_key == tool_key))
    tool_row = res.scalar_one_or_none()
    if tool_row is None:
        result.errors.append(f"tool '{tool_key}' not found — run import_tools first")
        result.skipped += 1
        return

    layer_key = f"tool:{tool_key}"
    version: str = str(raw.get("version", "1"))
    metadata_json = raw.get("tool_metadata")
    applies_to_json = raw.get("applies_to")

    layer_row, outcome = await _upsert_layer(
        session,
        layer_type="tool",
        layer_key=layer_key,
        version=version,
        tool_id=tool_row.id,
        language_id=None,
        metadata_json=metadata_json,
        applies_to_json=applies_to_json,
        source_path=str(json_path),
        source_checksum=checksum,
        dry_run=dry_run,
    )
    _track_outcome(result, outcome)

    if layer_row is None:
        return

    await _import_step_overrides(
        session, layer_row, raw.get("step_overrides", []), step_index, dry_run, result
    )
    await _import_field_metadata_overrides(
        session, layer_row, raw.get("metadata_overrides", []), field_index, dry_run, result
    )
    await _import_field_content_overrides(
        session, layer_row, raw.get("field_overrides", []), field_index, dry_run, result
    )


# ---------------------------------------------------------------------------
# Language layer import (Ticket 14)
# ---------------------------------------------------------------------------


async def _import_language_layer(
    session: AsyncSession,
    json_path: Path,
    step_index: dict[str, int],
    field_index: dict[str, int],
    dry_run: bool,
    result: ImportResult,
) -> None:
    raw = json.loads(json_path.read_text(encoding="utf-8"))
    lang_key: str = raw["language_id"]
    checksum = _sha256(json_path)

    # Resolve Language DB id
    res = await session.execute(select(Language).where(Language.language_key == lang_key))
    lang_row = res.scalar_one_or_none()
    if lang_row is None:
        result.errors.append(f"language '{lang_key}' not found — run import_languages first")
        result.skipped += 1
        return

    layer_key = f"language:{lang_key}"
    version: str = str(raw.get("version", "1"))
    metadata_json = raw.get("metadata")
    applies_to_json = raw.get("applies_to")

    layer_row, outcome = await _upsert_layer(
        session,
        layer_type="language",
        layer_key=layer_key,
        version=version,
        tool_id=None,
        language_id=lang_row.id,
        metadata_json=metadata_json,
        applies_to_json=applies_to_json,
        source_path=str(json_path),
        source_checksum=checksum,
        dry_run=dry_run,
    )
    _track_outcome(result, outcome)

    if layer_row is None:
        return

    await _import_step_overrides(
        session, layer_row, raw.get("step_overrides", []), step_index, dry_run, result
    )
    await _import_field_metadata_overrides(
        session, layer_row, raw.get("metadata_overrides", []), field_index, dry_run, result
    )
    await _import_field_content_overrides(
        session, layer_row, raw.get("field_overrides", []), field_index, dry_run, result
    )


# ---------------------------------------------------------------------------
# Public entry point (Tickets 13–15)
# ---------------------------------------------------------------------------


async def import_layers(
    session: AsyncSession,
    data_dir: Path,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Import all layer JSON files (tool, language, combo) from *data_dir*.

    Requires that tools/languages and the schema are already imported.

    Parameters
    ----------
    session:
        Async SQLAlchemy session.
    data_dir:
        Root wizard config directory.
    dry_run:
        When ``True``, compute what would change but do not write to the DB.
    """
    result = ImportResult()

    schema = await _load_schema(session)
    if schema is None:
        result.errors.append("No active ConfigSchema found — run import_schema first")
        return result

    step_index = await _build_step_index(session, schema)
    field_index = await _build_field_index(session, schema)

    # --- Tool layers (Ticket 13) ---
    tools_dir = data_dir / "tools"
    if tools_dir.is_dir():
        for json_file in sorted(tools_dir.glob("*.json")):
            try:
                await _import_tool_layer(
                    session, json_file, step_index, field_index, dry_run, result
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"tools/{json_file.name}: {exc}")

    # --- Language layers (Ticket 14) ---
    langs_dir = data_dir / "languages"
    if langs_dir.is_dir():
        for json_file in sorted(langs_dir.glob("*.json")):
            try:
                await _import_language_layer(
                    session, json_file, step_index, field_index, dry_run, result
                )
            except Exception as exc:  # noqa: BLE001
                result.errors.append(f"languages/{json_file.name}: {exc}")

    # --- Combo layers (Ticket 15) ---
    # No combo override files exist yet. Placeholder for future expansion.
    # When combo files exist they can be read from data_dir / "overrides" / "combos"

    if not dry_run:
        await session.flush()

    return result
