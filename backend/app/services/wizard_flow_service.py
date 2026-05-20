"""Phase 5B — Wizard flow service.

Manages user-level wizard flows: creation, retrieval, application to
a resolved config, and validation.
"""
from __future__ import annotations

from typing import Any

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models.flow import WizardFlow, WizardFlowStep
from app.db.models.schema import ConfigSchema, ConfigStep


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class FlowNotFoundError(Exception):
    pass


class FlowOwnershipError(Exception):
    pass


class FlowServiceError(Exception):
    pass


# ---------------------------------------------------------------------------
# CRUD operations
# ---------------------------------------------------------------------------


async def create_flow(
    session: AsyncSession,
    owner_actor: str,
    name: str,
    schema_id: int | None = None,
    tool_id: int | None = None,
    description: str = "",
    step_keys: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new wizard flow.

    If ``step_keys`` is not provided, creates a flow from all steps in the
    active schema.
    """
    # Resolve schema
    if schema_id is None:
        res = await session.execute(
            select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
        )
        schema = res.scalar_one_or_none()
        if schema is None:
            raise FlowServiceError("No active schema found")
        schema_id = schema.id

    flow = WizardFlow(
        owner_actor=owner_actor,
        name=name,
        description=description,
        source_schema_id=schema_id,
        source_tool_id=tool_id,
        is_default=False,
        status="active",
        created_by=owner_actor,
        updated_by=owner_actor,
    )
    session.add(flow)
    await session.flush()

    # Populate steps
    if step_keys is None:
        # Use all non-hidden steps from schema
        step_res = await session.execute(
            select(ConfigStep)
            .where(ConfigStep.schema_id == schema_id, ConfigStep.hidden.is_(False))
            .order_by(ConfigStep.position)
        )
        step_keys = [s.step_key for s in step_res.scalars().all()]

    for position, key in enumerate(step_keys):
        flow_step = WizardFlowStep(
            flow_id=flow.id,
            step_key=key,
            position=position,
            is_enabled=True,
            created_by=owner_actor,
            updated_by=owner_actor,
        )
        session.add(flow_step)

    await session.flush()
    return _flow_to_dict(flow)


async def list_flows(
    session: AsyncSession,
    owner_actor: str,
    include_archived: bool = False,
) -> list[dict[str, Any]]:
    """List flows for the given actor."""
    stmt = select(WizardFlow).where(WizardFlow.owner_actor == owner_actor)
    if not include_archived:
        stmt = stmt.where(WizardFlow.status == "active")
    stmt = stmt.order_by(WizardFlow.is_default.desc(), WizardFlow.name)

    res = await session.execute(stmt)
    return [_flow_to_dict(f) for f in res.scalars().all()]


async def get_flow(
    session: AsyncSession,
    flow_id: int,
    owner_actor: str,
) -> dict[str, Any]:
    """Get a flow by ID, with ownership check."""
    flow = await session.get(WizardFlow, flow_id)
    if flow is None:
        raise FlowNotFoundError(f"Flow {flow_id} not found")
    if flow.owner_actor != owner_actor:
        raise FlowOwnershipError("You do not own this flow")

    # Eagerly load steps
    step_res = await session.execute(
        select(WizardFlowStep)
        .where(WizardFlowStep.flow_id == flow.id)
        .order_by(WizardFlowStep.position)
    )
    steps = list(step_res.scalars().all())
    return _flow_to_dict(flow, steps)


async def update_flow(
    session: AsyncSession,
    flow_id: int,
    owner_actor: str,
    *,
    name: str | None = None,
    description: str | None = None,
    step_keys: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Update a flow's metadata and/or step ordering.

    ``step_keys`` should be a list of dicts: [{step_key, is_enabled, custom_title?, custom_description?}]
    """
    flow = await session.get(WizardFlow, flow_id)
    if flow is None:
        raise FlowNotFoundError(f"Flow {flow_id} not found")
    if flow.owner_actor != owner_actor:
        raise FlowOwnershipError("You do not own this flow")

    if name is not None:
        flow.name = name
    if description is not None:
        flow.description = description
    flow.updated_by = owner_actor

    if step_keys is not None:
        # Delete existing steps and rebuild
        await session.execute(
            select(WizardFlowStep).where(WizardFlowStep.flow_id == flow.id)
        )
        existing_res = await session.execute(
            select(WizardFlowStep).where(WizardFlowStep.flow_id == flow.id)
        )
        for existing in existing_res.scalars().all():
            await session.delete(existing)
        await session.flush()

        for position, step_data in enumerate(step_keys):
            flow_step = WizardFlowStep(
                flow_id=flow.id,
                step_key=step_data["step_key"],
                position=position,
                is_enabled=step_data.get("is_enabled", True),
                custom_title=step_data.get("custom_title"),
                custom_description=step_data.get("custom_description"),
                created_by=owner_actor,
                updated_by=owner_actor,
            )
            session.add(flow_step)

    await session.flush()
    return await get_flow(session, flow_id, owner_actor)


async def set_default_flow(
    session: AsyncSession,
    flow_id: int,
    owner_actor: str,
) -> dict[str, Any]:
    """Set a flow as the default for its owner (unsets any previous default)."""
    flow = await session.get(WizardFlow, flow_id)
    if flow is None:
        raise FlowNotFoundError(f"Flow {flow_id} not found")
    if flow.owner_actor != owner_actor:
        raise FlowOwnershipError("You do not own this flow")

    # Unset all other defaults for this owner
    await session.execute(
        update(WizardFlow)
        .where(WizardFlow.owner_actor == owner_actor, WizardFlow.id != flow_id)
        .values(is_default=False)
    )
    flow.is_default = True
    flow.updated_by = owner_actor
    await session.flush()
    return _flow_to_dict(flow)


async def archive_flow(
    session: AsyncSession,
    flow_id: int,
    owner_actor: str,
) -> dict[str, Any]:
    """Archive a flow."""
    flow = await session.get(WizardFlow, flow_id)
    if flow is None:
        raise FlowNotFoundError(f"Flow {flow_id} not found")
    if flow.owner_actor != owner_actor:
        raise FlowOwnershipError("You do not own this flow")

    flow.status = "archived"
    flow.is_default = False
    flow.updated_by = owner_actor
    await session.flush()
    return _flow_to_dict(flow)


# ---------------------------------------------------------------------------
# Flow application
# ---------------------------------------------------------------------------


def apply_flow_to_config(
    config: dict[str, Any],
    flow_steps: list[dict[str, Any]],
) -> dict[str, Any]:
    """Apply a flow's step ordering to a resolved config dict.

    Reorders and filters the config's steps according to the flow.
    Steps in the flow that don't exist in the config are silently skipped.
    Steps in the config but not in the flow are excluded.
    """
    steps_by_key = {s["id"]: s for s in config.get("steps", [])}
    ordered_steps: list[dict[str, Any]] = []

    for flow_step in flow_steps:
        if not flow_step.get("is_enabled", True):
            continue
        key = flow_step["step_key"]
        if key not in steps_by_key:
            continue
        step = dict(steps_by_key[key])
        # Apply custom title/description if set
        if flow_step.get("custom_title"):
            step["title"] = flow_step["custom_title"]
        if flow_step.get("custom_description"):
            step["description"] = flow_step["custom_description"]
        ordered_steps.append(step)

    return {**config, "steps": ordered_steps}


async def get_or_create_default_flow(
    session: AsyncSession,
    owner_actor: str,
    schema_id: int | None = None,
    tool_id: int | None = None,
) -> dict[str, Any]:
    """Get the user's default flow, or create one from the active schema."""
    stmt = (
        select(WizardFlow)
        .where(
            WizardFlow.owner_actor == owner_actor,
            WizardFlow.is_default.is_(True),
            WizardFlow.status == "active",
        )
        .limit(1)
    )
    res = await session.execute(stmt)
    flow = res.scalar_one_or_none()

    if flow is not None:
        return await get_flow(session, flow.id, owner_actor)

    # Create a default flow
    result = await create_flow(
        session,
        owner_actor,
        name="Default Flow",
        schema_id=schema_id,
        tool_id=tool_id,
        description="Auto-generated default flow with all steps",
    )
    # Mark as default
    flow_obj = await session.get(WizardFlow, result["id"])
    if flow_obj:
        flow_obj.is_default = True
        await session.flush()
        result["is_default"] = True
    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _flow_to_dict(
    flow: WizardFlow,
    steps: list[WizardFlowStep] | None = None,
) -> dict[str, Any]:
    """Convert a WizardFlow ORM object to a response dict."""
    result: dict[str, Any] = {
        "id": flow.id,
        "name": flow.name,
        "description": flow.description,
        "owner_actor": flow.owner_actor,
        "source_schema_id": flow.source_schema_id,
        "source_tool_id": flow.source_tool_id,
        "is_default": flow.is_default,
        "status": flow.status,
        "created_at": flow.created_at.isoformat() if flow.created_at else None,
        "updated_at": flow.updated_at.isoformat() if flow.updated_at else None,
    }
    if steps is not None:
        result["steps"] = [
            {
                "id": s.id,
                "step_key": s.step_key,
                "position": s.position,
                "is_enabled": s.is_enabled,
                "custom_title": s.custom_title,
                "custom_description": s.custom_description,
            }
            for s in steps
        ]
    return result
