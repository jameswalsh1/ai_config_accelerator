"""Phase 4 — Ticket 2: Config layer lifecycle service.

Manages valid status transitions for ConfigLayer records.  All status
changes must go through this service; direct ``layer.status = "..."``
mutations are forbidden in other services.

Valid transitions
-----------------
active  → draft copy     (creates a NEW draft from an active layer)
draft   → active         (promotion, handled by promote_draft)
draft   → archived       (discard a draft without promoting)
active  → archived       (archive an active layer — normally done via promotion)
candidate → draft        (accepted candidate becomes a draft)
candidate → rejected     (reviewer rejects a candidate)
candidate → withdrawn    (submitter withdraws a candidate)

Invalid (raise LayerTransitionError):
archived → * (anything)
rejected → * (anything)
withdrawn → * (anything)
draft   → rejected
active  → rejected
active  → candidate

Promotion flow (Ticket 7):
  draft → active  +  old active → archived   (both atomic)
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.audit import ConfigAuditEvent
from app.db.models.layer import (
    LAYER_STATUS_VALUES,
    ConfigFieldContentOverride,
    ConfigFieldMetadataOverride,
    ConfigLayer,
    ConfigStepOverride,
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class LayerTransitionError(Exception):
    """Raised when a requested lifecycle transition is not permitted."""


class LayerNotFoundError(Exception):
    """Raised when the target ConfigLayer cannot be found."""


# ---------------------------------------------------------------------------
# Allowed transitions table
# ---------------------------------------------------------------------------

# Maps (from_status, to_status) → True (permitted).
# Transitions not in this map are denied.
_ALLOWED_TRANSITIONS: set[tuple[str, str]] = {
    # Promote draft to active (Ticket 7 handles the paired archival)
    ("draft", "active"),
    # Archive drafts
    ("draft", "archived"),
    # Archive active layers (paired with promotion or direct archival)
    ("active", "archived"),
    # Candidate review outcomes
    ("candidate", "draft"),
    ("candidate", "rejected"),
    ("candidate", "withdrawn"),
}

# Terminal states — no transitions out
_TERMINAL_STATUSES = frozenset({"archived", "rejected", "withdrawn"})


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class ConfigLayerLifecycleService:
    """Centralises ConfigLayer status transitions.

    All methods operate within the supplied ``AsyncSession``.  Callers
    are responsible for ``session.commit()`` after successful operations.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_layer(self, layer_id: int) -> ConfigLayer:
        """Load a layer by primary key, raising ``LayerNotFoundError`` if absent."""
        result = await self._session.execute(
            select(ConfigLayer).where(ConfigLayer.id == layer_id)
        )
        layer = result.scalar_one_or_none()
        if layer is None:
            raise LayerNotFoundError(f"ConfigLayer id={layer_id} not found")
        return layer

    def validate_transition(self, layer: ConfigLayer, to_status: str) -> None:
        """Raise ``LayerTransitionError`` if the transition is not permitted."""
        if to_status not in LAYER_STATUS_VALUES:
            raise LayerTransitionError(
                f"Unknown target status '{to_status}'. "
                f"Valid values: {', '.join(LAYER_STATUS_VALUES)}"
            )
        from_status = layer.status
        if from_status == to_status:
            return  # no-op is always allowed
        if from_status in _TERMINAL_STATUSES:
            raise LayerTransitionError(
                f"Layer id={layer.id} is in terminal status '{from_status}' "
                "and cannot be transitioned."
            )
        if (from_status, to_status) not in _ALLOWED_TRANSITIONS:
            raise LayerTransitionError(
                f"Transition '{from_status}' → '{to_status}' is not permitted "
                f"for ConfigLayer id={layer.id}."
            )

    async def transition(
        self,
        layer: ConfigLayer,
        to_status: str,
        actor: str,
        *,
        reason: str | None = None,
    ) -> None:
        """Apply a validated status transition and write an audit event.

        For ``archived`` and ``rejected`` transitions the ``reason`` is stored
        on the layer record.  For ``active`` (promotion) use
        ``promote_draft`` instead.

        Parameters
        ----------
        layer:
            The ConfigLayer to transition.
        to_status:
            Desired new status.
        actor:
            Actor string performing the transition.
        reason:
            Optional human-readable reason (stored for archive/reject).
        """
        self.validate_transition(layer, to_status)

        now = datetime.now(timezone.utc)
        from_status = layer.status

        if to_status == "archived":
            layer.archived_at = now
            layer.archived_by = actor
            if reason:
                layer.archive_reason = reason
        elif to_status == "rejected":
            layer.rejected_at = now
            layer.rejected_by = actor
            if reason:
                layer.rejection_reason = reason

        layer.status = to_status
        layer.updated_by = actor
        layer.updated_at = now

        audit = ConfigAuditEvent(
            actor=actor,
            action=f"layer_{to_status}",
            scope=layer.layer_type,
            target_key=layer.layer_key,
            summary=f"Layer id={layer.id} transitioned {from_status!r} → {to_status!r}"
            + (f": {reason}" if reason else ""),
            created_at=now,
        )
        self._session.add(audit)
        await self._session.flush()

    async def clone_layer_to_draft(
        self,
        source_layer: ConfigLayer,
        actor: str,
        *,
        draft_name: str | None = None,
        draft_summary: str | None = None,
    ) -> ConfigLayer:
        """Create a draft clone of ``source_layer``.

        Copies all step/field-metadata/field-content overrides.  The new
        draft's ``parent_layer_id`` and ``created_from_layer_id`` are set to
        ``source_layer.id``.

        The source (active) layer is **not** modified.
        """
        now = datetime.now(timezone.utc)

        # Generate a unique version string for the new draft
        version = f"draft-{now.strftime('%Y%m%dT%H%M%SZ')}"

        draft = ConfigLayer(
            layer_type=source_layer.layer_type,
            layer_key=source_layer.layer_key,
            tool_id=source_layer.tool_id,
            language_id=source_layer.language_id,
            version=version,
            status="draft",
            metadata_json=source_layer.metadata_json,
            applies_to_json=source_layer.applies_to_json,
            parent_layer_id=source_layer.id,
            created_from_layer_id=source_layer.id,
            draft_name=draft_name,
            draft_summary=draft_summary,
            created_by=actor,
            updated_by=actor,
            created_at=now,
            updated_at=now,
        )
        self._session.add(draft)
        await self._session.flush()  # get draft.id

        # Clone step overrides
        so_res = await self._session.execute(
            select(ConfigStepOverride).where(
                ConfigStepOverride.layer_id == source_layer.id
            )
        )
        for so in so_res.scalars().all():
            cloned_so = ConfigStepOverride(
                layer_id=draft.id,
                step_id=so.step_id,
                hidden=so.hidden,
                title_override=so.title_override,
                description_override=so.description_override,
                hint_override=so.hint_override,
                created_by=actor,
                updated_by=actor,
                created_at=now,
                updated_at=now,
            )
            self._session.add(cloned_so)

        # Clone field metadata overrides
        fmo_res = await self._session.execute(
            select(ConfigFieldMetadataOverride).where(
                ConfigFieldMetadataOverride.layer_id == source_layer.id
            )
        )
        for fmo in fmo_res.scalars().all():
            cloned_fmo = ConfigFieldMetadataOverride(
                layer_id=draft.id,
                field_id=fmo.field_id,
                default_value_json=fmo.default_value_json,
                editability=fmo.editability,
                required=fmo.required,
                hidden=fmo.hidden,
                lock_reason=fmo.lock_reason,
                created_by=actor,
                updated_by=actor,
                created_at=now,
                updated_at=now,
            )
            self._session.add(cloned_fmo)

        # Clone field content overrides
        fco_res = await self._session.execute(
            select(ConfigFieldContentOverride).where(
                ConfigFieldContentOverride.layer_id == source_layer.id
            )
        )
        for fco in fco_res.scalars().all():
            cloned_fco = ConfigFieldContentOverride(
                layer_id=draft.id,
                field_id=fco.field_id,
                replace_options_with_json=fco.replace_options_with_json,
                merge_options_json=fco.merge_options_json,
                replace_presets_with_json=fco.replace_presets_with_json,
                merge_presets_json=fco.merge_presets_json,
                preset_files_to_add_json=fco.preset_files_to_add_json,
                merge_mode=fco.merge_mode,
                created_by=actor,
                updated_by=actor,
                created_at=now,
                updated_at=now,
            )
            self._session.add(cloned_fco)

        await self._session.flush()

        audit = ConfigAuditEvent(
            actor=actor,
            action="layer_draft_created",
            scope=source_layer.layer_type,
            target_key=source_layer.layer_key,
            summary=(
                f"Draft id={draft.id} created from active layer id={source_layer.id}"
                + (f": {draft_name}" if draft_name else "")
            ),
            created_at=now,
        )
        self._session.add(audit)
        await self._session.flush()

        return draft

    async def promote_draft(
        self,
        draft_layer: ConfigLayer,
        actor: str,
        *,
        summary: str | None = None,
    ) -> tuple[ConfigLayer, ConfigLayer | None]:
        """Promote ``draft_layer`` to active, archiving the current active layer.

        Returns ``(promoted_layer, archived_previous_layer | None)``.

        This operation is transactional — both status changes happen in the
        same session flush.  The caller commits.

        Raises ``LayerTransitionError`` if ``draft_layer.status != 'draft'``.
        """
        self.validate_transition(draft_layer, "active")

        now = datetime.now(timezone.utc)

        # Find and archive the current active layer for the same scope
        active_filter = [
            ConfigLayer.layer_type == draft_layer.layer_type,
            ConfigLayer.status == "active",
            ConfigLayer.layer_key == draft_layer.layer_key,
            ConfigLayer.id != draft_layer.id,
        ]
        prev_res = await self._session.execute(
            select(ConfigLayer).where(*active_filter).limit(1)
        )
        previous_active = prev_res.scalar_one_or_none()

        if previous_active is not None:
            previous_active.status = "archived"
            previous_active.archived_at = now
            previous_active.archived_by = actor
            previous_active.archive_reason = f"Superseded by draft id={draft_layer.id} promotion"
            previous_active.updated_by = actor
            previous_active.updated_at = now

        # Promote the draft
        draft_layer.status = "active"
        draft_layer.published_at = now
        draft_layer.published_by = actor
        draft_layer.published_from_layer_id = draft_layer.id
        draft_layer.updated_by = actor
        draft_layer.updated_at = now

        await self._session.flush()

        promo_summary = summary or f"Draft id={draft_layer.id} promoted to active"
        audit = ConfigAuditEvent(
            actor=actor,
            action="layer_promoted",
            scope=draft_layer.layer_type,
            target_key=draft_layer.layer_key,
            summary=promo_summary
            + (
                f"; previous active id={previous_active.id} archived"
                if previous_active
                else ""
            ),
            created_at=now,
        )
        self._session.add(audit)
        await self._session.flush()

        return draft_layer, previous_active
