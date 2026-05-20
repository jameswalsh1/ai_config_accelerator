"""Tests for app/services/file_generator.py."""

from app.enums import FieldType, OutputFormat
from app.models.wizard import (
    AgentFieldConfig,
    WizardConfig,
    WizardField,
    WizardStep,
)
from app.services.file_generator import generate_files

# ---------------------------------------------------------------------------
# Fixtures — minimal in-memory configs so tests don't depend on JSON files
# ---------------------------------------------------------------------------


def _make_step(
    step_id: str,
    output_file: str,
    output_format: OutputFormat,
    fields: list[WizardField],
) -> WizardStep:
    return WizardStep(
        id=step_id,
        title="Test Step",
        fields=fields,
        output_file=output_file,
        output_format=output_format,
    )


def _make_config(steps: list[WizardStep]) -> WizardConfig:
    return WizardConfig(
        id="test",
        title="Test Config",
        description="Test",
        target="test",
        steps=steps,
    )


def _textarea(
    field_id: str, *, locked_value: str | None = None, default: str | None = None
) -> WizardField:
    return WizardField(
        id=field_id,
        type=FieldType.textarea,
        label=field_id.capitalize(),
        locked_value=locked_value,
        default=default,
    )


def _textfield(field_id: str, *, default: str | None = None) -> WizardField:
    return WizardField(
        id=field_id, type=FieldType.text, label=field_id.capitalize(), default=default
    )


# ---------------------------------------------------------------------------
# Markdown renderer
# ---------------------------------------------------------------------------


class TestRenderMarkdown:
    def test_heading_field_becomes_h1(self):
        step = _make_step(
            "s",
            "OUT.md",
            OutputFormat.markdown,
            [
                _textfield("heading"),
                _textarea("overview"),
            ],
        )
        files = generate_files(_make_config([step]), {"s": {"heading": "My Title"}})
        assert files["OUT.md"].startswith("# My Title")

    def test_textarea_with_user_value_renders_section(self):
        step = _make_step("s", "OUT.md", OutputFormat.markdown, [_textarea("body")])
        files = generate_files(_make_config([step]), {"s": {"body": "Hello world"}})
        assert "## Body" in files["OUT.md"]
        assert "Hello world" in files["OUT.md"]

    def test_locked_value_appears_with_no_user_input(self):
        field = _textarea("conventions", locked_value="- Always test your code.")
        step = _make_step("s", "OUT.md", OutputFormat.markdown, [field])
        files = generate_files(_make_config([step]), {})
        assert "- Always test your code." in files["OUT.md"]

    def test_locked_value_prepended_before_user_input(self):
        field = _textarea("conventions", locked_value="- Locked rule.")
        step = _make_step("s", "OUT.md", OutputFormat.markdown, [field])
        files = generate_files(_make_config([step]), {"s": {"conventions": "- User rule."}})
        content = files["OUT.md"]
        assert "- Locked rule." in content
        assert "- User rule." in content
        assert content.index("- Locked rule.") < content.index("- User rule.")

    def test_field_without_value_or_locked_value_is_omitted(self):
        step = _make_step("s", "OUT.md", OutputFormat.markdown, [_textarea("empty")])
        files = generate_files(_make_config([step]), {})
        assert "## Empty" not in files.get("OUT.md", "")

    def test_multiple_steps_to_same_file_are_joined(self):
        step1 = _make_step("s1", "OUT.md", OutputFormat.markdown, [_textarea("a", default="Alpha")])
        step2 = _make_step("s2", "OUT.md", OutputFormat.markdown, [_textarea("b", default="Beta")])
        files = generate_files(_make_config([step1, step2]), {})
        assert "Alpha" in files["OUT.md"]
        assert "Beta" in files["OUT.md"]


# ---------------------------------------------------------------------------
# Verbatim renderer
# ---------------------------------------------------------------------------


class TestRenderVerbatim:
    def test_content_field_returned_as_is(self):
        step = _make_step(
            "s",
            "out.json",
            OutputFormat.verbatim,
            [
                _textarea("content", default='{"key": "value"}'),
            ],
        )
        files = generate_files(_make_config([step]), {})
        assert files["out.json"] == '{"key": "value"}'

    def test_locked_value_present_with_no_user_input(self):
        step = _make_step(
            "s",
            "out.txt",
            OutputFormat.verbatim,
            [
                _textarea("content", locked_value="# always here"),
            ],
        )
        files = generate_files(_make_config([step]), {})
        assert "# always here" in files["out.txt"]

    def test_locked_value_prepended_to_user_verbatim(self):
        step = _make_step(
            "s",
            "out.txt",
            OutputFormat.verbatim,
            [
                _textarea("content", locked_value="locked line"),
            ],
        )
        files = generate_files(_make_config([step]), {"s": {"content": "user line"}})
        content = files["out.txt"]
        assert content.index("locked line") < content.index("user line")

    def test_empty_step_produces_no_file(self):
        step = _make_step("s", "out.txt", OutputFormat.verbatim, [_textarea("content")])
        files = generate_files(_make_config([step]), {})
        assert "out.txt" not in files


# ---------------------------------------------------------------------------
# Agent renderer
# ---------------------------------------------------------------------------


