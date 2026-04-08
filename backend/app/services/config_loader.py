import json
from pathlib import Path
from typing import Any

from app.models.wizard import WizardConfig, WizardConfigSummary

DATA_DIR = Path(__file__).parent.parent / "data" / "wizard_configs"


def _resolve_preset_files(data: Any) -> Any:
    if isinstance(data, dict):
        if "preset_files" in data and isinstance(data["preset_files"], list):
            presets = list(data.get("presets", []))
            for preset_path in data["preset_files"]:
                preset_file = DATA_DIR / preset_path
                if not preset_file.exists():
                    raise FileNotFoundError(f"Preset file not found: {preset_file}")
                with preset_file.open(encoding="utf-8") as f:
                    file_presets = json.load(f)
                if not isinstance(file_presets, list):
                    raise ValueError(f"Preset file must contain a JSON array: {preset_file}")
                presets.extend(file_presets)
            data["presets"] = presets
        return {key: _resolve_preset_files(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_resolve_preset_files(value) for value in data]
    return data


def _load_all() -> list[WizardConfig]:
    configs: list[WizardConfig] = []
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        resolved = _resolve_preset_files(data)
        configs.append(WizardConfig.model_validate(resolved))
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
