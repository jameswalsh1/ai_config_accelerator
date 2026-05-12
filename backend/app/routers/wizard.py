from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any

from app.db.deps import require_db_session as _require_db_session
from app.models.wizard import WizardConfig, WizardConfigSummary
from app.services.config_editor import get_editable_step

router = APIRouter(prefix="/api/wizard", tags=["wizard"])


async def _load_tool_config(db: Any, tool_id: str, language_id: str | None = None) -> WizardConfig:
    """Load a WizardConfig for a tool+language from the database.

    If language_id is None or empty, only tool-layer overrides are applied.
    Raises HTTPException 404 if the tool is not found.
    """
    from sqlalchemy import select
    from app.db.models.tool import AITool
    from app.services.config_db_repository import DatabaseConfigReadRepository

    tool_res = await db.execute(select(AITool).where(AITool.tool_key == tool_id))
    tool_row = tool_res.scalar_one_or_none()
    if tool_row is None:
        raise HTTPException(status_code=404, detail=f"Config '{tool_id}' not found")

    repo = DatabaseConfigReadRepository(db)
    resolved = await repo.load_resolved_config(tool_id, language_id or "")

    config_dict: dict[str, Any] = {
        "id": tool_row.tool_key,
        "title": tool_row.title,
        "description": tool_row.description or "",
        "target": tool_row.tool_key,
        "schema_version": resolved.get("schema_version"),
        "steps": resolved.get("steps", []),
    }
    config = WizardConfig.model_validate(config_dict)
    return config.model_copy(update={"steps": [s for s in config.steps if not s.hidden]})


@router.get("/configs", response_model=list[WizardConfigSummary])
async def list_configs(
    db: Any = Depends(_require_db_session),
) -> list[WizardConfigSummary]:
    """List available wizard configurations (tools)."""
    from sqlalchemy import select
    from app.db.models.tool import AITool

    res = await db.execute(select(AITool).where(AITool.is_active.is_(True)).order_by(AITool.tool_key))
    tools = res.scalars().all()
    return [
        WizardConfigSummary(
            id=t.tool_key,
            title=t.title,
            description=t.description or "",
            target=t.tool_key,
        )
        for t in tools
    ]


@router.get("/config/resolved", response_model=WizardConfig)
async def get_resolved_config(
    tool: str = Query(..., description="Tool ID"),
    language: str = Query(..., description="Language ID"),
    db: Any = Depends(_require_db_session),
) -> WizardConfig:
    """Get fully resolved wizard config with all overrides applied."""
    try:
        return await _load_tool_config(db, tool, language)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading resolved config: {e}")


@router.get("/config/edit")
async def get_editable_config(
    tool: str = Query(..., description="Tool ID"),
    language: str = Query(..., description="Language ID"),
    step_id: str = Query(..., description="Step ID"),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Get editable configuration slice for a specific step + language."""
    from app.services.config_db_repository import DatabaseConfigReadRepository

    try:
        repo = DatabaseConfigReadRepository(db)
        resolved_dict = await repo.load_resolved_config(tool, language)
        return get_editable_step(resolved_dict, step_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading editable config: {e}")


@router.get("/config/{config_id}", response_model=WizardConfig)
async def get_wizard_config(
    config_id: str,
    language: str | None = None,
    db: Any = Depends(_require_db_session),
) -> WizardConfig:
    """Get wizard config, optionally filtered by language."""
    try:
        return await _load_tool_config(db, config_id, language)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading config: {e}")


@router.get("/presets")
async def get_available_presets(
    tool: str = Query(..., description="Tool ID"),
    language: str = Query(..., description="Language ID"),
    db: Any = Depends(_require_db_session),
) -> dict[str, list[dict[str, Any]]]:
    """Get all available presets for a tool and language combination."""
    from sqlalchemy import select
    from app.db.models.tool import AITool
    from app.services.config_db_repository import DatabaseConfigReadRepository
    from app.services.config_loader_composable import extract_presets_from_config

    tool_res = await db.execute(select(AITool).where(AITool.tool_key == tool).where(AITool.is_active.is_(True)))
    if tool_res.scalar_one_or_none() is None:
        raise HTTPException(status_code=404, detail=f"Tool '{tool}' not found")

    try:
        repo = DatabaseConfigReadRepository(db)
        resolved_dict = await repo.load_resolved_config(tool, language)
        return extract_presets_from_config(resolved_dict, tool, language)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading presets: {e}")
