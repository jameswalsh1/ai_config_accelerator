import io

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.services.config_loader import get_config
from app.services.file_generator import generate_files
from app.services.zip_service import create_zip

router = APIRouter(prefix="/api", tags=["generate"])


class GenerateRequest(BaseModel):
    config_id: str
    answers: dict[str, dict[str, object]]


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
