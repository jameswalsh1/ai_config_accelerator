"""Phase 5A — Visibility rules router.

Provides endpoints for evaluating and managing conditional visibility rules.
"""
from __future__ import annotations

from typing import Any, AsyncGenerator

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.services.auth import AuthUser, require_config_editor

router = APIRouter(prefix="/api/wizard", tags=["visibility"])


# ---------------------------------------------------------------------------
# DB session dependency
# ---------------------------------------------------------------------------


async def _require_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an AsyncSession; raises 503 if not in database mode."""
    from app.settings import get_config_source_settings

    if get_config_source_settings().config_source != "database":
        raise HTTPException(
            status_code=503,
            detail="Visibility endpoints require CONFIG_SOURCE=database",
        )
    from app.db.session import get_db_session

    async for session in get_db_session():
        yield session


# ---------------------------------------------------------------------------
# Request models
# ---------------------------------------------------------------------------


class EvaluateVisibilityRequest(BaseModel):
    answers: dict[str, dict[str, Any]]
    tool_key: str | None = None
    language_key: str | None = None


class CreateVisibilityRuleRequest(BaseModel):
    target_type: str  # "step" or "field"
    target_step_key: str
    target_field_path: str | None = None
    depends_on_field_path: str
    operator: str = "equals"
    value: Any = None
    action: str = "show"
    priority: int = 0


class UpdateVisibilityRuleRequest(BaseModel):
    operator: str | None = None
    value: Any = None
    action: str | None = None
    priority: int | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/visibility/rules")
async def list_visibility_rules(
    tool: str | None = Query(None),
    language: str | None = Query(None),
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> list[dict[str, Any]]:
    """Get all visibility rules for the active schema.

    Rules disabled by layer overrides are excluded.
    """
    from app.db.models.schema import ConfigSchema
    from app.db.models.layer import ConfigLayer
    from app.db.models.tool import AITool
    from app.db.models.language import Language
    from app.services.visibility_engine import get_visibility_rules_for_config
    from sqlalchemy import select

    # Get active schema
    res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = res.scalar_one_or_none()
    if schema is None:
        return []

    # Resolve layer IDs for tool/language
    layer_ids: list[int] = []
    if tool:
        tool_res = await session.execute(select(AITool).where(AITool.tool_key == tool))
        tool_row = tool_res.scalar_one_or_none()
        if tool_row:
            layer_res = await session.execute(
                select(ConfigLayer.id).where(
                    ConfigLayer.layer_type == "tool",
                    ConfigLayer.tool_id == tool_row.id,
                    ConfigLayer.status == "active",
                )
            )
            layer_ids.extend([r[0] for r in layer_res.all()])
    if language:
        lang_res = await session.execute(select(Language).where(Language.language_key == language))
        lang_row = lang_res.scalar_one_or_none()
        if lang_row:
            layer_res = await session.execute(
                select(ConfigLayer.id).where(
                    ConfigLayer.layer_type == "language",
                    ConfigLayer.language_id == lang_row.id,
                    ConfigLayer.status == "active",
                )
            )
            layer_ids.extend([r[0] for r in layer_res.all()])

    return await get_visibility_rules_for_config(session, schema.id, layer_ids or None)


@router.post("/visibility/evaluate")
async def evaluate_visibility(
    body: EvaluateVisibilityRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Evaluate visibility rules against provided answers.

    Returns a map of step/field visibility:
    {
        "steps": {"step_key": true/false, ...},
        "fields": {"step_key.field_key": true/false, ...},
        "rules_evaluated": 5
    }
    """
    from app.db.models.schema import ConfigSchema
    from app.db.models.layer import ConfigLayer
    from app.db.models.tool import AITool
    from app.db.models.language import Language
    from app.services.visibility_engine import evaluate_visibility as _eval
    from sqlalchemy import select

    # Get active schema
    res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = res.scalar_one_or_none()
    if schema is None:
        return {"steps": {}, "fields": {}, "rules_evaluated": 0}

    # Resolve layer IDs
    layer_ids: list[int] = []
    if body.tool_key:
        tool_res = await session.execute(select(AITool).where(AITool.tool_key == body.tool_key))
        tool_row = tool_res.scalar_one_or_none()
        if tool_row:
            layer_res = await session.execute(
                select(ConfigLayer.id).where(
                    ConfigLayer.layer_type == "tool",
                    ConfigLayer.tool_id == tool_row.id,
                    ConfigLayer.status == "active",
                )
            )
            layer_ids.extend([r[0] for r in layer_res.all()])
    if body.language_key:
        lang_res = await session.execute(select(Language).where(Language.language_key == body.language_key))
        lang_row = lang_res.scalar_one_or_none()
        if lang_row:
            layer_res = await session.execute(
                select(ConfigLayer.id).where(
                    ConfigLayer.layer_type == "language",
                    ConfigLayer.language_id == lang_row.id,
                    ConfigLayer.status == "active",
                )
            )
            layer_ids.extend([r[0] for r in layer_res.all()])

    result = await _eval(session, schema.id, body.answers, layer_ids or None)
    return result.to_dict()


@router.post("/visibility/rules")
async def create_visibility_rule(
    body: CreateVisibilityRuleRequest,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, Any]:
    """Create a new visibility rule."""
    from app.db.models.schema import ConfigSchema
    from app.db.models.visibility import VisibilityRule
    from sqlalchemy import select

    # Get active schema
    res = await session.execute(
        select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
    )
    schema = res.scalar_one_or_none()
    if schema is None:
        raise HTTPException(status_code=404, detail="No active schema found")

    # Validate target_type
    if body.target_type not in ("step", "field"):
        raise HTTPException(status_code=400, detail="target_type must be 'step' or 'field'")
    if body.operator not in ("equals", "not_equals", "in", "not_in", "is_empty", "is_not_empty"):
        raise HTTPException(status_code=400, detail="Invalid operator")
    if body.action not in ("show", "hide"):
        raise HTTPException(status_code=400, detail="action must be 'show' or 'hide'")

    rule = VisibilityRule(
        schema_id=schema.id,
        target_type=body.target_type,
        target_step_key=body.target_step_key,
        target_field_path=body.target_field_path,
        depends_on_field_path=body.depends_on_field_path,
        operator=body.operator,
        value_json=body.value,
        action=body.action,
        priority=body.priority,
        created_by=_user.username,
        updated_by=_user.username,
    )
    session.add(rule)
    await session.flush()

    return {
        "id": rule.id,
        "target_type": rule.target_type,
        "target_step_key": rule.target_step_key,
        "target_field_path": rule.target_field_path,
        "depends_on_field_path": rule.depends_on_field_path,
        "operator": rule.operator,
        "value": rule.value_json,
        "action": rule.action,
        "priority": rule.priority,
    }


@router.delete("/visibility/rules/{rule_id}")
async def delete_visibility_rule(
    rule_id: int,
    _user: AuthUser = Depends(require_config_editor),
    session: AsyncSession = Depends(_require_db_session),
) -> dict[str, str]:
    """Delete a visibility rule."""
    from app.db.models.visibility import VisibilityRule

    rule = await session.get(VisibilityRule, rule_id)
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")

    await session.delete(rule)
    await session.flush()
    return {"status": "deleted"}
