import io
from pathlib import PurePosixPath
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.db.deps import require_db_session as _require_db_session
from app.models.wizard import WizardConfig
from app.services.file_generator import generate_files
from app.services.zip_service import create_zip

router = APIRouter(prefix="/api", tags=["generate"])

# Map file extensions to a language hint for the frontend syntax highlighter
_EXT_LANGUAGE: dict[str, str] = {
    ".md": "markdown",
    ".json": "json",
    ".toml": "toml",
    ".yaml": "yaml",
    ".yml": "yaml",
    ".mdc": "markdown",
    ".txt": "text",
    ".sh": "bash",
    ".ps1": "powershell",
    ".gitignore": "text",
    ".cursorignore": "text",
    ".cursorindexingignore": "text",
}


def _language_hint(path: str) -> str:
    suffix = PurePosixPath(path).suffix.lower()
    # Files with no suffix (e.g. .gitignore whose name IS the suffix)
    if not suffix:
        name = PurePosixPath(path).name.lower()
        return _EXT_LANGUAGE.get(f".{name}", "text")
    return _EXT_LANGUAGE.get(suffix, "text")


class GenerateRequest(BaseModel):
    config_id: str
    answers: dict[str, dict[str, object]]


class PreviewFile(BaseModel):
    path: str
    content: str
    language: str


class PreviewResponse(BaseModel):
    files: list[PreviewFile]


async def _load_config_from_db(db: Any, config_id: str) -> WizardConfig:
    """Load a WizardConfig from the database for the given tool ID."""
    from sqlalchemy import select
    from app.db.models.tool import AITool
    from app.services.config_db_repository import DatabaseConfigReadRepository

    tool_res = await db.execute(select(AITool).where(AITool.tool_key == config_id))
    tool_row = tool_res.scalar_one_or_none()
    if tool_row is None:
        raise HTTPException(status_code=404, detail=f"Config '{config_id}' not found")

    repo = DatabaseConfigReadRepository(db)
    resolved = await repo.load_resolved_config(config_id, "")

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


@router.post("/generate/preview", response_model=PreviewResponse)
async def preview(request: GenerateRequest, db: Any = Depends(_require_db_session)) -> PreviewResponse:
    """Return the generated file contents without packaging into a ZIP."""
    config = await _load_config_from_db(db, request.config_id)

    raw_files = generate_files(config, request.answers)
    files = [
        PreviewFile(
            path=path,
            content="".join(chunks),
            language=_language_hint(path),
        )
        for path, chunks in raw_files.items()
        if any(c.strip() for c in chunks)  # skip empty files
    ]
    # Sort deterministically: directories first, then alphabetically
    files.sort(key=lambda f: (f.path.count("/"), f.path))
    return PreviewResponse(files=files)


@router.post("/generate")
async def generate(request: GenerateRequest, db: Any = Depends(_require_db_session)) -> StreamingResponse:
    config = await _load_config_from_db(db, request.config_id)

    files = generate_files(config, request.answers)
    zip_bytes = create_zip(files)

    filename = f"{config.id}_config.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
