from typing import Any, Literal

from pydantic import BaseModel

from app.enums import FieldType, OutputFormat, PresetMode


# Type alias for field editability states
FieldEditability = Literal["free", "locked", "suggested", "defaulted"]


class FieldOption(BaseModel):
    value: str
    label: str
    description: str | None = None


class Preset(BaseModel):
    label: str
    description: str | None = None
    value: Any
    mode: PresetMode = PresetMode.append
    tags: list[str] | None = None


class PreviewTarget(BaseModel):
    target: str
    label: str


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
    preset_files: list[str] | None = None  # load extra presets from external JSON files
    tag_source: bool = False  # values from this field are used as active tag filters for presets
    validation: dict[str, Any] | None = None
    render: bool = True  # if false, field is used for metadata/control but not emitted in output
    fields: list["WizardField"] | None = None
    locked_value: str | None = (
        None  # read-only best-practice content always prepended to generated output
    )
    agent_config: AgentFieldConfig | None = None  # only for agent_list fields
    # ===== Composable Config Metadata =====
    editability: FieldEditability = "free"  # "free" (user can edit), "locked" (readonly),
                                            # "suggested" (recommended), "defaulted" (pre-filled but editable)
    override_source: str | None = None  # tracks which layer (schema/tool/language/override) provided this value
    hidden: bool = False  # if true, field is used for metadata/control but hidden from UI


class WizardStep(BaseModel):
    id: str
    title: str
    description: str | None = None
    hint: str | None = None
    fields: list[WizardField]
    output_file: str
    output_format: OutputFormat = OutputFormat.text
    supported_surfaces: list[str] | None = None


class WizardConfigSummary(BaseModel):
    id: str
    title: str
    description: str
    target: str


class WizardConfig(WizardConfigSummary):
    schema_version: str | None = None
    target_version_constraints: dict[str, str] | None = None
    output_preview_targets: list[PreviewTarget] | None = None
    steps: list[WizardStep]
