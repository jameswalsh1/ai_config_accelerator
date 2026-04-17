import json
from copy import deepcopy
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


def _merge_language_overrides(base_config: dict[str, Any], language_config: dict[str, Any], tool_id: str | None = None) -> dict[str, Any]:
    """Merge language-specific step_overrides into base config, tagging presets with language.
    
    Args:
        base_config: The base configuration to merge into
        language_config: Language-specific configuration with step_overrides
        tool_id: Optional tool ID to filter applies_to_tools. If provided, only applies
                overrides where applies_to_tools includes this tool (or if applies_to_tools
                is not specified).
    """
    config = deepcopy(base_config)
    language = language_config.get("language", "")
    
    # Handle step_overrides from language config
    if "step_overrides" in language_config:
        for override in language_config["step_overrides"]:
            # Check if this override applies to the current tool
            applies_to = override.get("applies_to_tools")
            if applies_to and tool_id and tool_id not in applies_to:
                continue
            
            step_id = override.get("step_id")
            field_id = override.get("field_id")
            presets_to_add = override.get("presets_to_add", [])
            
            if not step_id or not field_id or not presets_to_add:
                continue
            
            # Find the step in config steps
            for step in config.get("steps", []):
                if step.get("id") == step_id:
                    # Find the field in the step
                    for field in step.get("fields", []):
                        if field.get("id") == field_id:
                            # Tag each preset with the language and append
                            if "presets" not in field:
                                field["presets"] = []
                            for preset in presets_to_add:
                                if isinstance(preset, dict):
                                    # Add language tag to each preset
                                    if "tags" not in preset:
                                        preset["tags"] = []
                                    if language and language not in preset["tags"]:
                                        preset["tags"].append(language)
                            field["presets"].extend(presets_to_add)
                            break
                    break
    
    return config


def _load_modular_config(config_id: str) -> dict[str, Any] | None:
    """Load a config from a modular directory structure (base + language variants)."""
    config_dir = DATA_DIR / config_id
    if not config_dir.is_dir():
        return None
    
    base_file = config_dir / "_base.json"
    if not base_file.exists():
        return None
    
    # Load base config
    with base_file.open(encoding="utf-8") as f:
        base_config = json.load(f)
    
    # Load and merge language-specific configs
    languages_dir = config_dir / "languages"
    if languages_dir.is_dir():
        for lang_file in sorted(languages_dir.glob("*.json")):
            with lang_file.open(encoding="utf-8") as f:
                lang_config = json.load(f)
            base_config = _merge_language_overrides(base_config, lang_config)
    
    return base_config


def _load_all() -> list[WizardConfig]:
    configs: list[WizardConfig] = []
    loaded_ids = set()
    
    # First, try to load modular configs from directories
    for dir_path in sorted(DATA_DIR.iterdir()):
        if dir_path.is_dir() and not dir_path.name.startswith("_"):
            # Check if this is a modular config directory
            base_file = dir_path / "_base.json"
            if base_file.exists():
                with base_file.open(encoding="utf-8") as f:
                    config_data = json.load(f)
                config_id = config_data.get("id")
                tool_id = dir_path.name  # Use directory name as tool_id
                
                # Merge tool-specific language overrides
                languages_dir = dir_path / "languages"
                if languages_dir.is_dir():
                    for lang_file in sorted(languages_dir.glob("*.json")):
                        with lang_file.open(encoding="utf-8") as f:
                            lang_config = json.load(f)
                        config_data = _merge_language_overrides(config_data, lang_config)
                
                # Merge shared language overrides (from root /languages/ directory)
                shared_languages_dir = DATA_DIR / "languages"
                if shared_languages_dir.is_dir():
                    for lang_file in sorted(shared_languages_dir.glob("*.json")):
                        with lang_file.open(encoding="utf-8") as f:
                            lang_config = json.load(f)
                        config_data = _merge_language_overrides(config_data, lang_config, tool_id=tool_id)
                
                # Resolve preset files
                resolved = _resolve_preset_files(config_data)
                configs.append(WizardConfig.model_validate(resolved))
                loaded_ids.add(config_id)
    
    # Then, load root-level JSON files (for backward compatibility)
    # But skip if we already loaded a modular version
    for path in sorted(DATA_DIR.glob("*.json")):
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        config_id = data.get("id")
        if config_id not in loaded_ids:
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


def get_config_with_language_filter(config_id: str, language: str) -> WizardConfig | None:
    """Get a config with presets filtered based on the selected language.
    
    Presets are filtered to include only those with:
    - No language tags (universal/applicable to all languages)
    - A tag matching the selected language
    
    This allows the frontend to show language-aware preset suggestions.
    """
    config = get_config(config_id)
    if not config or not language:
        return config
    
    # Deep copy to avoid modifying cached config
    config_copy = deepcopy(config)
    
    # Filter presets in all fields across all steps
    for step in config_copy.steps:
        for field in step.fields:
            if field.presets:
                # Keep presets with no tags OR presets with tag matching language
                field.presets = [
                    p for p in field.presets
                    if not p.tags or language in p.tags
                ]
            # Recursively handle nested fields in repeatable_group
            if field.fields:
                _filter_nested_presets(field.fields, language)
    
    return config_copy


def _filter_nested_presets(fields: list, language: str) -> None:
    """Helper to recursively filter presets in nested field structures."""
    for field in fields:
        if field.presets:
            field.presets = [
                p for p in field.presets
                if not p.tags or language in p.tags
            ]
        if field.fields:
            _filter_nested_presets(field.fields, language)
