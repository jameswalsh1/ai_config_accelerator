from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Any, AsyncGenerator, Literal, cast

from app.services.auth import AuthUser, require_config_editor, require_audit_viewer
from app.services.config_loader_composable import (
    load_composable_config,
    get_available_tools,
    get_available_languages,
    get_available_steps,
    get_coverage_matrix,
)
from app.services.config_editor import get_editable_step
from app.services.config_patcher import update_field_metadata, ConfigNotFoundError, add_preset_to_field, remove_preset_from_field, remove_field_override
from app.services.config_validator import validate_language_override, validate_tool_override, validate_step_id_exists, validate_field_id_exists, SchemaValidationError
from app.services.config_persistence import create_language_config, get_language_tags, ValidationError as PersistenceValidationError
from app.services.audit_log import read_audit_log
from app.services.version_history import list_versions, get_version, get_version_data
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
# Optional DB session dependency
# ---------------------------------------------------------------------------


async def _optional_db_session() -> AsyncGenerator[Any, None]:
    """Yield an AsyncSession when CONFIG_SOURCE=database, else yield None.

    This avoids requiring a live database connection when the app is running
    in JSON mode.
    """
    from app.settings import get_config_source_settings

    if get_config_source_settings().config_source == "database":
        from app.db.session import get_db_session

        async for session in get_db_session():
            yield session
    else:
        yield None


def _is_db_mode() -> bool:
    from app.settings import get_config_source_settings

    return get_config_source_settings().config_source == "database"


