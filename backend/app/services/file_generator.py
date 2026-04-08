from typing import Any, cast

from app.enums import FieldType, OutputFormat
from app.models.wizard import WizardConfig, WizardField, WizardStep

type Answers = dict[str, dict[str, Any]]


def _get(step_answers: dict[str, Any], field_id: str, default: Any = None) -> Any:
    v = step_answers.get(field_id)
    return v if v is not None else default


def _get_field_value(field, step_answers: dict[str, Any]) -> Any:
    value = _get(step_answers, field.id, field.default)
    return value if value is not None else field.locked_value


def _render_text(step: WizardStep, step_answers: dict[str, Any]) -> str:
    """Generic key: value text rendering — original behaviour, kept for demo/fallback."""
    lines: list[str] = [f"# {step.title}", ""]
    for field in step.fields:
        if field.render is False:
            continue
        value = _get_field_value(field, step_answers)
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
        if field.render is False or field.id == "heading":
            continue
        value = _get_field_value(field, step_answers)
        has_content = bool(value) or isinstance(value, bool)
        if not has_content:
            continue

        if field.type == FieldType.textarea:
            locked = (field.locked_value or "").strip()
            user = str(_get(step_answers, field.id, field.default)).strip() if _get(step_answers, field.id, field.default) else ""
            text = "\n".join(filter(None, [locked, user]))
            if text:
                lines += [f"## {field.label}", "", text, ""]
        elif field.type in (FieldType.text, FieldType.select):
            value_text = str(value).strip()
            lines += [f"**{field.label}:** {value_text}", ""]
        elif field.type == FieldType.multi_select:
            items = value if isinstance(value, list) else [value]
            if items:
                lines += [f"## {field.label}", ""] + [f"- {i}" for i in items] + [""]
        elif field.type == FieldType.checkbox and value:
            lines += [f"- {field.label}: enabled", ""]

    return "\n".join(lines).rstrip() + "\n"


def _render_markdown_frontmatter(step: WizardStep, step_answers: dict[str, Any]) -> str:
    """Fields with frontmatter=True → YAML block; remaining fields → Markdown body.
    
    Note: select/multi_select fields without frontmatter=True are treated as UI-only
    control fields and are not rendered to the output.
    """
    fm_lines: list[str] = []
    body_lines: list[str] = []

    for field in step.fields:
        if field.render is False:
            continue
        value = _get_field_value(field, step_answers)
        # Allow through if there is a user value OR a locked_value to emit
        user_empty = value is None or (value == "" and not isinstance(value, bool))
        if user_empty:
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
            # Skip select/multi_select fields that aren't marked for frontmatter
            # (these are UI control fields, not output fields)
            if field.type in (FieldType.select, FieldType.multi_select):
                continue
            
            if field.type == FieldType.textarea:
                locked = (field.locked_value or "").strip()
                user = str(_get(step_answers, field.id, field.default)).strip() if _get(step_answers, field.id, field.default) else ""
                text = "\n".join(filter(None, [locked, user]))
                if text:
                    body_lines += [text, ""]
            elif field.type == FieldType.text:
                text_value = str(value).strip()
                body_lines += [f"**{field.label}:** {text_value}", ""]

    parts: list[str] = []
    if fm_lines:
        parts += ["---"] + fm_lines + ["---", ""]
    parts += body_lines

    return "\n".join(parts).rstrip() + "\n"


def _render_verbatim(step: WizardStep, step_answers: dict[str, Any]) -> str:
    """Return the 'content' field verbatim; falls back to the first non-empty textarea."""
    for field in step.fields:
        if field.render is False:
            continue
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


def _render_group_entry(fields: list[WizardField], entry: dict[str, Any], title: str, output_format: OutputFormat) -> str:
    class TempStep:
        title: str
        fields: list[WizardField]
        output_format: OutputFormat

    # Filter out nested fields that are marked `render: false` unless the
    # corresponding include flag (nestedField.id + '__include') is truthy in
    # the entry. This ensures optional fields the user did not opt into are
    # omitted from generated output.
    filtered_fields: list[WizardField] = []
    for f in fields:
        # WizardField has a `render` attribute; avoid getattr for static typing.
        if f.render is False:
            include_flag = entry.get(f.id + '__include')
            if not include_flag:
                continue
        filtered_fields.append(f)

    temp_step = TempStep()
    temp_step.title = title
    temp_step.fields = filtered_fields
    temp_step.output_format = output_format
    
    step = cast(WizardStep, temp_step)

    if output_format == OutputFormat.markdown:
        return _render_markdown(step, entry)
    if output_format == OutputFormat.markdown_frontmatter:
        return _render_markdown_frontmatter(step, entry)
    if output_format == OutputFormat.verbatim:
        return _render_verbatim(step, entry)
    return _render_text(step, entry)


