"""Phase 4 — Tickets 3, 4, 5, 6, 7, 9, 10: Draft layer management service.

Provides:
- create_draft_from_active   (Ticket 3)
- load_draft_preview         (Ticket 5)
- diff_draft_vs_source       (Ticket 6)
- promote_draft              (Ticket 7)
- archive_draft              (Ticket 9)
- list_drafts                (Ticket 10)

Ticket 4 (routing writes to draft layers) is handled in the write
repository and router, not here.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.layer import (
    LAYER_STATUS_VALUES,
    ConfigFieldContentOverride,
    ConfigFieldMetadataOverride,
    ConfigLayer,
    ConfigStepOverride,
)
from app.db.models.schema import ConfigField, ConfigSchema, ConfigStep
from app.db.models.tool import AITool
from app.db.models.language import Language
from app.services.config_layer_lifecycle import (
    ConfigLayerLifecycleService,
    LayerNotFoundError,
    LayerTransitionError,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class DraftServiceError(Exception):
    """Base error for draft service operations."""


class ActiveLayerNotFoundError(DraftServiceError):
    """Raised when no active layer exists for the requested scope/target."""


# ---------------------------------------------------------------------------
# Helper: resolve active layer by scope/target
# ---------------------------------------------------------------------------


async def _resolve_active_layer(
    session: AsyncSession, scope: str, target: str
) -> ConfigLayer:
    """Find the active ConfigLayer for a given scope and target string.

    scope  : tool | language | override (combo)
    target : tool_key | language_key | "tool+language"
    """
    stmt = select(ConfigLayer).where(
        ConfigLayer.status == "active",
    )

    if scope == "tool":
        tool_res = await session.execute(
            select(AITool).where(AITool.tool_key == target).limit(1)
        )
        tool = tool_res.scalar_one_or_none()
        if tool is None:
            raise ActiveLayerNotFoundError(f"Tool '{target}' not found")
        stmt = stmt.where(
            ConfigLayer.layer_type == "tool",
            ConfigLayer.tool_id == tool.id,
        )
    elif scope == "language":
        lang_res = await session.execute(
            select(Language).where(Language.language_key == target).limit(1)
        )
        lang = lang_res.scalar_one_or_none()
        if lang is None:
            raise ActiveLayerNotFoundError(f"Language '{target}' not found")
        stmt = stmt.where(
            ConfigLayer.layer_type == "language",
            ConfigLayer.language_id == lang.id,
        )
    elif scope == "override":
        layer_key = f"override:{target}"
        stmt = stmt.where(
            ConfigLayer.layer_type == "combo",
            ConfigLayer.layer_key == layer_key,
        )
    else:
        raise DraftServiceError(f"Unknown scope '{scope}'")

    res = await session.execute(stmt.limit(1))
    layer = res.scalar_one_or_none()
    if layer is None:
        raise ActiveLayerNotFoundError(
            f"No active {scope} layer found for target '{target}'"
        )
    return layer


# ---------------------------------------------------------------------------
# Layer → dict serialiser for diff/preview (lightweight)
# ---------------------------------------------------------------------------


def _layer_to_summary_dict(layer: ConfigLayer) -> dict[str, Any]:
    return {
        "id": layer.id,
        "layer_type": layer.layer_type,
        "layer_key": layer.layer_key,
        "status": layer.status,
        "version": layer.version,
        "draft_name": layer.draft_name,
        "draft_summary": layer.draft_summary,
        "parent_layer_id": layer.parent_layer_id,
        "created_from_layer_id": layer.created_from_layer_id,
        "published_at": layer.published_at.isoformat() if layer.published_at else None,
        "published_by": layer.published_by,
        "archived_at": layer.archived_at.isoformat() if layer.archived_at else None,
        "archived_by": layer.archived_by,
        "archive_reason": layer.archive_reason,
        "created_by": layer.created_by,
        "created_at": layer.created_at.isoformat() if layer.created_at else None,
        "updated_by": layer.updated_by,
        "updated_at": layer.updated_at.isoformat() if layer.updated_at else None,
    }


# ---------------------------------------------------------------------------
# Ticket 3 — Create draft from active layer
# ---------------------------------------------------------------------------


async def create_draft_from_active(
    session: AsyncSession,
    scope: str,
    target: str,
    actor: str,
    *,
    draft_name: str | None = None,
    draft_summary: str | None = None,
) -> dict[str, Any]:
    """Create a draft clone of the active layer for ``scope``/``target``.

    Returns a summary dict of the newly created draft layer.

    Raises
    ------
    ActiveLayerNotFoundError
        When no active layer exists for the given scope/target.
    """
    active_layer = await _resolve_active_layer(session, scope, target)
    svc = ConfigLayerLifecycleService(session)
    draft = await svc.clone_layer_to_draft(
        active_layer,
        actor,
        draft_name=draft_name,
        draft_summary=draft_summary,
    )
    return _layer_to_summary_dict(draft)


# ---------------------------------------------------------------------------
# Ticket 5 — Draft preview resolver
# ---------------------------------------------------------------------------


async def load_draft_preview(
    session: AsyncSession,
    draft_layer_id: int,
    tool_id: str,
    language_id: str,
) -> dict[str, Any]:
    """Resolve wizard config with the draft layer substituted in for its scope.

    The draft layer replaces the active layer for the same scope (tool or
    language).  All other layers remain active.

    Returns the same shape as ``DatabaseConfigReadRepository.load_resolved_config``.
    """
    from app.services.config_db_repository import (
        _get_active_schema,
        _get_steps,
        _get_fields_for_step,
        _get_layer,
        _get_step_overrides,
        _get_field_metadata_overrides,
        _get_field_content_overrides,
        _override_source_label,
        _apply_overrides_to_field_tree,
        _apply_lang_overrides_to_fields,
    )
    from app.services.config_db_serialiser import (
        apply_step_overrides_to_dict,
        step_to_dict,
        _build_field_tree,
    )

    # Load draft
    draft_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.id == draft_layer_id,
            ConfigLayer.status == "draft",
        ).limit(1)
    )
    draft = draft_res.scalar_one_or_none()
    if draft is None:
        raise DraftServiceError(
            f"Draft layer id={draft_layer_id} not found or not in 'draft' status"
        )

    schema = await _get_active_schema(session)
    if schema is None:
        raise DraftServiceError("No active config schema in database")

    steps = await _get_steps(session, schema)

    from app.db.models.tool import AITool
    from app.db.models.language import Language

    tool_res = await session.execute(select(AITool).where(AITool.tool_key == tool_id))
    tool_row = tool_res.scalar_one_or_none()
    lang_res = await session.execute(select(Language).where(Language.language_key == language_id))
    lang_row = lang_res.scalar_one_or_none()

    # Determine which layer to use for each scope:
    # if the draft is for the tool scope, replace tool_layer with draft
    # if the draft is for the language scope, replace lang_layer with draft
    if draft.layer_type == "tool":
        tool_layer = draft
        lang_layer = (
            await _get_layer(session, "language", language_id=lang_row.id)
            if lang_row else None
        )
    elif draft.layer_type == "language":
        tool_layer = (
            await _get_layer(session, "tool", tool_id=tool_row.id)
            if tool_row else None
        )
        lang_layer = draft
    else:  # combo draft — apply as combo layer (simplified: treat as lang_layer override)
        tool_layer = (
            await _get_layer(session, "tool", tool_id=tool_row.id)
            if tool_row else None
        )
        lang_layer = (
            await _get_layer(session, "language", language_id=lang_row.id)
            if lang_row else None
        )
        # combo draft overrides are just added on top (future extension)

    # Collect overrides
    tool_step_overrides: dict[int, ConfigStepOverride] = {}
    lang_step_overrides: dict[int, ConfigStepOverride] = {}
    tool_meta: dict[int, ConfigFieldMetadataOverride] = {}
    tool_content: dict[int, ConfigFieldContentOverride] = {}
    lang_meta: dict[int, ConfigFieldMetadataOverride] = {}
    lang_content: dict[int, ConfigFieldContentOverride] = {}

    if tool_layer:
        tool_so = await _get_step_overrides(session, tool_layer)
        tool_step_overrides = {so.step_id: so for so in tool_so}
        tool_meta = await _get_field_metadata_overrides(session, tool_layer)
        tool_content = await _get_field_content_overrides(session, tool_layer)

    if lang_layer:
        lang_so = await _get_step_overrides(session, lang_layer)
        lang_step_overrides = {so.step_id: so for so in lang_so}
        lang_meta = await _get_field_metadata_overrides(session, lang_layer)
        lang_content = await _get_field_content_overrides(session, lang_layer)

    # Source labels include "draft:" prefix to indicate preview
    def _draft_label(layer: ConfigLayer) -> str:
        base = _override_source_label(layer)
        if layer.status == "draft":
            return f"draft:{base}"
        return base

    tool_source = _draft_label(tool_layer) if tool_layer else ""
    lang_source = _draft_label(lang_layer) if lang_layer else ""

    serialised_steps: list[dict[str, Any]] = []
    for step in steps:
        all_fields = await _get_fields_for_step(session, schema, step)

        if tool_layer:
            fields = _apply_overrides_to_field_tree(
                all_fields, None, tool_meta, tool_content, tool_source
            )
        else:
            fields = _build_field_tree(all_fields, None)

        if lang_layer:
            fields = _apply_lang_overrides_to_fields(
                fields, all_fields, lang_meta, lang_content, lang_source
            )

        step_dict = step_to_dict(step, all_fields)
        step_dict["fields"] = fields

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
        "_draft_layer_id": draft_layer_id,
        "_draft_scope": draft.layer_type,
    }


# ---------------------------------------------------------------------------
# Ticket 6 — Draft diff endpoint
# ---------------------------------------------------------------------------


async def _collect_layer_overrides(
    session: AsyncSession, layer: ConfigLayer
) -> dict[str, Any]:
    """Collect all overrides for a layer into a comparable dict."""
    so_res = await session.execute(
        select(ConfigStepOverride).where(ConfigStepOverride.layer_id == layer.id)
    )
    fmo_res = await session.execute(
        select(ConfigFieldMetadataOverride).where(
            ConfigFieldMetadataOverride.layer_id == layer.id
        )
    )
    fco_res = await session.execute(
        select(ConfigFieldContentOverride).where(
            ConfigFieldContentOverride.layer_id == layer.id
        )
    )

    step_overrides = {}
    for so in so_res.scalars().all():
        step_overrides[so.step_id] = {
            "hidden": so.hidden,
            "title_override": so.title_override,
            "description_override": so.description_override,
            "hint_override": so.hint_override,
        }

    metadata_overrides = {}
    for fmo in fmo_res.scalars().all():
        metadata_overrides[fmo.field_id] = {
            "default_value_json": fmo.default_value_json,
            "editability": fmo.editability,
            "required": fmo.required,
            "hidden": fmo.hidden,
            "lock_reason": fmo.lock_reason,
        }

    content_overrides = {}
    for fco in fco_res.scalars().all():
        content_overrides[fco.field_id] = {
            "replace_options_with_json": fco.replace_options_with_json,
            "merge_options_json": fco.merge_options_json,
            "replace_presets_with_json": fco.replace_presets_with_json,
            "merge_presets_json": fco.merge_presets_json,
            "preset_files_to_add_json": fco.preset_files_to_add_json,
            "merge_mode": fco.merge_mode,
        }

    return {
        "step_overrides": step_overrides,
        "metadata_overrides": metadata_overrides,
        "content_overrides": content_overrides,
        "metadata_json": layer.metadata_json,
        "applies_to_json": layer.applies_to_json,
    }


def _diff_dicts(
    left: dict[str, Any] | None,
    right: dict[str, Any] | None,
    path: str = "",
) -> list[dict[str, Any]]:
    """Recursively diff two dicts. Returns list of change records."""
    changes: list[dict[str, Any]] = []
    left = left or {}
    right = right or {}
    all_keys = set(left) | set(right)

    for key in sorted(all_keys):
        key_path = f"{path}.{key}" if path else str(key)
        lv = left.get(key)
        rv = right.get(key)
        if lv is None and rv is not None:
            changes.append({"path": key_path, "type": "added", "left": None, "right": rv})
        elif lv is not None and rv is None:
            changes.append({"path": key_path, "type": "removed", "left": lv, "right": None})
        elif lv != rv:
            if isinstance(lv, dict) and isinstance(rv, dict):
                changes.extend(_diff_dicts(lv, rv, key_path))
            else:
                changes.append({"path": key_path, "type": "changed", "left": lv, "right": rv})

    return changes


async def diff_draft_vs_source(
    session: AsyncSession,
    draft_layer_id: int,
) -> dict[str, Any]:
    """Compare a draft layer against its parent/source active layer.

    Returns a structured diff suitable for UI rendering.

    Raises
    ------
    DraftServiceError
        When the draft or its parent cannot be found.
    """
    draft_res = await session.execute(
        select(ConfigLayer).where(
            ConfigLayer.id == draft_layer_id,
            ConfigLayer.status == "draft",
        ).limit(1)
    )
    draft = draft_res.scalar_one_or_none()
    if draft is None:
        raise DraftServiceError(
            f"Draft layer id={draft_layer_id} not found or not in 'draft' status"
        )

    source_id = draft.created_from_layer_id or draft.parent_layer_id
    if source_id is None:
        # No known parent — diff against empty
        source_overrides: dict[str, Any] = {}
        source_summary = "no source layer"
    else:
        src_res = await session.execute(
            select(ConfigLayer).where(ConfigLayer.id == source_id).limit(1)
        )
        source = src_res.scalar_one_or_none()
        if source is None:
            source_overrides = {}
            source_summary = f"source layer id={source_id} not found"
        else:
            source_overrides = await _collect_layer_overrides(session, source)
            source_summary = f"layer id={source_id} ({source.status})"

    draft_overrides = await _collect_layer_overrides(session, draft)

    # Diff each category
    changes = _diff_dicts(source_overrides, draft_overrides)

    return {
        "draft_layer_id": draft_layer_id,
        "source_layer_id": source_id,
        "source_summary": source_summary,
        "draft_name": draft.draft_name,
        "draft_summary_text": draft.draft_summary,
        "changes": changes,
        "change_count": len(changes),
        "has_changes": len(changes) > 0,
    }


# ---------------------------------------------------------------------------
# Ticket 7 — Promote draft
# ---------------------------------------------------------------------------


async def promote_draft(
    session: AsyncSession,
    draft_layer_id: int,
    actor: str,
    *,
    summary: str | None = None,
) -> dict[str, Any]:
    """Promote a draft layer to active, archiving the current active layer.

    Returns a dict with the promoted layer summary and the archived layer id
    (if any).

    Raises
    ------
    DraftServiceError / LayerTransitionError
        On invalid state or missing draft.
    """
    from app.db.models.audit import ConfigVersion
    from app.services.config_db_write_repository import _next_version_number

    draft_res = await session.execute(
        select(ConfigLayer).where(ConfigLayer.id == draft_layer_id).limit(1)
    )
    draft = draft_res.scalar_one_or_none()
    if draft is None:
        raise DraftServiceError(f"Layer id={draft_layer_id} not found")

    svc = ConfigLayerLifecycleService(session)
    promoted, archived = await svc.promote_draft(draft, actor, summary=summary)

    # Write version snapshot
    from app.db.models.audit import ConfigAuditEvent, ConfigVersion
    now = datetime.now(timezone.utc)
    version_number = await _next_version_number(session, promoted.layer_type, promoted.layer_key)
    version = ConfigVersion(
        scope=promoted.layer_type,
        target_key=promoted.layer_key,
        version_number=version_number,
        actor=actor,
        summary=summary or f"Promoted draft id={draft_layer_id}",
        data_json={"layer_id": promoted.id, "layer_key": promoted.layer_key},
        created_at=now,
    )
    session.add(version)
    await session.flush()

    return {
        "promoted_layer": _layer_to_summary_dict(promoted),
        "archived_layer_id": archived.id if archived else None,
    }


# ---------------------------------------------------------------------------
# Ticket 9 — Archive draft
# ---------------------------------------------------------------------------


async def archive_draft(
    session: AsyncSession,
    draft_layer_id: int,
    actor: str,
    *,
    reason: str | None = None,
) -> dict[str, Any]:
    """Archive a draft layer (discard without promoting).

    Raises
    ------
    DraftServiceError
        If the layer is not found or not in 'draft' status.
    LayerTransitionError
        If the layer cannot be archived (e.g. it is already active).
    """
    draft_res = await session.execute(
        select(ConfigLayer).where(ConfigLayer.id == draft_layer_id).limit(1)
    )
    draft = draft_res.scalar_one_or_none()
    if draft is None:
        raise DraftServiceError(f"Layer id={draft_layer_id} not found")
    if draft.status != "draft":
        raise DraftServiceError(
            f"Layer id={draft_layer_id} is not a draft (status='{draft.status}'). "
            "Only draft layers can be archived via this endpoint."
        )

    svc = ConfigLayerLifecycleService(session)
    await svc.transition(draft, "archived", actor, reason=reason)

    return _layer_to_summary_dict(draft)


# ---------------------------------------------------------------------------
# Ticket 10 — List drafts
# ---------------------------------------------------------------------------


async def list_drafts(
    session: AsyncSession,
    *,
    layer_type: str | None = None,
    tool_key: str | None = None,
    language_key: str | None = None,
    status: str | None = None,
    created_by: str | None = None,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """Return a list of draft (and optionally archived) config layers.

    Filters can be combined.  By default only ``draft`` status layers are
    returned.  Pass ``include_archived=True`` to also include ``archived``
    layers.
    """
    stmt = select(ConfigLayer)

    if status:
        stmt = stmt.where(ConfigLayer.status == status)
    elif include_archived:
        stmt = stmt.where(ConfigLayer.status.in_(["draft", "archived"]))
    else:
        stmt = stmt.where(ConfigLayer.status == "draft")

    if layer_type:
        stmt = stmt.where(ConfigLayer.layer_type == layer_type)

    if tool_key:
        tool_res = await session.execute(
            select(AITool).where(AITool.tool_key == tool_key).limit(1)
        )
        tool = tool_res.scalar_one_or_none()
        if tool:
            stmt = stmt.where(ConfigLayer.tool_id == tool.id)

    if language_key:
        lang_res = await session.execute(
            select(Language).where(Language.language_key == language_key).limit(1)
        )
        lang = lang_res.scalar_one_or_none()
        if lang:
            stmt = stmt.where(ConfigLayer.language_id == lang.id)

    if created_by:
        stmt = stmt.where(ConfigLayer.created_by == created_by)

    stmt = stmt.order_by(ConfigLayer.created_at.desc())

    res = await session.execute(stmt)
    return [_layer_to_summary_dict(layer) for layer in res.scalars().all()]
