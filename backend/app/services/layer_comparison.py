"""Phase 4 — Ticket 11: Layer comparison service.

Compare any two config layers of the same scope.  Useful for comparing
active vs archived, draft vs active, or any two layers.

The comparison reuses the ``_diff_dicts`` logic from ``draft_service.py``.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.layer import ConfigLayer
from app.services.draft_service import _collect_layer_overrides, _diff_dicts


class ComparisonError(Exception):
    """Raised when the comparison request is invalid."""


async def compare_layers(
    session: AsyncSession,
    left_layer_id: int,
    right_layer_id: int,
) -> dict[str, Any]:
    """Compare two config layers and return a structured diff.

    Layers must be of the same ``layer_type`` (tool/language/combo).

    Parameters
    ----------
    session:
        Async SQLAlchemy session (read-only).
    left_layer_id:
        ID of the "before" / left layer.
    right_layer_id:
        ID of the "after" / right layer.

    Returns
    -------
    Diff dict with ``changes``, ``change_count``, and layer summaries.

    Raises
    ------
    ComparisonError
        If either layer is not found, or they are of incompatible types.
    """
    left_res = await session.execute(
        select(ConfigLayer).where(ConfigLayer.id == left_layer_id).limit(1)
    )
    left = left_res.scalar_one_or_none()
    if left is None:
        raise ComparisonError(f"ConfigLayer id={left_layer_id} not found")

    right_res = await session.execute(
        select(ConfigLayer).where(ConfigLayer.id == right_layer_id).limit(1)
    )
    right = right_res.scalar_one_or_none()
    if right is None:
        raise ComparisonError(f"ConfigLayer id={right_layer_id} not found")

    if left.layer_type != right.layer_type:
        raise ComparisonError(
            f"Layers have incompatible types: "
            f"left={left.layer_type!r}, right={right.layer_type!r}. "
            "Only layers of the same type can be compared."
        )

    left_overrides = await _collect_layer_overrides(session, left)
    right_overrides = await _collect_layer_overrides(session, right)

    changes = _diff_dicts(left_overrides, right_overrides)

    return {
        "left_layer_id": left_layer_id,
        "right_layer_id": right_layer_id,
        "left_status": left.status,
        "right_status": right.status,
        "left_layer_key": left.layer_key,
        "right_layer_key": right.layer_key,
        "layer_type": left.layer_type,
        "changes": changes,
        "change_count": len(changes),
        "has_changes": len(changes) > 0,
    }