def _resolve_directory_output(step: WizardStep, step_answers: dict[str, Any]) -> str | None:
    if not step.output_file.endswith("/"):
        return None

    candidate_keys = [
        "rule_file_name",
        "file_name",
        "filename",
        "prompt_file_name",
        "instruction_file_name",
    ]

    for key in candidate_keys:
        value = step_answers.get(key)
        if isinstance(value, str) and value.strip():
            return f"{step.output_file}{value.strip()}"

    for field in step.fields:
        if field.id in candidate_keys:
            value = step_answers.get(field.id)
            if isinstance(value, str) and value.strip():
                return f"{step.output_file}{value.strip()}"

    default_file_name = step.id.replace("_", "-")
    if step.id == "path_instructions":
        default_file_name = "copilot-instructions"
    elif step.id == "prompt_files":
        default_file_name = "copilot-prompts"
    elif step.id == "agent_skills":
        default_file_name = "copilot-skills"

    suffix = {
        OutputFormat.markdown_frontmatter: ".md",
        OutputFormat.markdown: ".md",
        OutputFormat.verbatim: ".txt",
        OutputFormat.text: ".txt",
    }.get(step.output_format, ".txt")

    return f"{step.output_file}{default_file_name}{suffix}"


def _resolve_directory_output_for_entry(step: WizardStep, entry: dict[str, Any]) -> str | None:
    if not step.output_file.endswith("/"):
        return None

    candidate_keys = [
        "rule_file_name",
        "file_name",
        "filename",
        "prompt_file_name",
        "instruction_file_name",
    ]

    for key in candidate_keys:
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return f"{step.output_file}{value.strip()}"

    return None


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

        repeatable_fields = [f for f in step.fields if f.type == FieldType.repeatable_group]
        for field in repeatable_fields:
            entries = step_answers.get(field.id)
            if not isinstance(entries, list):
                continue
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                entry_filename = _resolve_directory_output_for_entry(step, entry)
                if not entry_filename:
                    continue
                block = _render_group_entry(field.fields or [], entry, step.title, step.output_format)
                if block.strip():
                    files[entry_filename] = [block]

        # If the step only contains agent_list/repeatable_group fields, skip
        # the normal single-file rendering *unless* a repeatable_group field
        # contains a legacy non-list value (textarea style). In that case
        # keep falling through so the old textarea-style answers still
        # produce a single directory output file for backwards compatibility.
        if all(f.type in (FieldType.agent_list, FieldType.repeatable_group) for f in step.fields):
            legacy_present = False
            for f in step.fields:
                if f.type == FieldType.repeatable_group:
                    v = step_answers.get(f.id)
                    if v is not None and not isinstance(v, list):
                        legacy_present = True
                        break
            if not legacy_present:
                continue

        if dir_output := _resolve_directory_output(step, step_answers):
            # detect legacy repeatable_group textarea-style answers
            legacy_present = False
            for f in step.fields:
                if f.type == FieldType.repeatable_group:
                    v = step_answers.get(f.id)
                    if v is not None and not isinstance(v, list):
                        legacy_present = True
                        break

            # if legacy answers present, render using a temporary step that
            # exposes the repeatable_group field as a textarea so existing
            # textarea-style answers are preserved for backward compatibility.
            # Ensure `step_for_render` is typed as `WizardStep` so assigning
            # either the original `step` or a temporary rendering step is
            # type-safe for static checkers.
            step_for_render: WizardStep
            if legacy_present:
                class TempStepForRender:
                    title: str
                    fields: list[WizardField]
                    output_format: OutputFormat

                temp_fields: list[Any] = []
                for f in step.fields:
                    if f.type == FieldType.repeatable_group:
                        class TempField:
                            id: str
                            type: FieldType
                            label: str
                            description: str | None
                            placeholder: Any
                            required: bool
                            render: bool
                            locked_value: Any
                            default: Any
                            rows: int
                            frontmatter: bool
                            frontmatter_key: Any

                        tf = TempField()
                        tf.id = f.id
                        tf.type = FieldType.textarea
                        tf.label = f.label
                        tf.description = f.description
                        tf.placeholder = f.placeholder
                        tf.required = f.required
                        tf.render = True
                        tf.locked_value = None
                        tf.default = None
                        tf.rows = f.rows if f.rows is not None else 4
                        tf.frontmatter = False
                        tf.frontmatter_key = None
                        temp_fields.append(tf)
                    else:
                        temp_fields.append(f)

                temp_step = TempStepForRender()
                temp_step.title = step.title
                temp_step.fields = temp_fields
                temp_step.output_format = step.output_format

                step_for_render = cast(WizardStep, temp_step)
            else:
                step_for_render = step

            if step_for_render.output_format == OutputFormat.verbatim:
                block = _render_verbatim(step_for_render, step_answers)
            else:
                block = (
                    _render_markdown(step_for_render, step_answers)
                    if step_for_render.output_format == OutputFormat.markdown
                    else _render_markdown_frontmatter(step_for_render, step_answers)
                    if step_for_render.output_format == OutputFormat.markdown_frontmatter
                    else _render_text(step_for_render, step_answers)
                )

            if block.strip():
                files[dir_output] = [block]
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
        if (non_empty := [b for b in blocks if b.strip()])
    }
