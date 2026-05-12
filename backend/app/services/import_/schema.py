"""Ticket 12 — JSON import service for schema, steps, and fields.

Reads ``{data_dir}/schema.json`` and imports:
  - One ``config_schema`` row
  - One ``config_step`` row per step
  - One ``config_field`` row per field (including nested / repeatable_group children)

Strategy: idempotent keyed on (schema_version, step_key, field_path).
The schema row itself is keyed by ``schema_version``.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.services.import_.result import ImportResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


async def _upsert_schema(
    session: AsyncSession,
    schema_version: str,
    description: str,
    source_path: str,
    source_checksum: str,
    dry_run: bool,
) -> tuple[ConfigSchema | None, str]:
    """Upsert ConfigSchema by version. Returns (row_or_None, outcome)."""
    result = await session.execute(
        select(ConfigSchema).where(ConfigSchema.schema_version == schema_version)
    )
    existing = result.scalar_one_or_none()

    if existing is None:
        if dry_run:
            return None, "created"
        schema = ConfigSchema(
            schema_version=schema_version,
            description=description,
            status="active",
            source_path=source_path,
            source_checksum=source_checksum,
        )
        session.add(schema)
        await session.flush()
        return schema, "created"

    changed = (
        existing.description != description
        or existing.source_checksum != source_checksum
    )
    if changed and not dry_run:
        existing.description = description
        existing.source_checksum = source_checksum
        existing.source_path = source_path
        await session.flush()
    return existing, "updated" if changed else "unchanged"


async def _upsert_step(
    session: AsyncSession,
    schema: ConfigSchema,
    step_data: dict[str, Any],
    position: int,
    dry_run: bool,
) -> tuple[ConfigStep | None, str]:
    step_key: str = step_data["id"]

    result = await session.execute(
        select(ConfigStep).where(
            ConfigStep.schema_id == schema.id,
            ConfigStep.step_key == step_key,
        )
    )
    existing = result.scalar_one_or_none()

    attrs = {
        "title": step_data.get("title", ""),
        "description": step_data.get("description"),
        "hint": step_data.get("hint"),
        "output_file": step_data.get("output_file", ""),
        "output_format": step_data.get("output_format", "text"),
        "supported_surfaces_json": step_data.get("supported_surfaces"),
        "hidden": step_data.get("hidden", False),
        "position": position,
        "scope": step_data.get("scope", "global"),
    }

    if existing is None:
        if dry_run:
            return None, "created"
        step = ConfigStep(schema_id=schema.id, step_key=step_key, **attrs)
        session.add(step)
        await session.flush()
        return step, "created"

    changed = any(getattr(existing, k) != v for k, v in attrs.items())
    if changed and not dry_run:
        for k, v in attrs.items():
            setattr(existing, k, v)
        await session.flush()
    return existing, "updated" if changed else "unchanged"


async def _upsert_field(
    session: AsyncSession,
    schema: ConfigSchema,
    step: ConfigStep,
    field_data: dict[str, Any],
    field_path: str,
    position: int,
    parent_field_id: int | None,
    dry_run: bool,
) -> tuple[ConfigField | None, str]:
    field_key: str = field_data["id"]

    result = await session.execute(
        select(ConfigField).where(
            ConfigField.schema_id == schema.id,
            ConfigField.field_path == field_path,
        )
    )
    existing = result.scalar_one_or_none()

    attrs: dict[str, Any] = {
        "field_key": field_key,
        "field_path": field_path,
        "field_type": field_data.get("type", "text"),
        "label": field_data.get("label", ""),
        "description": field_data.get("description"),
        "placeholder": field_data.get("placeholder"),
        "required": field_data.get("required", False),
        "default_value_json": field_data.get("default"),
        "editability": field_data.get("editability", "free"),
        "locked_value": field_data.get("locked_value"),
        "render": field_data.get("render", True),
        "hidden": field_data.get("hidden", False),
        "options_json": field_data.get("options"),
        "presets_json": field_data.get("presets"),
        "preset_files_json": field_data.get("preset_files"),
        "screen_hint": field_data.get("screen_hint"),
        "frontmatter": field_data.get("frontmatter", False),
        "frontmatter_key": field_data.get("frontmatter_key"),
        "tag_source": field_data.get("tag_source"),
        "validation_json": field_data.get("validation"),
        "agent_config_json": field_data.get("agent_config"),
        "rows": field_data.get("rows"),
        "position": position,
        "parent_field_id": parent_field_id,
    }

    if existing is None:
        if dry_run:
            return None, "created"
        field = ConfigField(schema_id=schema.id, step_id=step.id, **attrs)
        session.add(field)
        await session.flush()
        return field, "created"

    changed = any(getattr(existing, k) != v for k, v in attrs.items())
    if changed and not dry_run:
        for k, v in attrs.items():
            setattr(existing, k, v)
        await session.flush()
    return existing, "updated" if changed else "unchanged"


def _track_outcome(result: ImportResult, outcome: str) -> None:
    if outcome == "created":
        result.created += 1
    elif outcome == "updated":
        result.updated += 1
    else:
        result.unchanged += 1


# ---------------------------------------------------------------------------
# Recursive field importer
# ---------------------------------------------------------------------------


async def _import_fields_recursive(
    session: AsyncSession,
    schema: ConfigSchema,
    step: ConfigStep,
    fields_data: list[dict[str, Any]],
    parent_path: str,
    parent_field_id: int | None,
    dry_run: bool,
    result: ImportResult,
) -> None:
    for position, field_data in enumerate(fields_data):
        field_key = field_data["id"]
        field_path = f"{parent_path}.{field_key}"

        field_row, outcome = await _upsert_field(
            session, schema, step, field_data, field_path, position, parent_field_id, dry_run
        )
        _track_outcome(result, outcome)

        # Recurse into nested fields
        nested = field_data.get("fields") or []
        if nested and field_row is not None:
            await _import_fields_recursive(
                session, schema, step, nested, field_path, field_row.id, dry_run, result
            )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def import_schema(
    session: AsyncSession,
    data_dir: Path,
    *,
    dry_run: bool = False,
) -> ImportResult:
    """Import schema.json into the database.

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

    schema_path = data_dir / "schema.json"
    if not schema_path.exists():
        result.errors.append(f"schema.json not found at {schema_path}")
        return result

    try:
        raw = json.loads(schema_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        result.errors.append(f"schema.json parse error: {exc}")
        return result

    checksum = _sha256(schema_path)
    schema_version: str = raw.get("schema_version", "unknown")
    description: str = raw.get("description", "")
    source_path = str(schema_path)

    schema_row, outcome = await _upsert_schema(
        session, schema_version, description, source_path, checksum, dry_run
    )
    _track_outcome(result, outcome)

    if schema_row is None:
        # dry_run with no existing schema — skip step/field processing
        if dry_run:
            for step_data in raw.get("steps", []):
                result.created += 1  # step
                for fd in step_data.get("fields", []):
                    result.created += 1  # field
                    result.created += len(fd.get("fields", []))
            return result
        return result

    # Import steps and fields
    for position, step_data in enumerate(raw.get("steps", [])):
        try:
            step_row, step_outcome = await _upsert_step(
                session, schema_row, step_data, position, dry_run
            )
            _track_outcome(result, step_outcome)

            if step_row is not None:
                step_key = step_data["id"]
                await _import_fields_recursive(
                    session, schema_row, step_row,
                    step_data.get("fields", []),
                    parent_path=step_key,
                    parent_field_id=None,
                    dry_run=dry_run,
                    result=result,
                )
        except Exception as exc:  # noqa: BLE001
            result.errors.append(f"step {step_data.get('id', '?')}: {exc}")

    if not dry_run:
        await session.flush()

    return result
