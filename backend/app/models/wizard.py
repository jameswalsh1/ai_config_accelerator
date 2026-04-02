from typing import Any

from pydantic import BaseModel

from app.enums import FieldType, OutputFormat, PresetMode


class FieldOption(BaseModel):
    value: str
    label: str
    description: str | None = None


class Preset(BaseModel):
    label: str
    description: str | None = None
    value: Any
    mode: PresetMode = PresetMode.append


class AgentFieldConfig(BaseModel):
    """Extra metadata for agent_list fields — controls where generated agent files land."""

    output_dir: str  # e.g. ".claude/agents/" or ".github/agents/"
    file_suffix: str = ".md"  # appended after agent name; e.g. ".md" or ".agent.md"
    available_tools: list[str] | None = None
    available_models: list[str] | None = None
    default_model: str | None = None


class WizardField(BaseModel):
    id: str
    type: FieldType
    label: str
    description: str | None = None
    placeholder: str | None = None
    required: bool = False
    options: list[FieldOption] | None = None
    default: Any = None
    rows: int | None = None  # textarea row height hint
    frontmatter: bool = False  # for markdown_frontmatter steps: emit in YAML block
    frontmatter_key: str | None = None  # YAML key name; defaults to field id if frontmatter=True
    screen_hint: str | None = None  # verbose per-field instructional text shown on its own screen
    presets: list[Preset] | None = None  # quick-fill options shown as chips below the field
    locked_value: str | None = (
        None  # read-only best-practice content always prepended to generated output
    )
    agent_config: AgentFieldConfig | None = None  # only for agent_list fields


class WizardStep(BaseModel):
    id: str
    title: str
    description: str | None = None
    hint: str | None = None
    fields: list[WizardField]
    output_file: str
    output_format: OutputFormat = OutputFormat.text


class WizardConfigSummary(BaseModel):
    id: str
    title: str
    description: str
    target: str


class WizardConfig(WizardConfigSummary):
    steps: list[WizardStep]
