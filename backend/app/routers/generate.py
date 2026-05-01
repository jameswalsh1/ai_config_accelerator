import io
from pathlib import PurePosixPath

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.config_loader_composable import get_config
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


@router.post("/generate/preview", response_model=PreviewResponse)
def preview(request: GenerateRequest) -> PreviewResponse:
    """Return the generated file contents without packaging into a ZIP."""
    config = get_config(request.config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Config '{request.config_id}' not found")

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
def generate(request: GenerateRequest) -> StreamingResponse:
    config = get_config(request.config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Config '{request.config_id}' not found")

    files = generate_files(config, request.answers)
    zip_bytes = create_zip(files)

    filename = f"{config.id}_config.zip"
    return StreamingResponse(
        io.BytesIO(zip_bytes),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