@router.get("/edit")
async def get_editable_config_slice(
    tool: str = Query(..., description="Tool ID (e.g., 'claude', 'copilot', 'cursor')"),
    language: str = Query(..., description="Language ID (e.g., 'python', 'java', 'javascript')"),
    step_id: str = Query(..., description="Step ID to fetch editable portion for"),
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """Get editable configuration slice for a specific step + language.

    Fetches the editable portion of config for a specific step, including:
    - All fields in the step
    - Current overrides with source tracking
    - Editability status (free, locked, suggested, defaulted)
    - Clear indication of which values are:
      * default (from schema.json)
      * overridden (from tool/language/combo layer)
      * locked (read-only)

    Response includes:
    - step: Full step definition with enhanced field metadata
    - source_tracking: Summary of override sources used

    Args:
        tool: Tool identifier (e.g., 'claude', 'copilot', 'cursor')
        language: Language identifier (e.g., 'python', 'java', 'javascript')
        step_id: Step ID to extract (e.g., 'engineering_standards', 'language_selection')

    Returns:
        Dictionary containing editable step with override metadata

    Raises:
        HTTPException 400: If tool/language/step invalid or validation fails
        HTTPException 404: If step_id not found in configuration
        HTTPException 500: For internal errors

    Example:
        GET /config/edit?tool=claude&language=python&step_id=engineering_standards

        Returns:
        {
            "step": {
                "id": "engineering_standards",
                "title": "Engineering Standards",
                "fields": [
                    {
                        "id": "coding_conventions",
                        "type": "textarea",
                        "label": "Coding Conventions",
                        "default": "PEP8",
                        "editability": "free",
                        "is_locked": false,
                        "is_default": false,
                        "override_source": "language:python",
                        "source_file": "languages/python.json",
                        "presets": [...],
                        ...
                    }
                ]
            },
            "source_tracking": {
                "total_fields": 5,
                "by_source": {
                    "schema.json": 2,
                    "tools/claude.json": 1,
                    "languages/python.json": 2
                },
                "by_editability": {"free": 4, "locked": 1},
                "locked_fields": 1,
                "default_fields": 2,
                "overridden_fields": 3
            }
        }
    """
    try:
        if db is not None:
            from app.services.config_db_repository import DatabaseConfigReadRepository
            repo = DatabaseConfigReadRepository(db)
            resolved_dict = await repo.load_resolved_config(tool, language)
        else:
            # Load fully resolved config
            resolved_dict = load_composable_config(tool, language)

        # Extract editable step with metadata
        result = get_editable_step(resolved_dict, step_id)

        return result
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Config not found for tool '{tool}' and language '{language}': {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading editable config: {str(e)}"
        )


@router.post("/update")
async def update_field_config(
    payload: UpdateFieldRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """
    Update field configuration metadata.

    Updates the default value and editability of a specific field in an override file.
    Triggers validation of the updated configuration.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "package_manager",
            "changes": {
                "default": "uv",
                "editable": false
            }
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        scope_str = payload.scope
        target_str = payload.target
        tool_str = payload.tool
        language_str = payload.language
        step_id_str = payload.step_id
        field_id_str = payload.field_id
        changes = payload.changes

        # Save-time reference validation
        try:
            validate_field_id_exists(step_id_str, field_id_str)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        # Transform changes: map 'editable' boolean to 'editability' string
        transformed_changes: dict[str, Any] = {}
        for key, value in changes.items():
            if key == "editable":
                transformed_changes["editability"] = "free" if value else "locked"
            else:
                transformed_changes[key] = value

        if db is not None:
            from app.services.config_db_write_repository import DatabaseConfigWriteRepository, DatabaseConfigWriteError, FieldNotFoundError, LayerNotFoundError
            from app.services.config_db_repository import DatabaseConfigReadRepository
            write_repo = DatabaseConfigWriteRepository(db)
            await write_repo.update_field_metadata(scope_str, target_str, step_id_str, field_id_str, transformed_changes, actor=_user.username)
            await db.commit()
            read_repo = DatabaseConfigReadRepository(db)
            resolved_dict = await read_repo.load_resolved_config(tool_str, language_str)
        else:
            # Update the override file
            updated_config = update_field_metadata(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, transformed_changes, actor=_user.username)

            # Validate the updated config
            if scope_str == "language":
                validate_language_override(updated_config)
            elif scope_str == "tool":
                validate_tool_override(updated_config)

            resolved_dict = load_composable_config(tool_str, language_str)

        result = get_editable_step(resolved_dict, step_id_str)
        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(status_code=404, detail=f"Config file not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error updating config: {str(e)}")


@router.post("/reset")
async def reset_field_to_base(
    payload: ResetFieldRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """
    Reset a field to its base/tool defaults by removing overrides.

    Removes the field override from the specified scope, allowing the field
    to revert to base schema or tool defaults.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "coding_conventions",
            "override_type": "metadata"  // optional, defaults to "metadata"
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        scope_str = payload.scope
        target_str = payload.target
        tool_str = payload.tool
        language_str = payload.language
        step_id_str = payload.step_id
        field_id_str = payload.field_id
        override_type_str = payload.override_type

        # Save-time reference validation
        try:
            validate_field_id_exists(step_id_str, field_id_str)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        if db is not None:
            from app.services.config_db_write_repository import DatabaseConfigWriteRepository
            from app.services.config_db_repository import DatabaseConfigReadRepository
            write_repo = DatabaseConfigWriteRepository(db)
            await write_repo.reset_field_override(scope_str, target_str, step_id_str, field_id_str, override_type_str, actor=_user.username)
            await db.commit()
            read_repo = DatabaseConfigReadRepository(db)
            resolved_dict = await read_repo.load_resolved_config(tool_str, language_str)
        else:
            updated_config = remove_field_override(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, cast(Literal["metadata", "structure"], override_type_str), actor=_user.username)
            resolved_dict = load_composable_config(tool_str, language_str)

        result = get_editable_step(resolved_dict, step_id_str)
        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(status_code=404, detail=f"Config file not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error resetting field: {str(e)}")


@router.post("/presets/add")
async def add_preset(
    payload: AddPresetRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """
    Add a preset to a field.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "coding_conventions",
            "preset": {
                "label": "PEP8",
                "value": "PEP8",
                "description": "Python Enhancement Proposal 8",
                "mode": "append",
                "tags": ["python"]
            },
            "position": 0  // optional, defaults to append
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        scope_str = payload.scope
        target_str = payload.target
        tool_str = payload.tool
        language_str = payload.language
        step_id_str = payload.step_id
        field_id_str = payload.field_id
        preset_dict: dict[str, Any] = payload.preset.model_dump(exclude_none=True)
        position = payload.position

        # Save-time reference validation
        try:
            validate_field_id_exists(step_id_str, field_id_str)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        if db is not None:
            from app.services.config_db_write_repository import DatabaseConfigWriteRepository
            from app.services.config_db_repository import DatabaseConfigReadRepository
            write_repo = DatabaseConfigWriteRepository(db)
            await write_repo.add_preset(scope_str, target_str, step_id_str, field_id_str, preset_dict, position, actor=_user.username)
            await db.commit()
            read_repo = DatabaseConfigReadRepository(db)
            resolved_dict = await read_repo.load_resolved_config(tool_str, language_str)
        else:
            updated_config = add_preset_to_field(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, preset_dict, position, actor=_user.username)
            resolved_dict = load_composable_config(tool_str, language_str)

        result = get_editable_step(resolved_dict, step_id_str)
        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(status_code=404, detail=f"Config file not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding preset: {str(e)}")


@router.post("/presets/remove")
async def remove_preset(
    payload: RemovePresetRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """
    Remove a preset from a field.

    Payload:
        {
            "scope": "language|tool|override",
            "target": "python|claude|etc",
            "tool": "claude",
            "language": "python",
            "step_id": "engineering_standards",
            "field_id": "coding_conventions",
            "preset_label": "PEP8",  // optional, if not provided use position
            "position": 0  // optional, takes precedence over preset_label
        }

    Returns:
        Updated editable config slice for the step

    Raises:
        HTTPException 400: If validation fails or invalid parameters
        HTTPException 404: If target file not found
        HTTPException 500: For internal errors
    """
    try:
        scope_str = payload.scope
        target_str = payload.target
        tool_str = payload.tool
        language_str = payload.language
        step_id_str = payload.step_id
        field_id_str = payload.field_id
        preset_label = payload.preset_label
        position = payload.position

        # Save-time reference validation
        try:
            validate_field_id_exists(step_id_str, field_id_str)
        except SchemaValidationError as e:
            raise HTTPException(status_code=422, detail=str(e))

        if db is not None:
            from app.services.config_db_write_repository import DatabaseConfigWriteRepository
            from app.services.config_db_repository import DatabaseConfigReadRepository
            write_repo = DatabaseConfigWriteRepository(db)
            await write_repo.remove_preset(scope_str, target_str, step_id_str, field_id_str, preset_label, position, actor=_user.username)
            await db.commit()
            read_repo = DatabaseConfigReadRepository(db)
            resolved_dict = await read_repo.load_resolved_config(tool_str, language_str)
        else:
            updated_config = remove_preset_from_field(cast(Literal["tool", "language", "override"], scope_str), target_str, step_id_str, field_id_str, preset_label, position, actor=_user.username)
            resolved_dict = load_composable_config(tool_str, language_str)

        result = get_editable_step(resolved_dict, step_id_str)
        return result

    except (FileNotFoundError, ConfigNotFoundError) as e:
        raise HTTPException(status_code=404, detail=f"Config file not found: {str(e)}")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error removing preset: {str(e)}")


@router.get("/tools")
def list_available_tools(
    _user: AuthUser = Depends(require_config_editor),
) -> list[dict[str, str]]:
    """Get list of available tools."""
    return get_available_tools()


@router.get("/coverage")
def get_tool_language_coverage(
    _user: AuthUser = Depends(require_config_editor),
) -> dict[str, Any]:
    """Return the tool × language coverage matrix.

    Each cell reports whether the language configuration has field overrides
    relevant to that tool's visible steps.

    Returns:
        {
            "tools":     [{"id": ..., "title": ...}, ...],
            "languages": [{"id": ..., "title": ...}, ...],
            "matrix":    { tool_id: { language_id: { "status", "field_count", "fields" } } }
        }

    Status values:
        - "full":    ≥ 2 relevant field overrides
        - "partial": exactly 1 relevant field override
        - "none":    no relevant field overrides
    """
    return get_coverage_matrix()


@router.get("/languages")
def list_available_languages(
    _user: AuthUser = Depends(require_config_editor),
) -> list[dict[str, str]]:
    """Get list of available languages."""
    return get_available_languages()


@router.post("/languages")
async def create_language(
    payload: CreateLanguageRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """Create a new language configuration.

    Returns:
        The newly created language config dict.

    Raises:
        HTTPException 400: language_id invalid or already exists
        HTTPException 500: Write failure
    """
    try:
        if db is not None:
            from app.services.config_db_write_repository import DatabaseConfigWriteRepository, DatabaseConfigWriteError
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
        else:
            new_config = create_language_config(
                title=payload.title,
                description=payload.description,
                based_on=payload.based_on,
                tag_remap=payload.tag_remap,
            )
            return new_config
    except PersistenceValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to create language: {e}")


@router.get("/languages/{language_id}/tags")
def get_language_tag_list(
    language_id: str,
    _user: AuthUser = Depends(require_config_editor),
) -> list[str]:
    """Return the unique tags used in presets for a language config.

    Useful for pre-populating a tag-remap UI when cloning a language.

    Returns:
        Sorted list of unique tag strings.

    Raises:
        HTTPException 404: Language not found.
    """
    try:
        return get_language_tags(language_id)
    except PersistenceValidationError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/steps")
def list_available_steps(
    tool: str = Query(..., description="Tool ID"),
    language: str = Query(..., description="Language ID"),
    _user: AuthUser = Depends(require_config_editor),
) -> list[dict[str, str]]:
    """Get list of available steps for a tool/language combination."""
    return get_available_steps(tool, language)


@router.get("/audit")
async def get_audit_log(
    limit: int = Query(default=50, ge=1, le=500, description="Max entries to return"),
    offset: int = Query(default=0, ge=0, description="Entries to skip (pagination)"),
    scope: str | None = Query(default=None, description="Filter by scope (language|tool|override)"),
    target: str | None = Query(default=None, description="Filter by target (e.g. 'python', 'claude')"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """Return a paginated, newest-first view of the audit log.

    Each entry records what config file changed, who changed it, when,
    and a full structured diff of what was different.

    Returns:
        {
            "entries": [
                {
                    "timestamp": "2026-04-28T14:30:00Z",
                    "action":    "update",
                    "scope":     "language",
                    "target":    "python",
                    "file":      "backend/app/data/wizard_configs/languages/python.json",
                    "actor":     "system",
                    "diff_summary": "step 'claude_md': 1 field(s) modified",
                    "diff":      { ... }
                },
                ...
            ],
            "total": 42
        }
    """
    if db is not None:
        from app.services.config_db_audit_service import read_db_audit_log
        return await read_db_audit_log(db, limit=limit, offset=offset, scope=scope, target=target)
    return read_audit_log(limit=limit, offset=offset, scope=scope, target=target)


# ---------------------------------------------------------------------------
# Version history endpoints
# ---------------------------------------------------------------------------

@router.get("/history")
async def get_config_history(
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier, e.g. 'python' or 'claude'"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_optional_db_session),
) -> list[dict[str, Any]]:
    """List all versions for a scope+target, newest first."""
    if db is not None:
        from app.services.config_db_version_service import db_list_versions
        return await db_list_versions(db, scope, target)
    return list_versions(scope, target)


@router.get("/history/diff")
async def diff_config_versions(
    scope: str = Query(..., description="Scope: tool|language|override"),
    target: str = Query(..., description="Target identifier, e.g. 'python' or 'claude'"),
    v1: int = Query(..., description="First version number"),
    v2: int = Query(..., description="Second version number"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """Compute the diff between two versions.

    Returns the structured diff from config_diff plus the version metadata.
    """
    from app.services.config_diff import compare_configs, diff_to_dict

    try:
        if db is not None:
            from app.services.config_db_version_service import db_get_version_data
            data1 = await db_get_version_data(db, scope, target, v1)
            data2 = await db_get_version_data(db, scope, target, v2)
        else:
            data1 = get_version_data(scope, target, v1)
            data2 = get_version_data(scope, target, v2)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))

    diff_obj = compare_configs(data1, data2)
    return {
        "v1": v1,
        "v2": v2,
        "scope": scope,
        "target": target,
        "diff": diff_to_dict(diff_obj),
    }


@router.post("/history/restore")
async def restore_config_version(
    payload: RestoreVersionRequest,
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """Restore a previous config version snapshot (database mode only).

    Loads the requested ConfigVersion and writes restore audit/version records.
    Returns the restored data snapshot.

    Raises:
        HTTPException 400: If restore is attempted in JSON mode
        HTTPException 404: If version not found
        HTTPException 500: For internal errors
    """
    if db is None:
        raise HTTPException(
            status_code=400,
            detail="Config restore is only supported in database mode (CONFIG_SOURCE=database)",
        )
    try:
        from app.services.config_db_write_repository import DatabaseConfigWriteRepository, DatabaseConfigWriteError
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
    target: str = Query(..., description="Target identifier, e.g. 'python' or 'claude'"),
    _user: AuthUser = Depends(require_audit_viewer),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """Return the full envelope (metadata + data) for a specific version."""
    try:
        if db is not None:
            from app.services.config_db_version_service import db_get_version
            return await db_get_version(db, scope, target, version)
        return get_version(scope, target, version)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))


# ---------------------------------------------------------------------------
# Ticket 19 — Config source diagnostics
# ---------------------------------------------------------------------------

@router.get("/diagnostics")
async def get_config_diagnostics(
    _user: AuthUser = Depends(require_config_editor),
    db: Any = Depends(_optional_db_session),
) -> dict[str, Any]:
    """Return current config source and database readiness information.

    Useful for operators to confirm which config source is active and
    whether the database config is ready for use.

    Returns:
        {
            "config_source": "json" | "database",
            "database_config_ready": true | false,
            "active_schema": "2.0",    // only in db mode
            "tools": 3,                // only in db mode
            "languages": 6,            // only in db mode
            "layers": { ... }          // only in db mode
        }
    """
    from app.settings import get_config_source_settings
    config_source = get_config_source_settings().config_source

    if db is None:
        return {"config_source": config_source, "database_config_ready": False}

    try:
        from sqlalchemy import func, select
        from app.db.models.schema import ConfigSchema
        from app.db.models.tool import AITool
        from app.db.models.language import Language
        from app.db.models.layer import ConfigLayer

        schema_res = await db.execute(
            select(ConfigSchema).where(ConfigSchema.status == "active").limit(1)
        )
        active_schema = schema_res.scalar_one_or_none()

        if active_schema is None:
            return {
                "config_source": config_source,
                "database_config_ready": False,
                "reason": "no active schema",
            }

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
            "config_source": config_source,
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
        return {
            "config_source": config_source,
            "database_config_ready": False,
            "reason": str(e),
        }