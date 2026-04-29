from fastapi import APIRouter, HTTPException, Query
from typing import Any

from app.models.wizard import WizardConfig, WizardConfigSummary
from app.services.config_loader import get_all_configs, get_config, get_config_with_language_filter, _strip_hidden_steps
from app.services.config_loader_composable import load_composable_config, extract_presets_from_config
from app.services.config_editor import get_editable_step

router = APIRouter(prefix="/api/wizard", tags=["wizard"])


@router.get("/configs", response_model=list[WizardConfigSummary])
def list_configs() -> list[WizardConfigSummary]:
    return get_all_configs()


@router.get("/config/resolved", response_model=WizardConfig)
def get_resolved_config(
    tool: str = Query(..., description="Tool ID (e.g., 'claude', 'copilot', 'cursor')"),
    language: str = Query(..., description="Language ID (e.g., 'python', 'java', 'javascript')"),
) -> WizardConfig:
    """Get fully resolved wizard config with all overrides applied.
    
    Merges:
    1. Base schema (canonical configuration)
    2. Tool overrides
    3. Language overrides
    4. Tool + Language combo overrides (if they exist)
    
    Returns complete wizard with:
    - All field metadata (default, editability, hidden, presets)
    - Preset files resolved inline
    - Override effects applied
    - Ready for UI rendering
    
    Args:
        tool: Tool identifier (e.g., 'claude', 'copilot', 'cursor')
        language: Language identifier (e.g., 'python', 'java', 'javascript')
    
    Returns:
        Fully resolved WizardConfig
    
    Raises:
        HTTPException: If tool/language combination not found or validation fails
    """
    try:
        resolved_dict = load_composable_config(tool, language)
        config = WizardConfig.model_validate(resolved_dict)
        return _strip_hidden_steps(config)
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Config not found for tool '{tool}' and language '{language}': {str(e)}"
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config for tool '{tool}' and language '{language}': {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading resolved config: {str(e)}"
        )


@router.get("/config/edit")
def get_editable_config(
    tool: str = Query(..., description="Tool ID (e.g., 'claude', 'copilot', 'cursor')"),
    language: str = Query(..., description="Language ID (e.g., 'python', 'java', 'javascript')"),
    step_id: str = Query(..., description="Step ID to fetch editable portion for"),
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
    
    Examples:
        GET /api/wizard/config/edit?tool=claude&language=python&step_id=engineering_standards
        
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


@router.get("/presets")
def get_available_presets(
    tool: str = Query(..., description="Tool ID (e.g., 'claude', 'copilot', 'cursor')"),
    language: str = Query(..., description="Language ID (e.g., 'python', 'java', 'javascript')"),
) -> dict[str, list[dict[str, Any]]]:
    """Get all available presets for a tool and language combination.
    
    Returns presets categorized as:
    - shared: Presets applicable to multiple tools
    - language: Presets specific to the selected language
    - tool: Presets specific to the selected tool
    
    Each preset includes label, description, value, mode, and tags.
    
    Args:
        tool: Tool identifier (e.g., 'claude', 'copilot', 'cursor')
        language: Language identifier (e.g., 'python', 'java', 'javascript')
    
    Returns:
        Dictionary with 'shared', 'language', and 'tool' keys containing preset lists
    
    Raises:
        HTTPException 400: If tool or language is invalid
        HTTPException 500: For internal errors
    
    Example:
        GET /api/wizard/presets?tool=claude&language=python
        
        Returns:
        {
            "shared": [
                {
                    "label": "Security-first guidance",
                    "description": "Applicable to all LLMs for secure engineering practices.",
                    "value": "## Security-first Guidance\\n...",
                    "mode": "append",
                    "tags": ["copilot", "claude", "cursor"]
                }
            ],
            "language": [
                {
                    "label": "Python PEP 8 + Type Hints",
                    "description": "Strict PEP 8 compliance with comprehensive type hints",
                    "value": "## Code Style & PEP 8\\n...",
                    "mode": "append",
                    "tags": ["python"]
                }
            ],
            "tool": [
                {
                    "label": "Secure baseline",
                    "description": "Block .env + disable telemetry",
                    "value": "{\\n  \\"$schema\\": \\"https://json.schemastore.org/claude-code-settings.json\\",\\n...",
                    "mode": "replace"
                }
            ]
        }
    """
    # Validate tool
    valid_tools = ["claude", "copilot", "cursor"]
    if tool not in valid_tools:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid tool '{tool}'. Valid tools are: {', '.join(valid_tools)}"
        )
    
    # Note: Language validation is not strict - any language string is accepted
    # If no specific language overrides exist, the base config is still valid
    
    try:
        # Load fully resolved config
        resolved_dict = load_composable_config(tool, language)
        
        # Extract and categorize presets
        presets = extract_presets_from_config(resolved_dict, tool, language)
        
        return presets
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid config for tool '{tool}' and language '{language}': {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error loading presets: {str(e)}"
        )
