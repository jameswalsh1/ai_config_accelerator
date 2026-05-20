from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any

from app.db.deps import require_db_session as _require_db_session
from app.services.auth import AuthUser, require_config_editor, require_audit_viewer
from app.services.config_editor import get_editable_step
from app.services.config_validator import validate_field_id_exists, SchemaValidationError
from app.services.config_db_write_repository import (
    DatabaseConfigWriteRepository,
    DatabaseConfigWriteError,
    LayerNotFoundError,
    FieldNotFoundError,
)
from app.services.config_db_repository import DatabaseConfigReadRepository
from app.models.config_requests import (
    UpdateFieldRequest,
    ResetFieldRequest,
    AddPresetRequest,
    RemovePresetRequest,
    CreateLanguageRequest,
    RestoreVersionRequest,
)

router = APIRouter(prefix="/config", tags=["config"])


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/edit")
async def get_editable_config_slice(
    tool: str = Query(..., description="Tool ID (e.g., 'claude', 'copilot', 'cursor')"),
    language: str = Query(..., description="Language ID (e.g., 'python', 'java', 'javascript')"),
    step_id: str = Query(..., description="Step ID to fetch editable portion for"),
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Get editable configuration slice for a specific step + language."""
    try:
        repo = DatabaseConfigReadRepository(db)
        resolved_dict = await repo.load_resolved_config(tool, language)
        return get_editable_step(resolved_dict, step_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Config not found: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error loading editable config: {e}")


@router.post("/update")
async def update_field_config(
    payload: UpdateFieldRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Update field configuration metadata."""
    try:
        try:
            validate_field_id_exists(payload.step_id, payload.field_id)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        transformed_changes: dict[str, Any] = {}
        for key, value in payload.changes.items():
            if key == "editable":
                transformed_changes["editability"] = "free" if value else "locked"
            else:
                transformed_changes[key] = value

        write_repo = DatabaseConfigWriteRepository(db)
        await write_repo.update_field_metadata(
            payload.scope, payload.target, payload.step_id, payload.field_id,
            transformed_changes, actor=_user.username,
        )
        await db.commit()

        resolved_dict = await DatabaseConfigReadRepository(db).load_resolved_config(payload.tool, payload.language)
        return get_editable_step(resolved_dict, payload.step_id)

    except (LayerNotFoundError, FieldNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseConfigWriteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {e}")


@router.post("/reset")
async def reset_field_to_base(
    payload: ResetFieldRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Reset a field to its base/tool defaults by removing overrides."""
    try:
        try:
            validate_field_id_exists(payload.step_id, payload.field_id)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        write_repo = DatabaseConfigWriteRepository(db)
        await write_repo.reset_field_override(
            payload.scope, payload.target, payload.step_id, payload.field_id,
            payload.override_type, actor=_user.username,
        )
        await db.commit()

        resolved_dict = await DatabaseConfigReadRepository(db).load_resolved_config(payload.tool, payload.language)
        return get_editable_step(resolved_dict, payload.step_id)

    except (LayerNotFoundError, FieldNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseConfigWriteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting field: {e}")


@router.post("/presets/add")
async def add_preset(
    payload: AddPresetRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Add a preset to a field."""
    try:
        try:
            validate_field_id_exists(payload.step_id, payload.field_id)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        preset_dict: dict[str, Any] = payload.preset.model_dump(exclude_none=True)

        write_repo = DatabaseConfigWriteRepository(db)
        await write_repo.add_preset(
            payload.scope, payload.target, payload.step_id, payload.field_id,
            preset_dict, payload.position, actor=_user.username,
        )
        await db.commit()

        resolved_dict = await DatabaseConfigReadRepository(db).load_resolved_config(payload.tool, payload.language)
        return get_editable_step(resolved_dict, payload.step_id)

    except (LayerNotFoundError, FieldNotFoundError) as e:
        raise HTTPException(status_code=404, detail=str(e))
    except DatabaseConfigWriteError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding preset: {e}")


@router.post("/presets/remove")
async def remove_preset(
    payload: RemovePresetRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Remove a preset from a field."""
    try:
        try:
            validate_field_id_exists(payload.step_id, payload.field_id)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        write_repo = DatabaseConfigWriteRepository(db)
        await write_repo.remove_preset(
            payload.scope, payload.target, payload.step_id, payload.field_id,
            payload.preset_label, payload.position, actor=_user.username,
        )
        await db.commit()

        resolved_dict = await DatabaseConfigReadRepository(db).load_resolved_config(payload.tool, payload.language)
        return get_editable_step(resolved_dict, payload.step_id)

    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=f"Config file not found: {e}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing preset: {e}")


@router.get("/tools")
async def list_available_tools(
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> list[dict[str, str]]:
    """Get list of available tools."""
    return await DatabaseConfigReadRepository(db).get_available_tools()


@router.get("/coverage")
async def get_tool_language_coverage(
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Return the tool × language coverage matrix."""
    return await DatabaseConfigReadRepository(db).get_coverage_matrix()


@router.get("/languages")
async def list_available_languages(
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> list[dict[str, str]]:
    """Get list of available languages."""
    return await DatabaseConfigReadRepository(db).get_available_languages()


@router.post("/languages")
async def create_language(
    payload: CreateLanguageRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Create a new language configuration."""
    try:
        language_key = payload.language_id or payload.title.lower().replace(" ", "_")
        write_repo = DatabaseConfigWriteRepository(db)
        lang = await write_repo.create_language(
            language_key=language_key,
            title=payload.title,
            description=payload.description,
            actor=_user.username,
        )
        await db.commit()
        return {
            "language_key": lang.language_key,
            "title": lang.title,
            "description": lang.description,
            "is_active": lang.is_active,
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create language: {e}")


@router.get("/languages/{language_id}/tags")
async def get_language_tag_list(
    language_id: str,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> list[str]:
    """Return the unique tags used in presets for a language config."""
    try:
        return await DatabaseConfigReadRepository(db).get_language_tags(language_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/steps")
async def list_available_steps(
    tool: str = Query(..., description="Tool ID"),
    language: str = Query(..., description="Language ID"),
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> list[dict[str, str]]:
    """Get list of available steps for a tool/language combination."""
    try:
        return await DatabaseConfigReadRepository(db).get_available_steps(tool, language)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/audit")
async def get_audit_log(
    limit: int = Query(default=50, ge=1, le=500, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Entries to skip (pagination)"),
    scope: str | None = Query(default=None, description="Filter by scope"),
    target: str | None = Query(default=None, description="Filter by target"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Return a paginated, newest-first view of the audit log."""
    from app.services.config_db_audit_service import read_db_audit_log
    return await read_db_audit_log(db, limit=limit, offset=offset, scope=scope, target=target)


# ---------------------------------------------------------------------------
# Version history endpoints
# ---------------------------------------------------------------------------


@router.get("/history")
async def get_config_history(
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier, e.g. 'python' or 'claude'"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_require_db_session),
) -> list[dict[str, Any]]:
    """List all versions for a scope+target, newest first."""
    from app.services.config_db_version_service import db_list_versions
    return await db_list_versions(db, scope, target)


@router.get("/history/diff")
async def diff_config_versions(
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier"),
    v1: int = Query(..., description="First version number"),
    v2: int = Query(..., description="Second version number"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Compute the diff between two versions."""
    from app.services.config_diff import compare_configs, diff_to_dict
    from app.services.config_db_version_service import db_get_version_data

    try:
        data1 = await db_get_version_data(db, scope, target, v1)
        data2 = await db_get_version_data(db, scope, target, v2)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    diff_obj = compare_configs(data1, data2)
    return {"v1": v1, "v2": v2, "scope": scope, "target": target, "diff": diff_to_dict(diff_obj)}


@router.post("/history/restore")
async def restore_config_version(
    payload: RestoreVersionRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Restore a previous config version snapshot."""
    from app.services.config_db_write_repository import DatabaseConfigWriteRepository, DatabaseConfigWriteError

    try:
        write_repo = DatabaseConfigWriteRepository(db)
        snapshot = await write_repo.restore_version(
            scope=payload.scope,
            target=payload.target,
            version_number=payload.version,
            actor=_user.username,
        )
        await db.commit()
        return {
            "restored": True,
            "scope": payload.scope,
            "target": payload.target,
            "version": payload.version,
            "snapshot": snapshot,
        }
    except DatabaseConfigWriteError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore failed: {e}")


@router.get("/history/{version}")
async def get_config_version(
    version: int,
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Return the full envelope (metadata + data) for a specific version."""
    from app.services.config_db_version_service import db_get_version

    try:
        return await db_get_version(db, scope, target, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Config source diagnostics
# ---------------------------------------------------------------------------


@router.get("/diagnostics")
async def get_config_diagnostics(
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_require_db_session),
) -> dict[str, Any]:
    """Return database readiness information."""
    from sqlalchemy import func, select
    from app.db.models.schema import ConfigSchema
    from app.db.models.tool import AITool
    from app.db.models.language import Language
    from app.db.models.layer import ConfigLayer

    try:
        schema_res = await db.execute(
            select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
        )
        active_schema = schema_res.scalar_one_or_none()

        if active_schema is None:
            return {"config_source": "database", "database_config_ready": False, "reason": "no active schema"}

        tool_count_res = await db.execute(
            select(func.count()).select_from(AITool).where(AITool.is_active.is_(True))
        )
        lang_count_res = await db.execute(
            select(func.count()).select_from(Language).where(Language.is_active.is_(True))
        )
        layer_res = await db.execute(
            select(ConfigLayer.layer_type, func.count())
            .group_by(ConfigLayer.layer_type)
            .where(ConfigLayer.status == "active")
        )
        layers: dict[str, int] = {row[0]: row[1] for row in layer_res}

        return {
            "config_source": "database",
            "database_config_ready": True,
            "active_schema": active_schema.schema_version,
            "tools": tool_count_res.scalar_one(),
            "languages": lang_count_res.scalar_one(),
            "layers": {
                "tool": layers.get("tool", 0),
                "language": layers.get("language", 0),
                "combo": layers.get("combo", 0),
            },
        }
    except Exception as e:
        return {"config_source": "database", "database_config_ready": False, "reason": str(e)}
