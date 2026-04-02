from typing import Any

from app.enums import FieldType, OutputFormat
from app.models.wizard import WizardConfig, WizardStep

# Answers shape: { step_id: { field_id: value } }
type Answers = dict[str, dict[str, Any]]


def _get(step_answers: dict[str, Any], field_id: str, default: Any = None) -> Any:
    v = step_answers.get(field_id)
    return v if v is not None else default


# ---------------------------------------------------------------------------
# Format renderers
# ---------------------------------------------------------------------------


def _render_text(step: WizardStep, step_answers: dict[str, Any]) -> str:
    """Generic key: value text rendering — original behaviour, kept for demo/fallback."""
    lines: list[str] = [f"# {step.title}", ""]
    for field in step.fields:
        value = _get(step_answers, field.id, field.default)
        if value is None:
            continue
        if isinstance(value, list):
            lines.append(f"{field.label}:")
            for item in value:
                lines.append(f"  - {item}")
        elif isinstance(value, bool):
            lines.append(f"{field.label}: {'true' if value else 'false'}")
        else:
            lines.append(f"{field.label}: {value}")
    return "\n".join(lines)


def _render_markdown(step: WizardStep, step_answers: dict[str, Any]) -> str:
    """Proper Markdown: `# {heading}` + `## {label}` section per textarea field."""
    heading = _get(step_answers, "heading", step.title)
    lines: list[str] = [f"# {heading}", ""]

    for field in step.fields:
        if field.id == "heading":
            continue
        value = _get(step_answers, field.id, field.default)
        has_content = bool(value) or isinstance(value, bool) or bool(field.locked_value)
        if not has_content:
            continue

        if field.type == FieldType.textarea:
            locked = (field.locked_value or "").strip()
            user = str(value).strip() if value else ""
            text = "\n".join(filter(None, [locked, user]))
            if text:
                lines += [f"## {field.label}", "", text, ""]
        elif field.type in (FieldType.text, FieldType.select):
            lines += [f"**{field.label}:** {value}", ""]
        elif field.type == FieldType.multi_select:
            items = value if isinstance(value, list) else [value]
            if items:
                lines += [f"## {field.label}", ""] + [f"- {i}" for i in items] + [""]
        elif field.type == FieldType.checkbox and value:
            lines += [f"- {field.label}: enabled", ""]

    return "\n".join(lines).rstrip() + "\n"


def _render_markdown_frontmatter(step: WizardStep, step_answers: dict[str, Any]) -> str:
    """Fields with frontmatter=True → YAML block; remaining fields → Markdown body."""
    fm_lines: list[str] = []
    body_lines: list[str] = []

    for field in step.fields:
        value = _get(step_answers, field.id, field.default)
        # Allow through if there is a user value OR a locked_value to emit
        user_empty = value is None or (value == "" and not isinstance(value, bool))
        if user_empty and not field.locked_value:
            continue

        key = field.frontmatter_key or field.id

        if field.frontmatter:
            if isinstance(value, bool):
                fm_lines.append(f"{key}: {'true' if value else 'false'}")
            elif isinstance(value, list):
                joined = ", ".join(f'"{str(v)}"' for v in value)
                fm_lines.append(f"{key}: [{joined}]")
            else:
                fm_lines.append(f'{key}: "{str(value).strip()}"')
        else:
            if field.type == FieldType.textarea:
                locked = (field.locked_value or "").strip()
                user = str(value).strip() if value else ""
                text = "\n".join(filter(None, [locked, user]))
                if text:
                    body_lines += [text, ""]
            elif field.type in (FieldType.text, FieldType.select):
                body_lines += [f"**{field.label}:** {value}", ""]
            elif field.type == FieldType.multi_select:
                items = value if isinstance(value, list) else [value]
                if items:
                    body_lines += [f"## {field.label}", ""] + [f"- {i}" for i in items] + [""]

    parts: list[str] = []
    if fm_lines:
        parts += ["---"] + fm_lines + ["---", ""]
    parts += body_lines

    return "\n".join(parts).rstrip() + "\n"


def _render_verbatim(step: WizardStep, step_answers: dict[str, Any]) -> str:
    """Return the 'content' field verbatim; falls back to the first non-empty textarea."""
    for field in step.fields:
        if field.id == "content" or field.type == FieldType.textarea:
            value = _get(step_answers, field.id, field.default)
            locked = (field.locked_value or "").strip()
            user = str(value).strip() if value else ""
            combined = "\n".join(filter(None, [locked, user]))
            if combined:
                return combined
    return ""


def _render_agent(agent: dict[str, Any]) -> str:
    """Render one agent definition as a Markdown file with YAML frontmatter."""
    fm: list[str] = []
    name = str(agent.get("name", "")).strip()
    description = str(agent.get("description", "")).strip()
    tools = agent.get("tools") or []
    model = str(agent.get("model", "")).strip()
    system_prompt = str(agent.get("system_prompt", "")).strip()

    fm.append(f"name: {name}")
    if description:
        fm.append(f"description: {description}")
    if tools:
        tools_str = ", ".join(f'"{t}"' for t in tools)
        fm.append(f"tools: [{tools_str}]")
    if model:
        fm.append(f"model: {model}")

    parts = ["---"] + fm + ["---", ""]
    if system_prompt:
        parts.append(system_prompt)
    return "\n".join(parts).rstrip() + "\n"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_files(config: WizardConfig, answers: Answers) -> dict[str, str]:
    """Return {output_filename: text_content} built from wizard answers."""
    files: dict[str, list[str]] = {}

    for step in config.steps:
        step_answers = answers.get(step.id, {})

        # agent_list fields generate one file per agent — handle before normal rendering
        agent_fields = [f for f in step.fields if f.type == FieldType.agent_list]
        for field in agent_fields:
            if field.agent_config is None:
                continue
            agents = step_answers.get(field.id)
            if not isinstance(agents, list):
                continue
            for agent_data in agents:
                if not isinstance(agent_data, dict):
                    continue
                agent_name = str(agent_data.get("name", "")).strip()
                if not agent_name:
                    continue
                filename = (
                    f"{field.agent_config.output_dir}{agent_name}{field.agent_config.file_suffix}"
                )
                files[filename] = [_render_agent(agent_data)]

        # skip normal rendering if every field in this step is an agent_list field
        if all(f.type == FieldType.agent_list for f in step.fields):
            continue

        match step.output_format:
            case OutputFormat.markdown:
                block = _render_markdown(step, step_answers)
            case OutputFormat.markdown_frontmatter:
                block = _render_markdown_frontmatter(step, step_answers)
            case OutputFormat.verbatim:
                block = _render_verbatim(step, step_answers)
            case _:  # OutputFormat.text (default)
                block = _render_text(step, step_answers)

        if step.output_file in files:
            files[step.output_file].append(block)
        else:
            files[step.output_file] = [block]

    return {
        filename: "\n\n".join(non_empty) if len(non_empty) > 1 else non_empty[0]
        for filename, blocks in files.items()
        if (non_empty := [b for b in blocks if b])
    }
