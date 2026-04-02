from fastapi import APIRouter, HTTPException

from app.models.wizard import WizardConfig, WizardConfigSummary
from app.services.config_loader import get_all_configs, get_config

router = APIRouter(prefix="/api/wizard", tags=["wizard"])


@router.get("/configs", response_model=list[WizardConfigSummary])
def list_configs() -> list[WizardConfigSummary]:
    return get_all_configs()


@router.get("/config/{config_id}", response_model=WizardConfig)
def get_wizard_config(config_id: str) -> WizardConfig:
    config = get_config(config_id)
    if config is None:
        raise HTTPException(status_code=404, detail=f"Config '{config_id}' not found")
    return config
