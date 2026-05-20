"""Ticket 17 — Database-backed config read repository.

Implements the ``ConfigReadRepository`` protocol (defined in
``config_repository.py``) using SQLAlchemy async sessions and the
ORM models introduced in Phase 2.

The resolver logic follows the same composition order as the JSON resolver:
  1. Base schema fields
  2. Tool layer overrides (metadata + content)
  3. Language layer overrides
  4. (Future) Combo layer overrides

Override attribution is tracked via ``override_source``.
"""
from __future__ import annotations

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
from app.services.config_db_serialiser import (
    apply_field_content_override_to_dict,
    apply_field_metadata_override_to_dict,
    apply_step_overrides_to_dict,
    schema_to_config_dict,
    step_to_dict,
    _build_field_tree,
    field_to_dict,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


async def _get_active_schema(session: AsyncSession) -> ConfigSchema | None:
    res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    return res.scalar_one_or_none()


async def _get_steps(session: AsyncSession, schema: ConfigSchema) -> list[ConfigStep]:
    res = await session.execute(
        select(ConfigStep)
        .where(ConfigStep.schema_id == schema.id)
        .order_by(ConfigStep.position)
    )
    return list(res.scalars().all())


async def _get_fields_for_step(
    session: AsyncSession, schema: ConfigSchema, step: ConfigStep
) -> list[ConfigField]:
    res = await session.execute(
        select(ConfigField)
        .where(ConfigField.schema_id == schema.id, ConfigField.step_id == step.id)
        .order_by(ConfigField.position)
    )
    return list(res.scalars().all())


async def _get_layer(
    session: AsyncSession,
    layer_type: str,
    tool_id: int | None = None,
    language_id: int | None = None,
) -> ConfigLayer | None:
    stmt = select(ConfigLayer).where(
        ConfigLayer.layer_type == layer_type,
        ConfigLayer.status == "active",
    )
    if tool_id is not None:
        stmt = stmt.where(ConfigLayer.tool_id == tool_id)
    if language_id is not None:
        stmt = stmt.where(ConfigLayer.language_id == language_id)
    res = await session.execute(stmt.limit(1))
    return res.scalar_one_or_none()


async def _get_step_overrides(
    session: AsyncSession, layer: ConfigLayer
) -> list[ConfigStepOverride]:
    res = await session.execute(
        select(ConfigStepOverride).where(ConfigStepOverride.layer_id == layer.id)
    )
    return list(res.scalars().all())


async def _get_field_metadata_overrides(
    session: AsyncSession, layer: ConfigLayer
) -> dict[int, ConfigFieldMetadataOverride]:
    """Return mapping field_id → ConfigFieldMetadataOverride."""
    res = await session.execute(
        select(ConfigFieldMetadataOverride).where(
            ConfigFieldMetadataOverride.layer_id == layer.id
        )
    )
    return {row.field_id: row for row in res.scalars().all()}


async def _get_field_content_overrides(
    session: AsyncSession, layer: ConfigLayer
) -> dict[int, ConfigFieldContentOverride]:
    """Return mapping field_id → ConfigFieldContentOverride."""
    res = await session.execute(
        select(ConfigFieldContentOverride).where(
            ConfigFieldContentOverride.layer_id == layer.id
        )
    )
    return {row.field_id: row for row in res.scalars().all()}


def _override_source_label(layer: ConfigLayer) -> str:
    if layer.layer_type == "tool":
        return f"tool:{layer.layer_key.split(':', 1)[-1]}"
    if layer.layer_type == "language":
        return f"language:{layer.layer_key.split(':', 1)[-1]}"
    return layer.layer_key


def _apply_overrides_to_field(
    field_dict: dict[str, Any],
    field_db_id: int,
    metadata_overrides: dict[int, ConfigFieldMetadataOverride],
    content_overrides: dict[int, ConfigFieldContentOverride],
    source: str,
) -> dict[str, Any]:
    result = field_dict
    if field_db_id in metadata_overrides:
        mo = metadata_overrides[field_db_id]
        result = apply_field_metadata_override_to_dict(
            result,
            {
                "default_value_json": mo.default_value_json,
                "editability": mo.editability,
                "required": mo.required,
                "hidden": mo.hidden,
                "lock_reason": mo.lock_reason,
            },
            source,
        )
    if field_db_id in content_overrides:
        co = content_overrides[field_db_id]
        result = apply_field_content_override_to_dict(
            result,
            {
                "replace_options_with_json": co.replace_options_with_json,
                "merge_options_json": co.merge_options_json,
                "replace_presets_with_json": co.replace_presets_with_json,
                "merge_presets_json": co.merge_presets_json,
                "preset_files_to_add_json": co.preset_files_to_add_json,
                "merge_mode": co.merge_mode,
            },
            source,
        )
    return result


def _apply_overrides_to_field_tree(
    all_fields: list[ConfigField],
    parent_id: int | None,
    metadata_overrides: dict[int, ConfigFieldMetadataOverride],
    content_overrides: dict[int, ConfigFieldContentOverride],
    source: str,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for field in all_fields:
        if field.parent_field_id == parent_id:
            children = _apply_overrides_to_field_tree(
                all_fields, field.id, metadata_overrides, content_overrides, source
            )
            fd = field_to_dict(field, children or None)
            fd = _apply_overrides_to_field(
                fd, field.id, metadata_overrides, content_overrides, source
            )
            result.append(fd)
    return result


# ---------------------------------------------------------------------------
# Database config read repository
# ---------------------------------------------------------------------------


class DatabaseConfigReadRepository:
    """Reads fully resolved wizard configuration from the database.

    Implements the ``ConfigReadRepository`` protocol.

    Parameters
    ----------
    session:
        An open AsyncSession.  The caller must manage the session lifecycle.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load_resolved_config(
        self, tool_id: str, language_id: str
    ) -> dict[str, Any]:
        """Return a fully resolved wizard config dict for the given tool+language.

        Applies overrides in order: base schema → tool layer → language layer.
        """
        session = self._session
        schema = await _get_active_schema(session)
        if schema is None:
            raise RuntimeError("No active config schema found in database")

        steps = await _get_steps(session, schema)

        # Resolve tool and language DB ids
        tool_res = await session.execute(
            select(AITool).where(AITool.tool_key == tool_id)
        )
        tool_row = tool_res.scalar_one_or_none()
        lang_res = await session.execute(
            select(Language).where(Language.language_key == language_id)
        )
        lang_row = lang_res.scalar_one_or_none()

        tool_layer = (
            await _get_layer(session, "tool", tool_id=tool_row.id)
            if tool_row
            else None
        )
        lang_layer = (
            await _get_layer(session, "language", language_id=lang_row.id)
            if lang_row
            else None
        )

        # Build step override sets per layer
        tool_step_overrides: dict[int, ConfigStepOverride] = {}
        lang_step_overrides: dict[int, ConfigStepOverride] = {}
        tool_meta_overrides: dict[int, ConfigFieldMetadataOverride] = {}
        tool_content_overrides: dict[int, ConfigFieldContentOverride] = {}
        lang_meta_overrides: dict[int, ConfigFieldMetadataOverride] = {}
        lang_content_overrides: dict[int, ConfigFieldContentOverride] = {}

        if tool_layer:
            tool_so = await _get_step_overrides(session, tool_layer)
            tool_step_overrides = {so.step_id: so for so in tool_so}
            tool_meta_overrides = await _get_field_metadata_overrides(session, tool_layer)
            tool_content_overrides = await _get_field_content_overrides(session, tool_layer)

        if lang_layer:
            lang_so = await _get_step_overrides(session, lang_layer)
            lang_step_overrides = {so.step_id: so for so in lang_so}
            lang_meta_overrides = await _get_field_metadata_overrides(session, lang_layer)
            lang_content_overrides = await _get_field_content_overrides(session, lang_layer)

        # Serialise each step with overrides applied
        serialised_steps: list[dict[str, Any]] = []
        for step in steps:
            all_fields = await _get_fields_for_step(session, schema, step)

            # Build field tree with tool overrides applied
            tool_source = _override_source_label(tool_layer) if tool_layer else ""
            lang_source = _override_source_label(lang_layer) if lang_layer else ""

            fields: list[dict[str, Any]]
            if tool_layer:
                fields = _apply_overrides_to_field_tree(
                    all_fields, None, tool_meta_overrides, tool_content_overrides, tool_source
                )
            else:
                fields = _build_field_tree(all_fields, None)

            # Apply language overrides on top
            if lang_layer:
                fields = _apply_lang_overrides_to_fields(
                    fields, all_fields, lang_meta_overrides, lang_content_overrides, lang_source
                )

            step_dict = step_to_dict(step, all_fields)
            step_dict["fields"] = fields

            # Apply step-level overrides
            step_override_list = []
            if tool_layer and step.id in tool_step_overrides:
                so = tool_step_overrides[step.id]
                step_override_list.append({
                    "hidden": so.hidden,
                    "title_override": so.title_override,
                    "description_override": so.description_override,
                    "hint_override": so.hint_override,
                })
            if lang_layer and step.id in lang_step_overrides:
                so = lang_step_overrides[step.id]
                step_override_list.append({
                    "hidden": so.hidden,
                    "title_override": so.title_override,
                    "description_override": so.description_override,
                    "hint_override": so.hint_override,
                })
            if step_override_list:
                step_dict = apply_step_overrides_to_dict(step_dict, step_override_list)

            serialised_steps.append(step_dict)

        return {
            "schema_version": schema.schema_version,
            "description": schema.description,
            "steps": serialised_steps,
        }

    async def get_available_tools(self) -> list[dict[str, Any]]:
        """Return list of active tools from the database."""
        res = await self._session.execute(
            select(AITool).where(AITool.is_active.is_(True)).order_by(AITool.tool_key)
        )
        return [
            {"id": t.tool_key, "title": t.title, "description": t.description}
            for t in res.scalars().all()
        ]

    async def get_available_languages(self) -> list[dict[str, Any]]:
        """Return list of active languages from the database."""
        res = await self._session.execute(
            select(Language)
            .where(Language.is_active.is_(True))
            .order_by(Language.language_key)
        )
        return [
            {"id": la.language_key, "title": la.title, "description": la.description}
            for la in res.scalars().all()
        ]

    async def get_available_steps(self, tool_id: str, language_id: str) -> list[dict[str, str]]:
        """Return non-hidden steps for a tool+language as id/title/description dicts."""
        resolved = await self.load_resolved_config(tool_id, language_id)
        return [
            {
                "id": step.get("id", ""),
                "title": step.get("title", step.get("id", "")),
                "description": step.get("description", ""),
            }
            for step in resolved.get("steps", [])
            if not step.get("hidden", False)
        ]

    async def get_language_tags(self, language_id: str) -> list[str]:
        """Return sorted unique preset tags for a language layer."""
        lang_res = await self._session.execute(
            select(Language).where(Language.language_key == language_id)
        )
        lang_row = lang_res.scalar_one_or_none()
        if lang_row is None:
            raise ValueError(f"Language '{language_id}' not found")
        lang_layer = await _get_layer(self._session, "language", language_id=lang_row.id)
        if lang_layer is None:
            return []
        overrides = await _get_field_content_overrides(self._session, lang_layer)
        tags: set[str] = set()
        for co in overrides.values():
            for preset in (co.merge_presets_json or []):
                tags.update(preset.get("tags", []))
            for preset in (co.replace_presets_with_json or []):
                tags.update(preset.get("tags", []))
        return sorted(tags)

    async def get_coverage_matrix(self) -> dict[str, Any]:
        """Return the tool × language coverage matrix from the database."""
        tools = await self.get_available_tools()
        languages = await self.get_available_languages()

        schema = await _get_active_schema(self._session)
        if schema is None:
            return {"tools": tools, "languages": languages, "matrix": {}}

        # All non-hidden steps
        all_steps = await _get_steps(self._session, schema)

        # Build matrix
        matrix: dict[str, dict[str, dict[str, Any]]] = {}
        for tool in tools:
            tool_id = tool["id"]
            tool_res = await self._session.execute(
                select(AITool).where(AITool.tool_key == tool_id)
            )
            tool_row = tool_res.scalar_one_or_none()
            tool_layer = await _get_layer(self._session, "tool", tool_id=tool_row.id) if tool_row else None

            # Steps hidden by this tool's layer
            tool_hidden: set[int] = set()
            if tool_layer:
                so_res = await _get_step_overrides(self._session, tool_layer)
                tool_hidden = {s.step_id for s in so_res if s.hidden}

            # Visible step DB ids for this tool
            visible_step_ids = {
                s.id for s in all_steps
                if not s.hidden
                and s.id not in tool_hidden
                and s.step_key != "language_selection"
            }

            matrix[tool_id] = {}
            for lang in languages:
                lang_id = lang["id"]
                lang_res = await self._session.execute(
                    select(Language).where(Language.language_key == lang_id)
                )
                lang_row = lang_res.scalar_one_or_none()
                lang_layer = await _get_layer(self._session, "language", language_id=lang_row.id) if lang_row else None

                if lang_layer is None:
                    matrix[tool_id][lang_id] = {"status": "none", "field_count": 0, "fields": []}
                    continue

                # Count field overrides whose step is visible for this tool
                meta_ov = await _get_field_metadata_overrides(self._session, lang_layer)
                content_ov = await _get_field_content_overrides(self._session, lang_layer)
                all_override_field_ids = set(meta_ov.keys()) | set(content_ov.keys())

                # Resolve field_id → step_id
                if all_override_field_ids:
                    field_res = await self._session.execute(
                        select(ConfigField.id, ConfigField.step_id, ConfigField.field_key)
                        .where(ConfigField.id.in_(all_override_field_ids))
                    )
                    relevant_fields = [
                        f"{row.step_id}.{row.field_key}"
                        for row in field_res
                        if row.step_id in visible_step_ids
                    ]
                else:
                    relevant_fields = []

                count = len(relevant_fields)
                status = "full" if count >= 2 else ("partial" if count == 1 else "none")
                matrix[tool_id][lang_id] = {
                    "status": status,
                    "field_count": count,
                    "fields": relevant_fields,
                }

        return {"tools": tools, "languages": languages, "matrix": matrix}


def _apply_lang_overrides_to_fields(
    fields: list[dict[str, Any]],
    all_fields: list[ConfigField],
    meta_overrides: dict[int, ConfigFieldMetadataOverride],
    content_overrides: dict[int, ConfigFieldContentOverride],
    source: str,
) -> list[dict[str, Any]]:
    """Apply language overrides to an already-serialised field tree.

    Matches fields by field_key against the ORM list to find DB IDs.
    """
    field_key_to_id = {f.field_key: f.id for f in all_fields}
    result: list[dict[str, Any]] = []
    for fd in fields:
        fd = dict(fd)
        field_db_id = field_key_to_id.get(fd.get("id", ""))
        if field_db_id is not None:
            fd = _apply_overrides_to_field(
                fd, field_db_id, meta_overrides, content_overrides, source
            )
        # Recurse into nested fields
        if fd.get("fields"):
            fd["fields"] = _apply_lang_overrides_to_fields(
                fd["fields"], all_fields, meta_overrides, content_overrides, source
            )
        result.append(fd)
    return result
