import json
from pathlib import Path

from app.models.wizard import WizardConfig, WizardConfigSummary

DATA_DIR = Path(__file__).parent.parent / "data" / "wizard_configs"


def _load_all() -> list[WizardConfig]:
    configs: list[WizardConfig] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        configs.append(WizardConfig.model_validate(data))
    return configs


def get_all_configs() -> list[WizardConfigSummary]:
    return [
        WizardConfigSummary(
            id=c.id,
            title=c.title,
            description=c.description,
            target=c.target,
        )
        for c in _load_all()
    ]


def get_config(config_id: str) -> WizardConfig | None:
    for config in _load_all():
        if config.id == config_id:
            return config
    return None
