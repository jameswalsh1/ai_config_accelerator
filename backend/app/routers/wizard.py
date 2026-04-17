from fastapi import APIRouter, HTTPException

from app.models.wizard import WizardConfig, WizardConfigSummary
from app.services.config_loader import get_all_configs, get_config, get_config_with_language_filter

router = APIRouter(prefix="/api/wizard", tags=["wizard"])


@router.get("/configs", response_model=list[WizardConfigSummary])
def list_configs() -> list[WizardConfigSummary]:
    return get_all_configs()


@router.get("/config/{config_id}", response_model=WizardConfig)
def get_wizard_config(config_id: str, language: str | None = None) -> WizardConfig:
    """Get wizard config, optionally filtered by language.
    
    If language query parameter is provided, presets in fields will be filtered
    to only show those applicable to the selected language.
    """
    if language:
        config = get_config_with_language_filter(config_id, language)
    else:
        config = get_config(config_id)
    
    if config is None:
        raise HTTPException(status_code=404, detail=f"Config '{config_id}' not found")
    return config