class TestRenderAgent:
    def _agent_step(self) -> WizardStep:
        agent_field = WizardField(
            id="agents",
            type=FieldType.agent_list,
            label="Agents",
            agent_config=AgentFieldConfig(output_dir=".agents/", file_suffix=".md"),
        )
        return _make_step("s", ".agents/", OutputFormat.text, [agent_field])

    def test_agent_generates_file_per_agent(self):
        step = self._agent_step()
        answers = {
            "s": {
                "agents": [
                    {
                        "name": "security-reviewer",
                        "description": "Reviews code",
                        "tools": ["Read"],
                        "model": "claude-sonnet-4-5",
                        "system_prompt": "Do security review.",
                    },
                    {
                        "name": "test-writer",
                        "description": "Writes tests",
                        "tools": ["Write"],
                        "model": "claude-sonnet-4-5",
                        "system_prompt": "Write tests.",
                    },
                ]
            }
        }
        files = generate_files(_make_config([step]), answers)
        assert ".agents/security-reviewer.md" in files
        assert ".agents/test-writer.md" in files

    def test_agent_file_contains_frontmatter(self):
        step = self._agent_step()
        answers = {
            "s": {
                "agents": [
                    {
                        "name": "my-agent",
                        "description": "Desc",
                        "tools": ["Read", "Write"],
                        "model": "claude-sonnet-4-5",
                        "system_prompt": "Do stuff.",
                    },
                ]
            }
        }
        files = generate_files(_make_config([step]), answers)
        content = files[".agents/my-agent.md"]
        assert content.startswith("---")
        assert "name: my-agent" in content
        assert "description: Desc" in content
        assert '"Read"' in content
        assert '"Write"' in content
        assert "model: claude-sonnet-4-5" in content
        assert "Do stuff." in content

    def test_agent_without_name_is_skipped(self):
        step = self._agent_step()
        answers = {"s": {"agents": [{"name": "", "description": "No name"}]}}
        files = generate_files(_make_config([step]), answers)
        assert not any(k.startswith(".agents/") for k in files)

    def test_non_list_agents_value_is_skipped(self):
        step = self._agent_step()
        answers = {"s": {"agents": "not-a-list"}}
        files = generate_files(_make_config([step]), answers)
        assert not any(k.startswith(".agents/") for k in files)


class TestDirectoryOutputResolver:
    def test_directory_output_with_file_name_field_writes_named_file(self):
        step = _make_step(
            "s",
            ".cursor/rules/",
            OutputFormat.verbatim,
            [
                _textfield("rule_file_name", default="my-rule.mdc"),
                _textarea("content", default="rule content"),
            ],
        )
        files = generate_files(
            _make_config([step]),
            {"s": {"rule_file_name": "my-rule.mdc", "content": "rule content"}},
        )

        assert ".cursor/rules/my-rule.mdc" in files
        assert files[".cursor/rules/my-rule.mdc"] == "rule content"


# ---------------------------------------------------------------------------
# Integration — real configs (loaded via API from seeded DB)
# ---------------------------------------------------------------------------

from fastapi.testclient import TestClient
from app.main import app as _app

_client = TestClient(_app)


def _load_config_from_api(tool_id: str, language_id: str = "python"):
    """Load a WizardConfig via the wizard API backed by the seeded test DB."""
    resp = _client.get(f"/api/wizard/config/{tool_id}", params={"language": language_id})
    assert resp.status_code == 200, f"Failed to load {tool_id}: {resp.text}"
    return WizardConfig.model_validate(resp.json())


class TestGenerateFilesIntegration:
    def test_claude_config_generates_claude_md(self):
        config = _load_config_from_api("claude")
        files = generate_files(config, {})
        assert "CLAUDE.md" in files

    def test_claude_locked_values_always_in_output(self):
        config = _load_config_from_api("claude")
        files = generate_files(config, {})
        md = files["CLAUDE.md"]
        assert "Do not modify generated, vendored, or third-party files unless the task explicitly requires it." in md
        assert "Run lint and tests" in md
        assert "Review every change for security implications" in md

    def test_claude_settings_locked_value_always_in_output(self):
        config = _load_config_from_api("claude")
        files = generate_files(config, {})
        settings = files[".claude/settings.json"]
        assert "CLAUDE_CODE_ENABLE_TELEMETRY" in settings

    def test_user_answers_combined_with_locked_values(self):
        config = _load_config_from_api("claude")
        answers = {"claude_md": {"coding_conventions": "- Project-specific rule."}}
        files = generate_files(config, answers)
        md = files["CLAUDE.md"]
        assert "Do not modify generated, vendored, or third-party files unless the task explicitly requires it." in md
        assert "- Project-specific rule." in md

    def test_copilot_config_generates_instructions_file(self):
        config = _load_config_from_api("copilot")
        answers = {
            "path_instructions": {
                "instruction_files": "---\napplyTo: '**/*.test.ts'\n---\n# Test guidance\n- Use Arrange / Act / Assert structure.\n"
            }
        }
        files = generate_files(config, answers)
        assert ".github/instructions/copilot-instructions.md" in files

    def test_cursor_config_generates_cursorignore(self):
        config = _load_config_from_api("cursor")
        files = generate_files(config, {})
        assert ".cursorignore" in files
        assert ".env" in files[".cursorignore"]

    def test_generate_returns_only_non_empty_files(self):
        for config_id in ("claude", "copilot", "cursor"):
            config = _load_config_from_api(config_id)
            files = generate_files(config, {})
            for filename, content in files.items():
                assert content.strip(), f"Empty file '{filename}' in '{config_id}'"
